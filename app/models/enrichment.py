from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class InvestmentStage(str, Enum):
    PRE_SEED  = "Pre-Seed"
    SEED      = "Seed"
    SERIES_A  = "Series A"
    SERIES_B  = "Series B"
    SERIES_C  = "Series C"
    GROWTH    = "Growth"
    LATE_STAGE = "Late Stage"


class VCStatus(str, Enum):
    ACTIVE   = "Active"
    INACTIVE = "Inactive"


class InvestmentTendency(str, Enum):
    LEAD      = "lead"
    FOLLOW_ON = "follow_on"
    UNSURE    = "unsure"


class PortcoStatus(str, Enum):
    ACTIVE = "active"
    EXITED = "exited"


# ── VC fund ───────────────────────────────────────────────────────────────────

class VCFund(BaseModel):
    fund_name:    str | None = None
    fund_size:    float | None = None
    fund_size_raw: str | None = None
    vintage_year: int | None = None


# ── VC team member ────────────────────────────────────────────────────────────

class VCMember(BaseModel):
    name:        str
    position:    str
    expertise:   list[str] = []
    description: str | None = None  # reasoning about investment focus
    linkedin:    str | None = None
    email:       str | None = None
    joined_at:   str | None = None  # ISO date string


# ── Portfolio company ─────────────────────────────────────────────────────────

class PortcoTeamMember(BaseModel):
    name:        str
    position:    str | None = None
    description: str | None = None
    linkedin:    str | None = None
    email:       str | None = None


class PortfolioCompany(BaseModel):
    name:             str
    overview:         str | None = None
    sectors:          list[str] = []
    stages:           list[InvestmentStage] = []
    status:           PortcoStatus | None = None
    hq:               str | None = None
    founded_year:     int | None = None
    company_size:     str | None = None
    valuation_usd:    str | None = None
    website_url:      str | None = None
    investment_date:  str | None = None
    team:             list[PortcoTeamMember] = []


# ── VC ────────────────────────────────────────────────────────────────────────

class VC(BaseModel):
    id:                int
    name:              str
    short_description: str | None = None
    long_description:  str | None = None   # research / deep notes
    stated_thesis:     str | None = None
    revealed_thesis:   str | None = None   # derived after portco scraping
    rounds:            list[InvestmentStage] = []
    sectors:           list[str] = []
    ticket_size_min:   float | None = None
    ticket_size_max:   float | None = None
    tendency:          InvestmentTendency | None = None
    year_founded:      int | None = None
    funds:             list[VCFund] = []
    location:          str | None = None
    geo_focus:         list[str] = []      # could be ["agnostic"]
    website_url:       str
    status:            VCStatus | None = None
    slug:              str


# ── Top-level enrichment payload (legacy) ─────────────────────────────────────

class EnrichedVC(BaseModel):
    vc:          VC
    members:     list[VCMember]
    portfolio:   list[PortfolioCompany]
    enriched_at: datetime


# ── DeepEnrichedVC — agent pipeline output ────────────────────────────────────

class SourceInfo(BaseModel):
    url:          str | None = None
    source_type:  str | None = None
    extracted_at: datetime | None = None


class TicketSize(BaseModel):
    minimum_usd: float | None = None
    maximum_usd: float | None = None
    currency:    str | None = None


class FundRecord(BaseModel):
    name:        str | None = None
    size_usd:    float | None = None
    vintage_year: int | None = None


class VCIdentity(BaseModel):
    short_description: str | None = None
    long_description:  str | None = None
    stated_thesis:     str | None = None
    year_founded:      int | None = None
    hq:                str | None = None
    website_url:       str | None = None


class VCPreferences(BaseModel):
    stages:      list[str] = []
    sectors:     list[str] = []
    ticket_size: TicketSize | None = None
    tendency:    str | None = None
    geo_focus:   list[str] = []
    funds:       list[FundRecord] = []


class EnrichedVCProfile(BaseModel):
    identity:    VCIdentity | None = None
    preferences: VCPreferences | None = None
    source:      SourceInfo | None = None


class EnrichedVCMember(BaseModel):
    name:              str
    position:          str | None = None
    area_of_expertise: str | None = None
    description:       str | None = None
    linkedin:          str | None = None
    email:             str | None = None
    joined_at:         str | None = None
    source:            SourceInfo | None = None


class EnrichedPortfolioCompany(BaseModel):
    name:             str
    overview:         str | None = None
    investment_stage: str | None = None
    sectors:          list[str] = []
    status:           str | None = None
    hq:               str | None = None
    founded_in:       int | None = None
    company_size:     str | None = None
    valuation:        str | None = None
    website_url:      str | None = None
    executives:       list[Any] = []
    source:           SourceInfo | None = None


class RevealedThesis(BaseModel):
    summary:            str | None = None
    inferred_sectors:   list[str] = []
    inferred_stages:    list[str] = []
    inferred_geo_focus: list[str] = []
    source:             SourceInfo | None = None


class BranchTrace(BaseModel):
    target_label:    str | None = None
    primary_url:     str | None = None
    fallback_used:   bool = False
    fallback_query:  str | None = None
    selected_source: SourceInfo | None = None


class DeepEnrichedVC(BaseModel):
    vc:              VC
    profile:         EnrichedVCProfile | None = None
    team:            list[EnrichedVCMember] = []
    portfolio:       list[EnrichedPortfolioCompany] = []
    revealed_thesis: RevealedThesis | None = None
    enriched_at:     datetime
    depth:           str | None = None
    branch_traces:   list[BranchTrace] = []
