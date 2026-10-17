"""Imports every model so they are registered on Base.metadata.
Alembic and relationship lookups rely on this."""

from app.models.agent import Agent
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.ticket_processing import TicketProcessing

__all__ = ["Agent", "Ticket", "TicketEvent", "TicketProcessing"]
