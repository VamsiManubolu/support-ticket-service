"""initial schema: enums, agents, tickets, ticket_events, ticket_processing

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ticket_status = postgresql.ENUM(
    "OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED", name="ticket_status", create_type=False
)
ticket_priority = postgresql.ENUM(
    "LOW", "MEDIUM", "HIGH", "URGENT", name="ticket_priority", create_type=False
)
ticket_category = postgresql.ENUM(
    "BILLING", "TECHNICAL", "ACCOUNT", "GENERAL", name="ticket_category", create_type=False
)
event_type = postgresql.ENUM(
    "CREATED", "STATUS_CHANGED", "ASSIGNED", "PROCESSED", name="event_type", create_type=False
)
processing_status = postgresql.ENUM(
    "PENDING", "COMPLETED", "FAILED", name="processing_status", create_type=False
)
ALL_ENUMS = (ticket_status, ticket_priority, ticket_category, event_type, processing_status)


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for enum in ALL_ENUMS:
        enum.create(bind, checkfirst=False)

    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_agents"),
        sa.UniqueConstraint("email", name="uq_agents_email"),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("customer_name", sa.String(120), nullable=False),
        sa.Column("customer_email", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", ticket_priority, server_default="MEDIUM", nullable=False),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("status", ticket_status, server_default="OPEN", nullable=False),
        sa.Column("assigned_agent_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_tickets"),
        sa.ForeignKeyConstraint(
            ["assigned_agent_id"],
            ["agents.id"],
            name="fk_tickets_assigned_agent_id_agents",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_priority", "tickets", ["priority"])
    op.create_index("ix_tickets_category", "tickets", ["category"])
    op.create_index("ix_tickets_customer_email", "tickets", ["customer_email"])
    op.create_index("ix_tickets_created_at_desc", "tickets", [sa.text("created_at DESC")])
    op.create_index(
        "ix_tickets_status_priority_created_at", "tickets", ["status", "priority", "created_at"]
    )

    op.create_table(
        "ticket_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", event_type, nullable=False),
        sa.Column("from_status", ticket_status, nullable=True),
        sa.Column("to_status", ticket_status, nullable=True),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_events"),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_ticket_events_ticket_id_tickets",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_ticket_events_ticket_id_created_at", "ticket_events", ["ticket_id", "created_at"]
    )

    op.create_table(
        "ticket_processing",
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("status", processing_status, server_default="PENDING", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("suggested_priority", ticket_priority, nullable=True),
        sa.Column("is_spam", sa.Boolean(), nullable=True),
        sa.Column("spam_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("department", sa.String(50), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("ticket_id", name="pk_ticket_processing"),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name="fk_ticket_processing_ticket_id_tickets",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "spam_score >= 0 AND spam_score <= 1", name="ck_ticket_processing_spam_score_range"
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_ticket_processing_attempts_non_negative"),
    )


def downgrade() -> None:
    op.drop_table("ticket_processing")
    op.drop_table("ticket_events")
    op.drop_table("tickets")
    op.drop_table("agents")
    bind = op.get_bind()
    for enum in reversed(ALL_ENUMS):
        enum.drop(bind, checkfirst=False)
