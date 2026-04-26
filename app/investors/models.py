"""SQLModel for the ``investors`` table — base (CSV-imported) columns only.

Keep this slim. The base shape mirrors the public ``VC`` API contract
in ``app.investors.schemas``: identity, location, sector, rounds,
status, slug, website. We also carry the queue metadata
(``enrichment_status``, ``last_enriched_at``, ``needs_review``) because
the enrichment context joins on it via ``external_vc_id``.

Everything else physically on the ``investors`` table in production —
CSV provenance (``description``, ``investment_thesis``,
``first_cheque_*``, ``source_names``, ``dedupe_*``, ``raw_combined``,
``funds_raw_json``, …) and enrichment-managed columns
(``short_description``, ``long_description``, ``stated_thesis``,
``revealed_thesis``, ``ticket_size_*``, ``investment_tendency``,
``year_founded``, ``geo_focus``, …) — is **not** mapped here. The
legacy raw-SQL routes continue to read/write those columns directly.
A second SQLModel (``InvestorEnrichmentColumns`` mapped via
``extend_existing=True``) will join the enrichment-managed subset to
this table when slice 2 ports ``POST /complete`` to the new layer.
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
    canonical_name: str
    slug: str | None = None
    website_url: str | None = None
    location: str | None = None
    sector: str | None = None
    rounds: list[str] = Field(default_factory=list, sa_type=TextArray)
    status: str | None = None
    enrichment_status: str = "not_started"
    last_enriched_at: datetime | None = None
    needs_review: bool = False
