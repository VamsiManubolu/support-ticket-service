"""Domain errors raised by services, each with an HTTP status and error code.
Kept free of FastAPI so services never depend on the web layer."""

import uuid
from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from app.models.enums import TicketStatus


class ErrorCode(StrEnum):
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TICKET_NOT_FOUND = "TICKET_NOT_FOUND"
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    status_code: int = 400
    code: ErrorCode = ErrorCode.BAD_REQUEST

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TicketNotFoundError(AppError):
    status_code = 404
    code = ErrorCode.TICKET_NOT_FOUND

    def __init__(self, ticket_id: uuid.UUID) -> None:
        super().__init__(f"Ticket {ticket_id} not found", {"ticket_id": str(ticket_id)})


class InvalidTransitionError(AppError):
    status_code = 409
    code = ErrorCode.INVALID_STATUS_TRANSITION

    # Include the allowed statuses so the client knows what it can do instead
    def __init__(
        self, current: TicketStatus, target: TicketStatus, allowed: Iterable[TicketStatus]
    ) -> None:
        super().__init__(
            f"Cannot change status from {current} to {target}",
            {
                "current_status": current,
                "requested_status": target,
                "allowed_statuses": sorted(allowed),
            },
        )
