"""Builds the Jira-style history view from a ticket and its events.
Pure functions: no database access, so it's easy to test."""

from collections.abc import Sequence
from datetime import datetime
from typing import assert_never

from app.core.constants import EVENT_NOTE_KEY, UNKNOWN_ACTOR
from app.models import Ticket, TicketEvent
from app.models.enums import EventType, TicketStatus
from app.schemas.history import HistoryEntry, StatusPeriod, TicketHistory


# Combine the activity log, status timeline and time spent per status
def build_history(ticket: Ticket, events: Sequence[TicketEvent], now: datetime) -> TicketHistory:
    timeline = _status_timeline(ticket, events, now)
    time_in_status = dict.fromkeys(TicketStatus, 0.0)
    for period in timeline:
        time_in_status[period.status] += period.duration_seconds

    return TicketHistory(
        ticket_id=ticket.id,
        current_status=ticket.status,
        created_at=ticket.created_at,
        transition_count=len(timeline) - 1,
        time_in_status={status: round(total, 3) for status, total in time_in_status.items()},
        status_timeline=timeline,
        entries=[_entry(event) for event in events],
    )


# Turn status-change events into periods: when each status started and ended
def _status_timeline(
    ticket: Ticket, events: Sequence[TicketEvent], now: datetime
) -> list[StatusPeriod]:
    created_by = next(
        (event.actor for event in events if event.event_type == EventType.CREATED), UNKNOWN_ACTOR
    )
    changes = [event for event in events if event.event_type == EventType.STATUS_CHANGED]
    initial_status = (changes[0].from_status if changes else None) or ticket.status

    starts = [(initial_status, ticket.created_at, created_by)]
    for change in changes:
        if change.to_status is not None:
            starts.append((change.to_status, change.created_at, change.actor))

    periods = []
    for index, (status, entered_at, entered_by) in enumerate(starts):
        exited_at = starts[index + 1][1] if index + 1 < len(starts) else None
        periods.append(
            StatusPeriod(
                status=status,
                entered_at=entered_at,
                entered_by=entered_by,
                exited_at=exited_at,
                duration_seconds=_seconds_between(entered_at, exited_at or now),
            )
        )
    return periods


def _seconds_between(start: datetime, end: datetime) -> float:
    # app and DB clocks can be a few ms apart
    return round(max((end - start).total_seconds(), 0.0), 3)


# Convert one event into a readable history entry
def _entry(event: TicketEvent) -> HistoryEntry:
    note = event.event_metadata.get(EVENT_NOTE_KEY)
    return HistoryEntry(
        id=event.id,
        event_type=event.event_type,
        actor=event.actor,
        created_at=event.created_at,
        from_status=event.from_status,
        to_status=event.to_status,
        note=note if isinstance(note, str) else None,
        description=_describe(event),
    )


# One-line text for an event, e.g. "alice changed status from OPEN to IN_PROGRESS"
def _describe(event: TicketEvent) -> str:
    match event.event_type:
        case EventType.CREATED:
            return f"{event.actor} created the ticket"
        case EventType.STATUS_CHANGED:
            return f"{event.actor} changed status from {event.from_status} to {event.to_status}"
        case EventType.ASSIGNED:
            return f"{event.actor} assigned the ticket"
        case EventType.PROCESSED:
            return f"{event.actor} processed the ticket"
        case _:
            assert_never(event.event_type)
