"""Background processing result for a ticket (one row per ticket).
Holds the summary, spam score, suggested priority, department and retry state."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pg_enum
from app.models.enums import ProcessingStatus, TicketPriority
from app.models.ticket import Ticket


class TicketProcessing(TimestampMixin, Base):
    __tablename__ = "ticket_processing"
    __table_args__ = (
        CheckConstraint("spam_score >= 0 AND spam_score <= 1", name="spam_score_range"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
    )

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(Ticket.id, ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[ProcessingStatus] = mapped_column(
        pg_enum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        server_default=ProcessingStatus.PENDING.value,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    suggested_priority: Mapped[TicketPriority | None] = mapped_column(pg_enum(TicketPriority))
    is_spam: Mapped[bool | None] = mapped_column(Boolean)
    spam_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    department: Mapped[str | None] = mapped_column(String(50))
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
