"""Base (CSV-importable) API DTOs for the investors context.

These shapes are the public contract for browsing investors. The
enrichment context extends them in ``app.enrichment.schemas`` with
agent-derived fields.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class EnrichmentStatus(str, Enum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    COMPLETED = "completed"


class InvestmentTendency(str, Enum):
    LEAD = "lead"
    FOLLOW_ON = "follow_on"
    UNSURE = "unsure"


class InvestmentStage(str, Enum):
    PRE_SEED = "Pre-Seed"
    SEED = "Seed"
    SERIES_A = "Series A"
    SERIES_B = "Series B"
    SERIES_C = "Series C"
    GROWTH = "Growth"
    LATE_STAGE = "Late Stage"


class VCStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class VCMember(BaseModel):
    name: str
    role: str


class PortfolioCompany(BaseModel):
    name: str
    sector: str
    stage: InvestmentStage | None = None
    investment_date: str | None = None
    valuation_usd: str | None = None
    description: str
    url: str | None = None


class VC(BaseModel):
    id: str
    name: str
    rounds: list[InvestmentStage] = []
    location: str | None = None
    sector: str | None = None
    website_url: str
    status: VCStatus | None = None
    slug: str


class InvestorCreate(BaseModel):
    """Request body for creating a new investor."""

    canonical_name: str
    slug: str
    website_url: str
    external_vc_id: int | None = None
    location: str | None = None
    sector: str | None = None
    rounds: list[InvestmentStage] = []
    status: VCStatus | None = None


class InvestorSummary(BaseModel):
    """Slim search-row DTO returned by ``GET /investors/search``.

    Mirrors the frontend ``Investor`` type — the list view the data
    table renders against.
    """

    id: str
    canonical_name: str
    slug: str
    website: str | None = None
    domain: str | None = None
    investor_type: str | None = None
    status: str | None = None
    hq_city: str | None = None
    hq_country: str | None = None
    stages: list[str] = []
    sectors: list[str] = []
    geographies: list[str] = []
    first_cheque_min: float | None = None
    first_cheque_max: float | None = None
    first_cheque_currency: str | None = None
    description: str | None = None
    investment_thesis: str | None = None
    source_count: int
    dedupe_confidence: float | None = None
    needs_review: bool
    enrichment_status: EnrichmentStatus | None = None


class InvestorDetail(BaseModel):
    """Full detail DTO returned by ``GET /investors/{id}``.

    Mirrors the frontend ``InvestorDetail`` type.
    """

    id: str
    external_vc_id: int | None = None
    canonical_name: str
    slug: str
    website: str | None = None
    website_url: str | None = None
    domain: str | None = None
    investor_type: str | None = None
    status: str | None = None
    hq_city: str | None = None
    hq_country: str | None = None
    location: str | None = None
    stages: list[str] | None = None
    rounds: list[str] | None = None
    sectors: list[str] | None = None
    geographies: list[str] | None = None
    geo_focus: list[str] | None = None
    short_description: str | None = None
    long_description: str | None = None
    investment_thesis: str | None = None
    stated_thesis: str | None = None
    revealed_thesis: str | None = None
    investment_tendency: InvestmentTendency | None = None
    year_founded: int | None = None
    ticket_size_min: float | None = None
    ticket_size_max: float | None = None
    first_cheque_min: float | None = None
    first_cheque_max: float | None = None
    first_cheque_currency: str | None = None
    enrichment_status: EnrichmentStatus
    source_count: int
    source_names: list[str] = []
    needs_review: bool
    dedupe_confidence: float | None = None
    created_at: datetime
    updated_at: datetime
