"""Base (CSV-importable) API DTOs for the investors context.

These shapes are the public contract for browsing investors. The
enrichment context extends them in ``app.enrichment.schemas`` with
agent-derived fields.
"""

from enum import Enum

from pydantic import BaseModel


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
