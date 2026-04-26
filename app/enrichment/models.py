"""SQLModel tables owned by the enrichment context.

Six tables, FK-linked to ``investors.external_vc_id`` (legacy bigint id):

- ``vc_members`` — VC team members (one row per partner / GP / etc.)
- ``vc_funds`` — fund history per VC
- ``portfolio_companies`` — investments
- ``portco_team`` — executives at portfolio companies
- ``vc_enrichments`` — agent run metadata + raw payload

Tables that only have ``created_at`` in production inherit
``CreatedAtMixin``; ``vc_enrichments`` carries both timestamps and
inherits ``TimestampedModel``.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.db.timestamps import TimestampedModel
from app.db.types import JsonB, TextArray


class VCMember(TimestampedModel, table=True):
    """Investment team member of a VC."""

    __tablename__ = "vc_members"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    vc_id: int = Field(index=True)
    name: str
    role: str | None = None
    position: str | None = None
    expertise: list[str] = Field(default_factory=list, sa_type=TextArray)
    description: str | None = None
    linkedin: str | None = None
    email: str | None = None
    joined_at: date | None = None


class VCFund(TimestampedModel, table=True):
    """A named fund raised by a VC."""

    __tablename__ = "vc_funds"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    vc_id: int = Field(index=True)
    fund_name: str | None = None
    fund_size: float | None = None
    fund_size_raw: str | None = None
    vintage_year: int | None = None


class PortfolioCompany(TimestampedModel, table=True):
    """A company a VC has invested in."""

    __tablename__ = "portfolio_companies"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    vc_id: int = Field(index=True)
    name: str
    sector: str | None = None
    overview: str | None = None
    sectors: list[str] = Field(default_factory=list, sa_type=TextArray)
    stage: list[str] = Field(default_factory=list, sa_type=TextArray)
    status: str | None = None
    hq: str | None = None
    founded_year: int | None = None
    company_size: str | None = None
    valuation_usd: str | None = None
    website_url: str | None = None
    investment_date: str | None = None


class PortcoTeamMember(TimestampedModel, table=True):
    """An executive at a portfolio company."""

    __tablename__ = "portco_team"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    portfolio_company_id: UUID = Field(foreign_key="portfolio_companies.id", index=True)
    name: str
    position: str | None = None
    description: str | None = None
    linkedin: str | None = None
    email: str | None = None


class VCEnrichment(TimestampedModel, table=True):
    """Per-VC enrichment metadata and raw agent payload."""

    __tablename__ = "vc_enrichments"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    vc_id: int = Field(unique=True, index=True)
    enriched_at: datetime
    raw_payload: dict = Field(default_factory=dict, sa_type=JsonB)
    depth: str | None = None
    branch_traces: list = Field(default_factory=list, sa_type=JsonB)


__all__ = [
    "PortcoTeamMember",
    "PortfolioCompany",
    "VCEnrichment",
    "VCFund",
    "VCMember",
]
