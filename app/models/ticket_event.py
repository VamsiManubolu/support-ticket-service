"""Ticket event model: the append-only audit log of a ticket.
One row per creation, status change or processing result."""

import uuid
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Identity, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, pg_enum
from app.models.enums import EventType, TicketStatus
from app.models.ticket import Ticket


class TicketEvent(CreatedAtMixin, Base):
    __tablename__ = "ticket_events"
    __table_args__ = (Index("ix_ticket_events_ticket_id_created_at", "ticket_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Ticket.id, ondelete="CASCADE"))
    event_type: Mapped[EventType] = mapped_column(pg_enum(EventType))
    from_status: Mapped[TicketStatus | None] = mapped_column(pg_enum(TicketStatus))
    to_status: Mapped[TicketStatus | None] = mapped_column(pg_enum(TicketStatus))
    actor: Mapped[str] = mapped_column(String(120))
    # "metadata" is reserved by SQLAlchemy
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
