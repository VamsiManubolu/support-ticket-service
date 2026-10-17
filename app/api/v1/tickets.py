"""Ticket endpoints under /api/v1/tickets.
HTTP only: parse the request, call TicketService, return the response model."""

import uuid
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import TicketServiceDep
from app.core.constants import LOCATION_HEADER
from app.models import Ticket, TicketEvent
from app.schemas.common import ErrorResponse, Page
from app.schemas.event import EventRead
from app.schemas.history import TicketHistory
from app.schemas.ticket import (
    TicketCreate,
    TicketDetail,
    TicketFilter,
    TicketRead,
    TicketStatusUpdate,
)

TICKETS_PREFIX = "/tickets"
TICKET_PATH = "/{ticket_id}"
TICKET_STATUS_PATH = f"{TICKET_PATH}/status"
TICKET_EVENTS_PATH = f"{TICKET_PATH}/events"
TICKET_HISTORY_PATH = f"{TICKET_PATH}/history"

router = APIRouter(prefix=TICKETS_PREFIX, tags=["tickets"])

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Ticket not found"}
}
_INVALID: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Validation error"}
}


# Create a ticket; it starts OPEN and is processed in the background
@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TicketDetail,
    responses=_INVALID,
    summary="Create a ticket",
)
def create_ticket(
    payload: TicketCreate, request: Request, response: Response, service: TicketServiceDep
) -> Ticket:
    ticket = service.create_ticket(payload)
    response.headers[LOCATION_HEADER] = str(
        request.url_for(get_ticket.__name__, ticket_id=ticket.id)
    )
    return ticket


# List tickets, newest first, with optional filters and pagination
@router.get(
    "",
    response_model=Page[TicketRead],
    responses=_INVALID,
    summary="List tickets (filtered, paginated, newest first)",
)
def list_tickets(
    filters: Annotated[TicketFilter, Query()], service: TicketServiceDep
) -> Page[TicketRead]:
    return service.list_tickets(filters)


# Get one ticket with its processing result
@router.get(
    TICKET_PATH,
    response_model=TicketDetail,
    responses={**_NOT_FOUND, **_INVALID},
    summary="Get a ticket with its processing result",
)
def get_ticket(ticket_id: uuid.UUID, service: TicketServiceDep) -> Ticket:
    return service.get_ticket(ticket_id)


# Change a ticket's status; invalid transitions return 409
@router.patch(
    TICKET_STATUS_PATH,
    response_model=TicketRead,
    responses={
        **_NOT_FOUND,
        **_INVALID,
        409: {"model": ErrorResponse, "description": "Transition not allowed"},
    },
    summary="Change a ticket's status",
)
def update_ticket_status(
    ticket_id: uuid.UUID, payload: TicketStatusUpdate, service: TicketServiceDep
) -> Ticket:
    return service.update_status(ticket_id, payload)


# Get the ticket's raw event log, oldest first
@router.get(
    TICKET_EVENTS_PATH,
    response_model=list[EventRead],
    responses={**_NOT_FOUND, **_INVALID},
    summary="Get a ticket's raw event log, oldest first",
)
def list_ticket_events(ticket_id: uuid.UUID, service: TicketServiceDep) -> Sequence[TicketEvent]:
    return service.list_events(ticket_id)


# Get a readable history with time spent in each status
@router.get(
    TICKET_HISTORY_PATH,
    response_model=TicketHistory,
    responses={**_NOT_FOUND, **_INVALID},
    summary="Get a Jira-style history: activity and time spent in each status",
)
def get_ticket_history(ticket_id: uuid.UUID, service: TicketServiceDep) -> TicketHistory:
    return service.get_history(ticket_id)
