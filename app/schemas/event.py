"""Response schema for a ticket event.
Used by GET /tickets/{id}/events."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EventType, TicketStatus


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: uuid.UUID
    event_type: EventType
    from_status: TicketStatus | None
    to_status: TicketStatus | None
    actor: str
    # ORM attribute is event_metadata
    metadata: dict[str, Any] = Field(validation_alias="event_metadata")
    created_at: datetime
