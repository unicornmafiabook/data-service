"""SQLModel for the ``investors`` table.

Carries every column the public API surfaces on ``/investors/search``
(``Investor``) and ``/investors/{id}`` (``InvestorDetail``). Fields are
grouped by concern: identity, websites, type/status/queue, location,
stage/sector/geo, descriptions/thesis, financials, and
provenance/dedupe. Enum-shaped fields (``status``, ``enrichment_status``,
``investment_tendency``) stay as ``str`` on the table and are validated
at the schema boundary in ``app.investors.schemas``.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.db.timestamps import TimestampedModel
from app.db.types import TextArray


class Investor(TimestampedModel, table=True):
    """One row per canonical VC firm in the database."""

    __tablename__ = "investors"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    external_vc_id: int | None = Field(default=None, unique=True, index=True)

    # Identity
    canonical_name: str
    slug: str = Field(unique=True, index=True)

    # Websites / domain
    website: str | None = None
    website_url: str | None = None
    domain: str | None = None

    # Type / status / enrichment queue
    investor_type: str | None = None
    status: str | None = None
    enrichment_status: str = "not_started"
    last_enriched_at: datetime | None = None
    needs_review: bool = False

    # Location
    hq_city: str | None = None
    hq_country: str | None = None
    location: str | None = None

    # Stage / sector / geography
    stages: list[str] = Field(default_factory=list, sa_type=TextArray)
    rounds: list[str] = Field(default_factory=list, sa_type=TextArray)
    sector: str | None = None
    sectors: list[str] = Field(default_factory=list, sa_type=TextArray)
    geographies: list[str] = Field(default_factory=list, sa_type=TextArray)
    geo_focus: list[str] = Field(default_factory=list, sa_type=TextArray)

    # Descriptions / thesis
    description: str | None = None
    short_description: str | None = None
    long_description: str | None = None
    investment_thesis: str | None = None
    stated_thesis: str | None = None
    revealed_thesis: str | None = None
    investment_tendency: str | None = None
    year_founded: int | None = None

    # Financials
    first_cheque_min: float | None = None
    first_cheque_max: float | None = None
    first_cheque_currency: str | None = None
    ticket_size_min: float | None = None
    ticket_size_max: float | None = None

    # Provenance / dedupe
    source_count: int = 1
    source_names: list[str] = Field(default_factory=list, sa_type=TextArray)
    dedupe_confidence: float | None = None
