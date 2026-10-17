"""Response schema for a ticket's processing result.
Embedded in the single-ticket view."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProcessingStatus, TicketPriority


class ProcessingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ProcessingStatus
    summary: str | None
    suggested_priority: TicketPriority | None
    is_spam: bool | None
    spam_score: Decimal | None
    department: str | None
    error: str | None
    attempts: int
    processed_at: datetime | None
