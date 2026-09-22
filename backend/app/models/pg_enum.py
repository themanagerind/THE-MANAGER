"""
Small helper so every enum column in the schema creates (and reuses) a
proper native PostgreSQL ENUM type instead of SQLAlchemy's default
VARCHAR+CHECK emulation — matches the `xxx_enum` types named throughout
the DB Schema Specification (e.g. `society_status_enum`, `role_enum`).
"""
import enum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum

E = TypeVar("E", bound=enum.Enum)


def pg_enum(enum_cls: type[E], pg_name: str) -> SAEnum:
    """
    Usage: mapped_column(pg_enum(SocietyStatus, "society_status_enum"))
    `create_type=False` because Alembic migrations create/manage the type
    explicitly (see alembic/versions/ — avoids duplicate-type errors when
    multiple tables/migrations reference the same enum).
    """
    return SAEnum(
        enum_cls,
        name=pg_name,
        values_callable=lambda e: [member.value for member in e],
        create_type=False,
    )
