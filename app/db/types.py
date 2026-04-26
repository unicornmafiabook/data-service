"""
Dialect-aware ``TypeDecorator``s.

Production runs on PostgreSQL (Supabase) with native ``ARRAY(TEXT)`` and
``JSONB`` columns; tests run on SQLite in-memory which has neither type.
The decorators below let the same SQLModel definitions bind to both
backends — a Python ``list[str]`` becomes ``ARRAY(TEXT)`` on Postgres
and ``JSON`` on SQLite, and a Python ``dict`` becomes ``JSONB`` on
Postgres and ``JSON`` on SQLite.
"""

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine


class TextArray(TypeDecorator):
    """List of strings: ``ARRAY(TEXT)`` on Postgres, ``JSON`` on SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(String))
        return dialect.type_descriptor(JSON())

    def process_bind_param(
        self, value: list[str] | None, dialect: Dialect
    ) -> list[str] | None:
        if value is None:
            return None
        return list(value)

    def process_result_value(
        self, value: list[str] | None, dialect: Dialect
    ) -> list[str]:
        if value is None:
            return []
        return list(value)


class JsonB(TypeDecorator):
    """JSON blob: ``JSONB`` on Postgres, ``JSON`` on SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())
