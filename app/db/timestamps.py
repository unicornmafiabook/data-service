"""
Timestamp mixins for SQLModel tables.

Two universal columns are factored out here so individual tables don't
re-declare them. Production tables are managed by the
``set_updated_at()`` trigger defined in ``sql/schema.sql``; the
``onupdate`` hook below mirrors that behaviour for SQLite tests.

Tables choose the variant matching their on-disk schema:

- ``CreatedAtMixin`` — tables that only have ``created_at`` (most child
  tables in the enrichment context).
- ``UpdatedAtMixin`` — rarely used alone; usually combined with
  ``CreatedAtMixin``.
- ``TimestampedModel`` — convenience base that combines both. Used by
  tables whose prod schema carries both columns (e.g. ``investors``,
  ``vc_enrichments``).
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class CreatedAtMixin(SQLModel):
    """Adds a ``created_at`` column with a DB-side default of NOW()."""

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=False),
            server_default=func.now(),
            nullable=True,
        ),
    )


class UpdatedAtMixin(SQLModel):
    """Adds an ``updated_at`` column that auto-bumps on every UPDATE."""

    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=False),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=True,
        ),
    )


class TimestampedModel(CreatedAtMixin, UpdatedAtMixin):
    """Combined mixin for tables carrying both timestamps."""
