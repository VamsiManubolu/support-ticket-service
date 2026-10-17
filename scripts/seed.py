"""Seeds 3 agents and 15 tickets covering every status, priority and category.
Skipped when tickets already exist or SEED_ON_START is false; IDs are stable across resets."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import CUSTOMER_ACTOR, EVENT_NOTE_KEY, SYSTEM_ACTOR
from app.core.logging import setup_logging
from app.db.session import SessionLocal
from app.models import Agent, Ticket, TicketEvent, TicketProcessing
from app.models.enums import (
    Department,
    EventType,
    ProcessingStatus,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.services import processing
from app.services.state_machine import ensure_transition

logger = logging.getLogger(__name__)

SEED_NAMESPACE = uuid.UUID("6f1c2e9a-3b7d-4c55-9a51-2f0e8d4b7c10")
SUPPORT_LEAD_ACTOR = "support.lead"
FAILED_ERROR = "TransientAnalysisError: Analysis timed out after 30.0s"
# hours after creation at which each status change happens (max 4 changes)
STEP_HOURS = (3, 8, 14, 20)

S = TicketStatus
NOTES = {
    S.IN_PROGRESS: "Looking into it",
    S.OPEN: "Waiting for the customer's reply",
    S.RESOLVED: "Fixed and confirmed with the customer",
    S.CLOSED: "Closing after confirmation",
}


@dataclass(frozen=True)
class SeedTicket:
    key: str
    customer_name: str
    customer_email: str
    subject: str
    description: str
    category: TicketCategory
    priority: TicketPriority
    path: tuple[TicketStatus, ...] = ()
    processing: ProcessingStatus = ProcessingStatus.COMPLETED
    notes: dict[TicketStatus, str] = field(default_factory=dict)


AGENTS = (
    ("Alice Johnson", "alice@support.example.com", Department.BILLING),
    ("Bob Smith", "bob@support.example.com", Department.TECHNICAL_SUPPORT),
    ("Carol Diaz", "carol@support.example.com", Department.ACCOUNT_MANAGEMENT),
)

TICKETS = (
    SeedTicket(
        "t01",
        "Jane Doe",
        "jane@example.com",
        "Charged twice for March",
        "I was charged twice for my March subscription. Please refund the duplicate charge.",
        TicketCategory.BILLING,
        TicketPriority.MEDIUM,
    ),
    SeedTicket(
        "t02",
        "Raj Patel",
        "raj@acme.example",
        "Production API down",
        "Our integration returns 503 errors since 09:00 UTC. This is an outage for our users.",
        TicketCategory.TECHNICAL,
        TicketPriority.URGENT,
    ),
    SeedTicket(
        "t03",
        "Mia Chen",
        "mia@example.org",
        "Feature request: dark mode",
        "Just wondering if dark mode is on the roadmap. It would make the dashboard easier.",
        TicketCategory.GENERAL,
        TicketPriority.LOW,
        processing=ProcessingStatus.PENDING,
    ),
    SeedTicket(
        "t04",
        "Tom Brown",
        "tom@example.com",
        "Cannot log in after password reset",
        "I reset my password but still cannot log in. The page says invalid credentials.",
        TicketCategory.ACCOUNT,
        TicketPriority.HIGH,
    ),
    SeedTicket(
        "t05",
        "Lena Novak",
        "lena@example.org",
        "App crashes on export",
        "The desktop app crashes every time I export a report to PDF.",
        TicketCategory.TECHNICAL,
        TicketPriority.HIGH,
        (S.IN_PROGRESS,),
    ),
    SeedTicket(
        "t06",
        "Omar Haddad",
        "omar@acme.example",
        "Invoice shows old company name",
        "Our April invoice lists our old company name. Please update it.",
        TicketCategory.BILLING,
        TicketPriority.MEDIUM,
        (S.IN_PROGRESS,),
    ),
    SeedTicket(
        "t07",
        "Sara Kim",
        "sara@example.com",
        "Change account email",
        "Please change the email on our account to finance@acme.example.",
        TicketCategory.ACCOUNT,
        TicketPriority.MEDIUM,
        (S.IN_PROGRESS,),
    ),
    SeedTicket(
        "t08",
        "Ivan Petrov",
        "ivan@example.org",
        "Possible security breach",
        "We noticed logins from an unknown country. Was our account hacked?",
        TicketCategory.GENERAL,
        TicketPriority.URGENT,
        (S.IN_PROGRESS,),
        processing=ProcessingStatus.FAILED,
    ),
    SeedTicket(
        "t09",
        "Grace Lee",
        "grace@example.com",
        "Refund not received",
        "The refund approved last week has not arrived in my bank account.",
        TicketCategory.BILLING,
        TicketPriority.HIGH,
        (S.IN_PROGRESS, S.RESOLVED),
    ),
    SeedTicket(
        "t10",
        "Diego Ruiz",
        "diego@acme.example",
        "Webhook retries unclear",
        "How do I configure webhook retries? The docs are unclear about the backoff.",
        TicketCategory.TECHNICAL,
        TicketPriority.MEDIUM,
        (S.IN_PROGRESS, S.OPEN, S.IN_PROGRESS, S.RESOLVED),
    ),
    SeedTicket(
        "t11",
        "Hana Sato",
        "hana@example.org",
        "Update profile photo",
        "Question: how do I update the photo on my profile?",
        TicketCategory.ACCOUNT,
        TicketPriority.LOW,
        (S.IN_PROGRESS, S.RESOLVED),
    ),
    SeedTicket(
        "t12",
        "Paul Martin",
        "paul@example.com",
        "Payment page error",
        "The payment page shows an error after I enter my card details.",
        TicketCategory.GENERAL,
        TicketPriority.MEDIUM,
        (S.IN_PROGRESS, S.RESOLVED),
    ),
    SeedTicket(
        "t13",
        "Nora Ali",
        "nora@example.org",
        "Typo in the docs",
        "There is a typo on the getting started page, second paragraph.",
        TicketCategory.TECHNICAL,
        TicketPriority.LOW,
        (S.IN_PROGRESS, S.RESOLVED, S.CLOSED),
    ),
    SeedTicket(
        "t14",
        "Prize Team",
        "prizes@spam.example",
        "WINNER!!! Claim your prize",
        "Click here http://prize.example to claim your lottery winnings!!! Act now.",
        TicketCategory.GENERAL,
        TicketPriority.LOW,
        (S.CLOSED,),
        notes={S.CLOSED: "Spam"},
    ),
    SeedTicket(
        "t15",
        "Ella White",
        "ella@acme.example",
        "Duplicate charges on every card",
        "Every card on file was charged twice today. We need a refund urgently.",
        TicketCategory.BILLING,
        TicketPriority.URGENT,
        (S.IN_PROGRESS, S.RESOLVED, S.CLOSED),
    ),
)


def seed_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)


def build_agents() -> list[Agent]:
    return [
        Agent(id=seed_id(email), name=name, email=email, department=department)
        for name, email, department in AGENTS
    ]


def agent_for(department: Department, agents: list[Agent]) -> Agent:
    # customer_support has no dedicated agent in the seed; the last agent covers it
    return next((a for a in agents if a.department == department), agents[-1])


# Build one ticket with its events, walking it through its status path
def build_ticket(
    spec: SeedTicket, created_at: datetime, agents: list[Agent]
) -> tuple[Ticket, list[TicketEvent]]:
    department = processing.route_department(spec.category, spec.subject, spec.description)
    ticket = Ticket(
        id=seed_id(spec.key),
        customer_name=spec.customer_name,
        customer_email=spec.customer_email,
        subject=spec.subject,
        description=spec.description,
        category=spec.category,
        priority=spec.priority,
        status=TicketStatus.OPEN,
        created_at=created_at,
        updated_at=created_at,
        processing=build_processing(spec, created_at),
    )
    events = [
        TicketEvent(
            event_type=EventType.CREATED,
            to_status=TicketStatus.OPEN,
            actor=CUSTOMER_ACTOR,
            created_at=created_at,
        )
    ]
    if spec.processing == ProcessingStatus.COMPLETED:
        assert ticket.processing is not None
        events.append(
            TicketEvent(
                event_type=EventType.PROCESSED,
                actor=SYSTEM_ACTOR,
                event_metadata={
                    "department": department,
                    "suggested_priority": ticket.processing.suggested_priority,
                    "is_spam": ticket.processing.is_spam,
                },
                created_at=created_at + timedelta(minutes=1),
            )
        )

    agent = agent_for(department, agents)
    if spec.path and spec.path[0] == TicketStatus.IN_PROGRESS:
        ticket.assigned_agent_id = agent.id
        events.append(
            TicketEvent(
                event_type=EventType.ASSIGNED,
                actor=SUPPORT_LEAD_ACTOR,
                event_metadata={"agent_id": str(agent.id), "agent_name": agent.name},
                created_at=created_at + timedelta(hours=1),
            )
        )

    for target, hours in zip(spec.path, STEP_HOURS, strict=False):
        ensure_transition(ticket.status, target)
        changed_at = created_at + timedelta(hours=hours)
        note = spec.notes.get(target, NOTES[target])
        events.append(
            TicketEvent(
                event_type=EventType.STATUS_CHANGED,
                from_status=ticket.status,
                to_status=target,
                actor=agent.name,
                event_metadata={EVENT_NOTE_KEY: note},
                created_at=changed_at,
            )
        )
        ticket.status = target
        ticket.updated_at = changed_at
    return ticket, events


# Processing row for a seed ticket: pending, failed, or computed from the rules
def build_processing(spec: SeedTicket, created_at: datetime) -> TicketProcessing:
    if spec.processing == ProcessingStatus.PENDING:
        return TicketProcessing(status=ProcessingStatus.PENDING, attempts=0)
    if spec.processing == ProcessingStatus.FAILED:
        return TicketProcessing(status=ProcessingStatus.FAILED, attempts=4, error=FAILED_ERROR)
    spam = processing.detect_spam(spec.subject, spec.description)
    return TicketProcessing(
        status=ProcessingStatus.COMPLETED,
        summary=processing.summarize(spec.subject, spec.description),
        is_spam=spam.is_spam,
        spam_score=spam.score,
        suggested_priority=processing.suggest_priority(
            spec.subject, spec.description, spec.priority
        ),
        department=processing.route_department(spec.category, spec.subject, spec.description),
        attempts=1,
        processed_at=created_at + timedelta(minutes=1),
    )


# Insert agents and tickets unless tickets already exist
def seed(db: Session) -> bool:
    if db.scalar(select(Ticket.id).limit(1)) is not None:
        logger.info("Tickets already exist; skipping seed")
        return False

    agents = build_agents()
    db.add_all(agents)
    now = datetime.now(UTC)
    for index, spec in enumerate(TICKETS):
        created_at = now - timedelta(days=len(TICKETS) - index)
        ticket, events = build_ticket(spec, created_at, agents)
        db.add(ticket)
        db.flush()
        for event in events:
            event.ticket_id = ticket.id
        db.add_all(events)
    db.commit()
    logger.info("Seeded %d agents and %d tickets", len(AGENTS), len(TICKETS))
    return True


# Entry point: python -m scripts.seed
def main() -> None:
    settings = get_settings()
    setup_logging(settings)
    if not settings.seed_on_start:
        logger.info("SEED_ON_START is false; skipping seed")
        return
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main()
