"""Declarative base, timestamp mixins and the Postgres enum helper.
Shared by every model."""

import re
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# stable constraint names, so migrations can refer to them
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Map a Python enum to the matching Postgres enum type
def pg_enum(enum_cls: type[StrEnum]) -> ENUM:
    # TicketStatus -> ticket_status
    # the migration creates the type
    return ENUM(
        enum_cls,
        name=re.sub(r"(?<!^)(?=[A-Z])", "_", enum_cls.__name__).lower(),
        values_callable=lambda members: [member.value for member in members],
        create_type=False,
    )
