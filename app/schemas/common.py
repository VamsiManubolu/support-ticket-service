"""Shared response shapes: the generic Page[T] wrapper and the error envelope.
Used by every endpoint."""

import math
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)

    # Wrap a page of items and work out the total number of pages
    @classmethod
    def create(cls, items: Sequence[T], *, page: int, page_size: int, total: int) -> "Page[T]":
        return cls(
            items=list(items),
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size),
        )


class FieldError(BaseModel):
    field: str
    message: str
    type: str


class ValidationErrorDetails(BaseModel):
    errors: list[FieldError]


class HealthResponse(BaseModel):
    status: str
    database: str


class ErrorBody(BaseModel):
    code: str = Field(examples=["TICKET_NOT_FOUND"])
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
