"""Saves background processing results for the worker.
Each step is a short transaction, so no lock is held during the analysis."""

import logging
import uuid
from datetime import UTC, datetime
from typing import TypedDict

from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_ACTOR
from app.models import TicketEvent
from app.models.enums import Department, EventType, ProcessingStatus, TicketPriority
from app.repositories.ticket_repository import TicketRepository
from app.services.analyzer import AnalysisResult, TicketInput

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 1000


class ProcessedEventMetadata(TypedDict):
    department: Department
    suggested_priority: TicketPriority
    is_spam: bool


class ProcessingService:
    def __init__(self, db: Session, repository: TicketRepository) -> None:
        self.db = db
        self.repository = repository

    # Claim the ticket for processing; returns None if it's missing or already done
    def start_attempt(self, ticket_id: uuid.UUID) -> TicketInput | None:
        processing = self.repository.get_processing_for_update(ticket_id)
        if processing is None:
            logger.warning("No processing row for ticket %s; skipping", ticket_id)
            self.db.rollback()
            return None
        if processing.status == ProcessingStatus.COMPLETED:
            logger.info("Ticket %s already processed; skipping duplicate delivery", ticket_id)
            self.db.rollback()
            return None

        ticket = self.repository.get(ticket_id)
        if ticket is None:
            self.db.rollback()
            return None
        processing.attempts += 1
        snapshot = TicketInput(
            ticket_id=ticket.id,
            subject=ticket.subject,
            description=ticket.description,
            category=ticket.category,
            priority=ticket.priority,
        )
        self.db.commit()
        return snapshot

    # Save the analysis results and record a PROCESSED event
    def complete(self, ticket_id: uuid.UUID, result: AnalysisResult) -> None:
        processing = self.repository.get_processing_for_update(ticket_id)
        if processing is None or processing.status == ProcessingStatus.COMPLETED:
            # ticket deleted, or a duplicate delivery finished first
            self.db.rollback()
            return

        processing.status = ProcessingStatus.COMPLETED
        processing.summary = result.summary
        processing.is_spam = result.is_spam
        processing.spam_score = result.spam_score
        processing.suggested_priority = result.suggested_priority
        processing.department = result.department
        processing.error = None
        processing.processed_at = datetime.now(UTC)
        self.repository.add_event(
            TicketEvent(
                ticket_id=ticket_id,
                event_type=EventType.PROCESSED,
                actor=SYSTEM_ACTOR,
                event_metadata=ProcessedEventMetadata(
                    department=result.department,
                    suggested_priority=result.suggested_priority,
                    is_spam=result.is_spam,
                ),
            )
        )
        self.db.commit()
        logger.info(
            "Ticket %s processed: department=%s priority=%s spam=%s",
            ticket_id,
            result.department,
            result.suggested_priority,
            result.is_spam,
        )

    # Mark processing as FAILED after the last retry, keeping the error
    def mark_failed(self, ticket_id: uuid.UUID, error: str) -> None:
        processing = self.repository.get_processing_for_update(ticket_id)
        if processing is None or processing.status == ProcessingStatus.COMPLETED:
            self.db.rollback()
            return
        processing.status = ProcessingStatus.FAILED
        processing.error = error[:MAX_ERROR_LENGTH]
        self.db.commit()
        logger.error("Ticket %s processing failed permanently: %s", ticket_id, error)
