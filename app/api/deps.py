"""FastAPI dependencies for the HTTP layer.
Builds a TicketService per request, sharing that request's DB session."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.ticket_repository import TicketRepository
from app.services.publisher import CeleryJobPublisher
from app.services.ticket_service import TicketService

_publisher = CeleryJobPublisher()


def get_ticket_service(db: Annotated[Session, Depends(get_db)]) -> TicketService:
    return TicketService(db, TicketRepository(db), _publisher)


TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]
