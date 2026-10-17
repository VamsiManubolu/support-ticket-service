"""Allowed ticket status transitions and the check that enforces them.
Invalid moves raise InvalidTransitionError (HTTP 409)."""

from types import MappingProxyType

from app.core.exceptions import InvalidTransitionError
from app.models.enums import TicketStatus

ALLOWED_TRANSITIONS = MappingProxyType(
    {
        TicketStatus.OPEN: frozenset({TicketStatus.IN_PROGRESS, TicketStatus.CLOSED}),
        TicketStatus.IN_PROGRESS: frozenset({TicketStatus.OPEN, TicketStatus.RESOLVED}),
        TicketStatus.RESOLVED: frozenset({TicketStatus.IN_PROGRESS, TicketStatus.CLOSED}),
        TicketStatus.CLOSED: frozenset[TicketStatus](),
    }
)


def ensure_transition(current: TicketStatus, target: TicketStatus) -> None:
    # no status lists itself, so same-status updates are rejected too
    allowed = ALLOWED_TRANSITIONS[current]
    if target not in allowed:
        raise InvalidTransitionError(current, target, allowed)
