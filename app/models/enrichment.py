from datetime import datetime
from enum import Enum

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


# ── Top-level enrichment payload ──────────────────────────────────────────────

class EnrichedVC(BaseModel):
    vc:          VC
    members:     list[VCMember]
    portfolio:   list[PortfolioCompany]
    enriched_at: datetime
