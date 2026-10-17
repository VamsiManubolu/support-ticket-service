"""Response schemas for the Jira-style ticket history.
Activity entries, status timeline and time spent in each status."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EventType, TicketStatus


class HistoryEntry(BaseModel):
    id: int
    event_type: EventType
    actor: str
    created_at: datetime
    from_status: TicketStatus | None
    to_status: TicketStatus | None
    note: str | None
    description: str = Field(examples=["agent.smith changed status from OPEN to IN_PROGRESS"])


class StatusPeriod(BaseModel):
    status: TicketStatus
    entered_at: datetime
    entered_by: str
    exited_at: datetime | None = Field(description="null while this is the current status")
    duration_seconds: float = Field(description="Up to now for the current status")


class TicketHistory(BaseModel):
    ticket_id: uuid.UUID
    current_status: TicketStatus
    created_at: datetime
    transition_count: int
    time_in_status: dict[TicketStatus, float] = Field(
        description="Total seconds spent in each status, including the current one"
    )
    status_timeline: list[StatusPeriod]
    entries: list[HistoryEntry]
