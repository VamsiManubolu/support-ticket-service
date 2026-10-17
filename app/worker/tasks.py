"""Celery task that processes a newly created ticket.
Retries transient failures with backoff and marks the ticket FAILED after the last retry."""

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Any

from billiard.einfo import ExceptionInfo
from celery import Task
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.middleware import bind_request_id
from app.db.session import SessionLocal
from app.repositories.ticket_repository import TicketRepository
from app.services.analyzer import (
    TransientAnalysisError,
    analyze_with_timeout,
    get_analyzer,
)
from app.services.processing_service import ProcessingService
from app.worker.celery_app import PROCESS_TICKET_TASK, REQUEST_ID_HEADER_KEY, celery_app

logger = logging.getLogger(__name__)

# Task is only generic in the type stubs
if TYPE_CHECKING:
    _TaskBase = Task[[str], None]
else:
    _TaskBase = Task


class ProcessTicketTask(_TaskBase):
    # Celery calls this once retries are used up; mark the ticket FAILED
    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: ExceptionInfo,
    ) -> None:
        # runs after the last retry fails
        try:
            ticket_id = uuid.UUID(str(args[0]))
        except (IndexError, ValueError):
            logger.error("process_ticket failed with an invalid ticket id: %r", args)
            return
        with SessionLocal() as db:
            ProcessingService(db, TicketRepository(db)).mark_failed(
                ticket_id, f"{type(exc).__name__}: {exc}"
            )


# Background job: analyze a new ticket and save the results
@celery_app.task(
    bind=True,
    base=ProcessTicketTask,
    name=PROCESS_TICKET_TASK,
    autoretry_for=(OperationalError, TransientAnalysisError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
)
def process_ticket(self: ProcessTicketTask, ticket_id: str) -> None:
    bind_request_id(getattr(self.request, REQUEST_ID_HEADER_KEY, None) or self.request.id)
    parsed_id = uuid.UUID(ticket_id)
    logger.info("Processing ticket %s (attempt %d)", parsed_id, self.request.retries + 1)

    with SessionLocal() as db:
        service = ProcessingService(db, TicketRepository(db))
        snapshot = service.start_attempt(parsed_id)
        if snapshot is None:
            return
        # start_attempt committed, so no connection is held during the analysis
        timeout = get_settings().processing_timeout_seconds
        result = asyncio.run(analyze_with_timeout(get_analyzer(), snapshot, timeout))
        service.complete(parsed_id, result)
