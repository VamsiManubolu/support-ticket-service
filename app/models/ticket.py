"""Ticket model and its indexes.
The core table: customer details, subject, priority, category and status."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, pg_enum
from app.models.agent import Agent
from app.models.enums import TicketCategory, TicketPriority, TicketStatus

if TYPE_CHECKING:
    from app.models.ticket_processing import TicketProcessing


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(254), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[TicketPriority] = mapped_column(
        pg_enum(TicketPriority),
        default=TicketPriority.MEDIUM,
        server_default=TicketPriority.MEDIUM.value,
        index=True,
    )
    category: Mapped[TicketCategory] = mapped_column(pg_enum(TicketCategory), index=True)
    status: Mapped[TicketStatus] = mapped_column(
        pg_enum(TicketStatus),
        default=TicketStatus.OPEN,
        server_default=TicketStatus.OPEN.value,
        index=True,
    )
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(Agent.id, ondelete="SET NULL")
    )

    # must be loaded explicitly (joinedload), so lists can't trigger N+1 queries
    processing: Mapped["TicketProcessing | None"] = relationship(lazy="raise", passive_deletes=True)


# DESC index needs the mapped column, so it's declared after the class
Index("ix_tickets_created_at_desc", Ticket.created_at.desc())
Index("ix_tickets_status_priority_created_at", Ticket.status, Ticket.priority, Ticket.created_at)
