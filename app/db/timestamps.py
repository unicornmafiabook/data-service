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

We use ``sa_column_kwargs`` rather than a pre-built ``sa_column=Column(...)``
so SQLModel's metaclass constructs a fresh ``Column`` for each subclass
— without this, every table inheriting the mixin would share one
``Column`` instance and SQLAlchemy raises
``ArgumentError: Column already assigned to Table``.
"""

from datetime import datetime

from sqlalchemy import DateTime, text
from sqlmodel import Field, SQLModel

class TimestampedModel(SQLModel):
    """Combined mixin for tables carrying both timestamps."""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        nullable=False,
        sa_type=DateTime,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        nullable=False,
        sa_type=DateTime,
        sa_column_kwargs={
            "server_default": text("CURRENT_TIMESTAMP"),
            "onupdate": text("CURRENT_TIMESTAMP"),
        },
    )