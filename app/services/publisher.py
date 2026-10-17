"""Publishes background jobs when a ticket is created.
TicketService depends on the JobPublisher Protocol; Celery is the real implementation."""

import uuid
from typing import Protocol

from app.core.middleware import get_request_id
from app.worker.celery_app import PROCESS_TICKET_TASK, REQUEST_ID_HEADER_KEY, celery_app


class JobPublisher(Protocol):
    def publish_ticket_created(self, ticket_id: uuid.UUID) -> None: ...


class CeleryJobPublisher:
    # send by name so the API doesn't import worker code
    def publish_ticket_created(self, ticket_id: uuid.UUID) -> None:
        celery_app.send_task(
            PROCESS_TICKET_TASK,
            args=[str(ticket_id)],
            headers={REQUEST_ID_HEADER_KEY: get_request_id()},
        )
