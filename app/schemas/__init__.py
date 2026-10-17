"""Request and response DTOs used by the API.
Re-exported here for shorter imports."""

from app.schemas.common import ErrorBody, ErrorResponse, Page
from app.schemas.event import EventRead
from app.schemas.history import HistoryEntry, StatusPeriod, TicketHistory
from app.schemas.processing import ProcessingRead
from app.schemas.ticket import (
    TicketCreate,
    TicketDetail,
    TicketFilter,
    TicketRead,
    TicketStatusUpdate,
)

__all__ = [
    "ErrorBody",
    "ErrorResponse",
    "EventRead",
    "HistoryEntry",
    "Page",
    "ProcessingRead",
    "StatusPeriod",
    "TicketCreate",
    "TicketDetail",
    "TicketFilter",
    "TicketHistory",
    "TicketRead",
    "TicketStatusUpdate",
]
