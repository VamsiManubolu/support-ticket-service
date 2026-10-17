"""Ticket business logic: create, read, list, status changes and history.
The only layer that commits; enqueues processing after a ticket is saved."""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.constants import CUSTOMER_ACTOR, EVENT_NOTE_KEY
from app.core.exceptions import TicketNotFoundError
from app.models import Ticket, TicketEvent, TicketProcessing
from app.models.enums import EventType, TicketStatus
from app.repositories.ticket_repository import TicketRepository
from app.schemas.common import Page
from app.schemas.history import TicketHistory
from app.schemas.ticket import TicketCreate, TicketFilter, TicketRead, TicketStatusUpdate
from app.services.history import build_history
from app.services.publisher import JobPublisher
from app.services.state_machine import ensure_transition

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(self, db: Session, repository: TicketRepository, publisher: JobPublisher) -> None:
        self.db = db
        self.repository = repository
        self.publisher = publisher

    # Save the ticket with its processing row and CREATED event, then queue processing
    def create_ticket(self, data: TicketCreate) -> Ticket:
        ticket = Ticket(**data.model_dump(), processing=TicketProcessing())
        self.repository.add(ticket)
        self.repository.add_event(
            TicketEvent(
                ticket_id=ticket.id,
                event_type=EventType.CREATED,
                to_status=TicketStatus.OPEN,
                actor=CUSTOMER_ACTOR,
            )
        )
        # commit before enqueueing, or the worker could look for a ticket that isn't saved yet
        self.db.commit()
        logger.info(
            "Ticket created id=%s priority=%s category=%s",
            ticket.id,
            ticket.priority,
            ticket.category,
        )
        try:
            self.publisher.publish_ticket_created(ticket.id)
        except Exception:
            # ticket is already saved, so don't fail the request; it stays PENDING
            logger.exception("Failed to enqueue processing for ticket %s", ticket.id)
        return ticket

    def get_ticket(self, ticket_id: uuid.UUID) -> Ticket:
        ticket = self.repository.get_with_processing(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        return ticket

    # Filtered, paginated list of tickets
    def list_tickets(self, filters: TicketFilter) -> Page[TicketRead]:
        tickets, total = self.repository.list_tickets(
            status=filters.status,
            priority=filters.priority,
            category=filters.category,
            offset=filters.offset,
            limit=filters.page_size,
        )
        return Page[TicketRead].create(
            [TicketRead.model_validate(ticket) for ticket in tickets],
            page=filters.page,
            page_size=filters.page_size,
            total=total,
        )

    # Validate the transition, update the status and record it in the history
    def update_status(self, ticket_id: uuid.UUID, data: TicketStatusUpdate) -> Ticket:
        # lock the row so two concurrent updates can't both pass the check
        ticket = self.repository.get_for_update(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)

        previous = ticket.status
        ensure_transition(previous, data.status)
        ticket.status = data.status
        self.repository.add_event(
            TicketEvent(
                ticket_id=ticket.id,
                event_type=EventType.STATUS_CHANGED,
                from_status=previous,
                to_status=data.status,
                actor=data.actor,
                event_metadata={EVENT_NOTE_KEY: data.note} if data.note else {},
            )
        )
        self.db.commit()
        logger.info("Ticket %s status %s -> %s by %s", ticket.id, previous, data.status, data.actor)
        return ticket

    def list_events(self, ticket_id: uuid.UUID) -> Sequence[TicketEvent]:
        if not self.repository.exists(ticket_id):
            raise TicketNotFoundError(ticket_id)
        return self.repository.list_events(ticket_id)

    def get_history(self, ticket_id: uuid.UUID) -> TicketHistory:
        ticket = self.repository.get(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        events = self.repository.list_events(ticket_id)
        return build_history(ticket, events, now=datetime.now(UTC))
