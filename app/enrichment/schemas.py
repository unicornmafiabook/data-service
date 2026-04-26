"""Enriched API DTOs for the enrichment context.

These shapes carry the full agent-derived data on top of the base VC
contract owned by ``app.investors.schemas``. The ``DeepEnrichedVC``
hierarchy mirrors the agent pipeline output; the ``Enrichment*``
hierarchy is the response shape for ``GET /enrichment/vc/{external_vc_id}``.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.investors.schemas import (
    InvestmentStage,
    PortfolioCompany as BasePortfolioCompany,
    VC as BaseVC,
    VCMember as BaseVCMember,
    VCStatus,
)


# ── Re-exports so the enrichment context is self-sufficient ──────────────────

__all__ = [
    "BranchTrace",
    "DeepEnrichedVC",
    "EnrichedPortfolioCompany",
    "EnrichedVC",
    "EnrichedVCMember",
    "EnrichedVCProfile",
    "EnrichmentFund",
    "EnrichmentInvestorSummary",
    "EnrichmentMember",
    "EnrichmentPortcoTeamMember",
    "EnrichmentPortfolioCompany",
    "EnrichmentSnapshot",
    "FundRecord",
    "InvestmentStage",
    "InvestmentTendency",
    "PortcoStatus",
    "PortcoTeamMember",
    "RevealedThesis",
    "SourceInfo",
    "TicketSize",
    "VC",
    "VCFund",
    "VCIdentity",
    "VCMember",
    "VCPreferences",
    "VCStatus",
]


# Re-bind the base shapes so callers can import them from this module
# during the migration.
VC = BaseVC
VCMember = BaseVCMember
PortfolioCompany = BasePortfolioCompany


# ── Enums local to enrichment ────────────────────────────────────────────────

class InvestmentTendency(str, Enum):
    LEAD = "lead"
    FOLLOW_ON = "follow_on"
    UNSURE = "unsure"


class PortcoStatus(str, Enum):
    ACTIVE = "active"
    EXITED = "exited"


# ── Enriched VC team / fund / portco shapes ──────────────────────────────────

class VCFund(BaseModel):
    fund_name: str | None = None
    fund_size: float | None = None
    fund_size_raw: str | None = None
    vintage_year: int | None = None


class PortcoTeamMember(BaseModel):
    name: str
    position: str | None = None
    description: str | None = None
    linkedin: str | None = None
    email: str | None = None


class EnrichedVCMember(BaseModel):
    name: str
    position: str | None = None
    area_of_expertise: str | None = None
    description: str | None = None
    linkedin: str | None = None
    email: str | None = None
    joined_at: str | None = None
    source: "SourceInfo | None" = None


class EnrichedPortfolioCompany(BaseModel):
    name: str
    overview: str | None = None
    investment_stage: str | None = None
    sectors: list[str] = []
    status: str | None = None
    hq: str | None = None
    founded_in: int | None = None
    company_size: str | None = None
    valuation: str | None = None
    website_url: str | None = None
    executives: list[Any] = []
    source: "SourceInfo | None" = None


class EnrichedVC(BaseVC):
    """Base ``VC`` plus enrichment-derived fields."""

    short_description: str | None = None
    long_description: str | None = None
    stated_thesis: str | None = None
    revealed_thesis: str | None = None
    sectors: list[str] = []
    ticket_size_min: float | None = None
    ticket_size_max: float | None = None
    tendency: InvestmentTendency | None = None
    year_founded: int | None = None
    funds: list[VCFund] = []
    geo_focus: list[str] = []


# ── Agent pipeline output (DeepEnrichedVC family) ────────────────────────────

class SourceInfo(BaseModel):
    url: str | None = None
    source_type: str | None = None
    extracted_at: datetime | None = None


class TicketSize(BaseModel):
    minimum_usd: float | None = None
    maximum_usd: float | None = None
    currency: str | None = None


class FundRecord(BaseModel):
    name: str | None = None
    size_usd: float | None = None
    vintage_year: int | None = None


class VCIdentity(BaseModel):
    short_description: str | None = None
    long_description: str | None = None
    stated_thesis: str | None = None
    year_founded: int | None = None
    hq: str | None = None
    website_url: str | None = None


class VCPreferences(BaseModel):
    stages: list[str] = []
    sectors: list[str] = []
    ticket_size: TicketSize | None = None
    tendency: str | None = None
    geo_focus: list[str] = []
    funds: list[FundRecord] = []


class EnrichedVCProfile(BaseModel):
    identity: VCIdentity | None = None
    preferences: VCPreferences | None = None
    source: SourceInfo | None = None


class RevealedThesis(BaseModel):
    summary: str | None = None
    inferred_sectors: list[str] = []
    inferred_stages: list[str] = []
    inferred_geo_focus: list[str] = []
    source: SourceInfo | None = None


class BranchTrace(BaseModel):
    target_label: str | None = None
    primary_url: str | None = None
    fallback_used: bool = False
    fallback_query: str | None = None
    selected_source: SourceInfo | None = None


class DeepEnrichedVC(BaseModel):
    vc: BaseVC
    profile: EnrichedVCProfile | None = None
    team: list[EnrichedVCMember] = []
    portfolio: list[EnrichedPortfolioCompany] = []
    revealed_thesis: RevealedThesis | None = None
    enriched_at: datetime
    depth: str | None = None
    branch_traces: list[BranchTrace] = []


# ── GET /enrichment/vc/{external_vc_id} response shape ───────────────────────
#
# These are intentionally permissive — they mirror exactly what the
# legacy raw-SQL endpoint returned so existing clients don't break.

class EnrichmentInvestorSummary(BaseModel):
    id: UUID
    canonical_name: str
    slug: str
    website_url: str | None = None
    enrichment_status: str | None = None
    last_enriched_at: datetime | None = None


class EnrichmentMember(BaseModel):
    name: str
    position: str | None = None
    expertise: list[str] = []
    description: str | None = None
    linkedin: str | None = None
    email: str | None = None
    joined_at: date | None = None


class EnrichmentFund(BaseModel):
    fund_name: str | None = None
    fund_size: float | None = None
    fund_size_raw: str | None = None
    vintage_year: int | None = None


class EnrichmentPortcoTeamMember(BaseModel):
    name: str | None = None
    position: str | None = None
    linkedin: str | None = None
    email: str | None = None


class EnrichmentPortfolioCompany(BaseModel):
    name: str
    overview: str | None = None
    sectors: list[str] = []
    stages: list[str] = []
    status: str | None = None
    hq: str | None = None
    founded_year: int | None = None
    company_size: str | None = None
    valuation_usd: str | None = None
    website_url: str | None = None
    investment_date: str | None = None
    team: list[EnrichmentPortcoTeamMember] = []


class EnrichmentSnapshot(BaseModel):
    investor: EnrichmentInvestorSummary
    enriched_at: datetime | None = None
    members: list[EnrichmentMember] = []
    funds: list[EnrichmentFund] = []
    portfolio: list[EnrichmentPortfolioCompany] = []


EnrichedVCMember.model_rebuild()
EnrichedPortfolioCompany.model_rebuild()
