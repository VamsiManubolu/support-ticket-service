"""Database queries for tickets, their events and processing rows.
No business rules and no commits; the calling service owns the transaction."""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Ticket, TicketEvent, TicketProcessing
from app.models.enums import TicketCategory, TicketPriority, TicketStatus


class TicketRepository:
    # flushes but never commits; services own the transaction

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, ticket: Ticket) -> Ticket:
        self.db.add(ticket)
        self.db.flush()
        return ticket

    def get(self, ticket_id: uuid.UUID) -> Ticket | None:
        return self.db.get(Ticket, ticket_id)

    def get_with_processing(self, ticket_id: uuid.UUID) -> Ticket | None:
        stmt = select(Ticket).options(joinedload(Ticket.processing)).where(Ticket.id == ticket_id)
        return self.db.scalars(stmt).one_or_none()

    def get_for_update(self, ticket_id: uuid.UUID) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.id == ticket_id).with_for_update()
        return self.db.scalars(stmt).one_or_none()

    def exists(self, ticket_id: uuid.UUID) -> bool:
        stmt = select(select(Ticket.id).where(Ticket.id == ticket_id).exists())
        return bool(self.db.scalar(stmt))

    # One page of tickets plus the total count, both using the same filters
    def list_tickets(
        self,
        *,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        category: TicketCategory | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Ticket], int]:
        conditions: list[ColumnElement[bool]] = []
        if status is not None:
            conditions.append(Ticket.status == status)
        if priority is not None:
            conditions.append(Ticket.priority == priority)
        if category is not None:
            conditions.append(Ticket.category == category)

        total = self.db.scalar(select(func.count()).select_from(Ticket).where(*conditions)) or 0
        stmt = (
            select(Ticket)
            .where(*conditions)
            .order_by(Ticket.created_at.desc(), Ticket.id)
            .offset(offset)
            .limit(limit)
        )
        return self.db.scalars(stmt).all(), total

    def add_event(self, event: TicketEvent) -> TicketEvent:
        self.db.add(event)
        self.db.flush()
        return event

    # All events for a ticket, oldest first
    def list_events(self, ticket_id: uuid.UUID) -> Sequence[TicketEvent]:
        stmt = (
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at, TicketEvent.id)
        )
        return self.db.scalars(stmt).all()

    def add_processing(self, processing: TicketProcessing) -> TicketProcessing:
        self.db.add(processing)
        self.db.flush()
        return processing

    # Load and lock the processing row so only one worker updates it
    def get_processing_for_update(self, ticket_id: uuid.UUID) -> TicketProcessing | None:
        stmt = (
            select(TicketProcessing)
            .where(TicketProcessing.ticket_id == ticket_id)
            .with_for_update()
        )
        return self.db.scalars(stmt).one_or_none()
