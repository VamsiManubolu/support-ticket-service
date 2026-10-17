"""Ticket request and response schemas, with input validation.
Create, status update, list filters, and the list/detail views."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.schemas.processing import ProcessingRead

_INPUT_CONFIG = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TicketCreate(BaseModel):
    model_config = _INPUT_CONFIG

    customer_name: str = Field(min_length=1, max_length=120, examples=["Jane Doe"])
    customer_email: EmailStr = Field(examples=["jane@example.com"])
    subject: str = Field(min_length=3, max_length=200, examples=["Cannot log in"])
    description: str = Field(
        min_length=10,
        max_length=5000,
        examples=["I reset my password but still get 'invalid credentials'."],
    )
    priority: TicketPriority = TicketPriority.MEDIUM
    category: TicketCategory


class TicketStatusUpdate(BaseModel):
    model_config = _INPUT_CONFIG

    status: TicketStatus
    actor: str = Field(min_length=1, max_length=120, examples=["agent.smith"])
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note")
    @classmethod
    def _blank_note_to_none(cls, value: str | None) -> str | None:
        return value or None


class TicketFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    category: TicketCategory | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_name: str
    customer_email: str
    subject: str
    description: str
    priority: TicketPriority
    category: TicketCategory
    status: TicketStatus
    assigned_agent_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketRead):
    processing: ProcessingRead | None
