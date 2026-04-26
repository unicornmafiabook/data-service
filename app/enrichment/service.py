"""Service layer for the enrichment context.

``EnrichmentService`` is instantiated with a SQLModel ``Session`` and
exposes the read + write operations the routes call:

- ``get_snapshot`` — read a VC's current enrichment snapshot.
- ``create_enrichment`` — insert enrichment data; raises if one exists.
- ``update_enrichment`` — replace enrichment data; raises if missing.
- ``complete_enrichment`` — upsert (update if exists, else create).

The class body stays minimal; row IO and DTO conversion live as
module-level helpers below.
"""

from collections import defaultdict
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlmodel import Session, col, select

from app.enrichment.models import (
    PortcoTeamMember,
    PortfolioCompany,
    VCEnrichment,
    VCFund,
    VCMember,
)
from app.enrichment.schemas import (
    DeepEnrichedVC,
    EnrichedPortfolioCompany,
    EnrichedVCMember,
    EnrichmentFund,
    EnrichmentInvestorSummary,
    EnrichmentMember,
    EnrichmentPortcoTeamMember,
    EnrichmentPortfolioCompany,
    EnrichmentSnapshot,
    FundRecord,
)
from app.investors.models import Investor


class InvestorNotFoundError(Exception):
    """Raised when no investor matches the requested external VC id."""


class EnrichmentAlreadyExistsError(Exception):
    """Raised when ``create_enrichment`` would conflict with an existing row."""


class EnrichmentNotFoundError(Exception):
    """Raised when ``update_enrichment`` finds no existing record to replace."""


class EnrichmentService:
    """Read and write operations over the enrichment-owned tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_snapshot(self, external_vc_id: int) -> EnrichmentSnapshot:
        investor = _require_investor(self._session, external_vc_id)
        return _build_snapshot(self._session, investor, external_vc_id)

    def create_enrichment(
        self, external_vc_id: int, payload: DeepEnrichedVC,
    ) -> EnrichmentSnapshot:
        _require_investor(self._session, external_vc_id)
        _reject_existing_enrichment(self._session, external_vc_id)
        _write_enrichment(self._session, external_vc_id, payload)
        return self.get_snapshot(external_vc_id)

    def update_enrichment(
        self, external_vc_id: int, payload: DeepEnrichedVC,
    ) -> EnrichmentSnapshot:
        _require_investor(self._session, external_vc_id)
        _require_existing_enrichment(self._session, external_vc_id)
        _delete_children(self._session, external_vc_id)
        _write_enrichment(self._session, external_vc_id, payload)
        return self.get_snapshot(external_vc_id)

    def complete_enrichment(
        self, external_vc_id: int, payload: DeepEnrichedVC,
    ) -> EnrichmentSnapshot:
        if _enrichment_exists(self._session, external_vc_id):
            return self.update_enrichment(external_vc_id, payload)
        return self.create_enrichment(external_vc_id, payload)


# ── lookups ───────────────────────────────────────────────────────────────────

def _require_investor(session: Session, external_vc_id: int) -> Investor:
    investor = _fetch_investor(session, external_vc_id)
    if investor is None:
        raise InvestorNotFoundError(
            f"No investor with external_vc_id={external_vc_id}"
        )
    return investor


def _fetch_investor(session: Session, external_vc_id: int) -> Investor | None:
    statement = select(Investor).where(Investor.external_vc_id == external_vc_id)
    return session.exec(statement).first()


def _enrichment_exists(session: Session, external_vc_id: int) -> bool:
    return _fetch_enrichment(session, external_vc_id) is not None


def _fetch_enrichment(session: Session, external_vc_id: int) -> VCEnrichment | None:
    statement = select(VCEnrichment).where(VCEnrichment.vc_id == external_vc_id)
    return session.exec(statement).first()


def _reject_existing_enrichment(session: Session, external_vc_id: int) -> None:
    if _enrichment_exists(session, external_vc_id):
        raise EnrichmentAlreadyExistsError(
            f"Enrichment for external_vc_id={external_vc_id} already exists"
        )


def _require_existing_enrichment(session: Session, external_vc_id: int) -> None:
    if not _enrichment_exists(session, external_vc_id):
        raise EnrichmentNotFoundError(
            f"No enrichment record for external_vc_id={external_vc_id}"
        )


# ── snapshot building ─────────────────────────────────────────────────────────

def _build_snapshot(
    session: Session, investor: Investor, external_vc_id: int,
) -> EnrichmentSnapshot:
    members = _fetch_members(session, external_vc_id)
    funds = _fetch_funds(session, external_vc_id)
    portfolio = _fetch_portfolio_with_team(session, external_vc_id)
    enrichment = _fetch_enrichment(session, external_vc_id)
    return EnrichmentSnapshot(
        investor=_investor_summary(investor),
        enriched_at=enrichment.enriched_at if enrichment else None,
        members=members,
        funds=funds,
        portfolio=portfolio,
    )


def _investor_summary(investor: Investor) -> EnrichmentInvestorSummary:
    return EnrichmentInvestorSummary(
        id=investor.id,
        canonical_name=investor.canonical_name,
        enrichment_status=investor.enrichment_status,
        last_enriched_at=investor.last_enriched_at,
    )


def _fetch_members(session: Session, external_vc_id: int) -> list[EnrichmentMember]:
    statement = (
        select(VCMember)
        .where(VCMember.vc_id == external_vc_id)
        .order_by(VCMember.name)
    )
    rows = session.exec(statement).all()
    return [_member_dto(row) for row in rows]


def _member_dto(row: VCMember) -> EnrichmentMember:
    return EnrichmentMember(
        name=row.name,
        position=row.position,
        expertise=list(row.expertise or []),
        description=row.description,
        linkedin=row.linkedin,
        email=row.email,
        joined_at=row.joined_at,
    )


def _fetch_funds(session: Session, external_vc_id: int) -> list[EnrichmentFund]:
    statement = (
        select(VCFund)
        .where(VCFund.vc_id == external_vc_id)
        .order_by(col(VCFund.vintage_year))
    )
    rows = session.exec(statement).all()
    return [_fund_dto(row) for row in rows]


def _fund_dto(row: VCFund) -> EnrichmentFund:
    return EnrichmentFund(
        fund_name=row.fund_name,
        fund_size=row.fund_size,
        fund_size_raw=row.fund_size_raw,
        vintage_year=row.vintage_year,
    )


def _fetch_portfolio_with_team(
    session: Session, external_vc_id: int,
) -> list[EnrichmentPortfolioCompany]:
    portcos = _fetch_portcos(session, external_vc_id)
    portco_ids = [portco.id for portco in portcos]
    teams = _fetch_teams_grouped(session, portco_ids)
    return [_portfolio_dto(portco, teams[portco.id]) for portco in portcos]


def _fetch_portcos(session: Session, external_vc_id: int) -> list[PortfolioCompany]:
    statement = (
        select(PortfolioCompany)
        .where(PortfolioCompany.vc_id == external_vc_id)
        .order_by(PortfolioCompany.name)
    )
    return list(session.exec(statement).all())


def _fetch_teams_grouped(
    session: Session, portco_ids: list[UUID],
) -> dict[UUID, list[PortcoTeamMember]]:
    grouped: dict[UUID, list[PortcoTeamMember]] = defaultdict(list)
    if not portco_ids:
        return grouped
    statement = select(PortcoTeamMember).where(
        col(PortcoTeamMember.portfolio_company_id).in_(portco_ids)
    )
    for row in session.exec(statement).all():
        grouped[row.portfolio_company_id].append(row)
    return grouped


def _portfolio_dto(
    portco: PortfolioCompany, team_rows: list[PortcoTeamMember],
) -> EnrichmentPortfolioCompany:
    return EnrichmentPortfolioCompany(
        name=portco.name,
        overview=portco.overview,
        sectors=list(portco.sectors or []),
        stages=list(portco.stage or []),
        status=portco.status,
        hq=portco.hq,
        founded_year=portco.founded_year,
        company_size=portco.company_size,
        valuation_usd=portco.valuation_usd,
        website_url=portco.website_url,
        investment_date=portco.investment_date,
        team=[_team_dto(row) for row in team_rows],
    )


def _team_dto(row: PortcoTeamMember) -> EnrichmentPortcoTeamMember:
    return EnrichmentPortcoTeamMember(
        name=row.name,
        position=row.position,
        linkedin=row.linkedin,
        email=row.email,
    )


# ── writes ────────────────────────────────────────────────────────────────────

def _write_enrichment(
    session: Session, external_vc_id: int, payload: DeepEnrichedVC,
) -> None:
    _write_members(session, external_vc_id, payload.team)
    _write_funds(session, external_vc_id, _funds_from_payload(payload))
    _write_portfolio(session, external_vc_id, payload.portfolio)
    _upsert_enrichment_row(session, external_vc_id, payload)
    session.commit()


def _funds_from_payload(payload: DeepEnrichedVC) -> list[FundRecord]:
    if not payload.profile or not payload.profile.preferences:
        return []
    return list(payload.profile.preferences.funds)


def _write_members(
    session: Session, external_vc_id: int, members: Iterable[EnrichedVCMember],
) -> None:
    for member in members:
        session.add(_member_row(external_vc_id, member))


def _member_row(external_vc_id: int, member: EnrichedVCMember) -> VCMember:
    expertise = [member.area_of_expertise] if member.area_of_expertise else []
    return VCMember(
        vc_id=external_vc_id,
        name=member.name,
        position=member.position,
        expertise=expertise,
        description=member.description,
        linkedin=member.linkedin,
        email=member.email,
    )


def _write_funds(
    session: Session, external_vc_id: int, funds: Iterable[FundRecord],
) -> None:
    for fund in funds:
        session.add(_fund_row(external_vc_id, fund))


def _fund_row(external_vc_id: int, fund: FundRecord) -> VCFund:
    return VCFund(
        vc_id=external_vc_id,
        fund_name=fund.name,
        fund_size=fund.size_usd,
        vintage_year=fund.vintage_year,
    )


def _write_portfolio(
    session: Session,
    external_vc_id: int,
    companies: Iterable[EnrichedPortfolioCompany],
) -> None:
    for company in companies:
        portco = _portfolio_row(external_vc_id, company)
        session.add(portco)
        session.flush()
        _write_team(session, portco.id, company.executives)


def _portfolio_row(
    external_vc_id: int, company: EnrichedPortfolioCompany,
) -> PortfolioCompany:
    stage = [company.investment_stage] if company.investment_stage else []
    return PortfolioCompany(
        vc_id=external_vc_id,
        name=company.name,
        sectors=list(company.sectors),
        stage=stage,
        status=company.status,
        hq=company.hq,
        founded_year=company.founded_in,
        company_size=company.company_size,
        valuation_usd=company.valuation,
        website_url=company.website_url,
    )


def _write_team(
    session: Session, portfolio_company_id: UUID, executives: Iterable[Any],
) -> None:
    for executive in executives:
        session.add(_team_row(portfolio_company_id, executive))


def _team_row(portfolio_company_id: UUID, executive: Any) -> PortcoTeamMember:
    data = _executive_dict(executive)
    return PortcoTeamMember(
        portfolio_company_id=portfolio_company_id,
        name=data.get("name", ""),
        position=data.get("position"),
        description=data.get("description"),
        linkedin=data.get("linkedin"),
        email=data.get("email"),
    )


def _executive_dict(executive: Any) -> dict[str, Any]:
    if isinstance(executive, dict):
        return executive
    if hasattr(executive, "model_dump"):
        return executive.model_dump()
    return {}


def _upsert_enrichment_row(
    session: Session, external_vc_id: int, payload: DeepEnrichedVC,
) -> None:
    existing = _fetch_enrichment(session, external_vc_id)
    if existing:
        _update_enrichment_row(existing, payload)
        session.add(existing)
        return
    session.add(_new_enrichment_row(external_vc_id, payload))


def _update_enrichment_row(row: VCEnrichment, payload: DeepEnrichedVC) -> None:
    row.enriched_at = payload.enriched_at
    row.raw_payload = payload.model_dump(mode="json")
    row.depth = payload.depth
    row.branch_traces = [trace.model_dump(mode="json") for trace in payload.branch_traces]


def _new_enrichment_row(
    external_vc_id: int, payload: DeepEnrichedVC,
) -> VCEnrichment:
    return VCEnrichment(
        vc_id=external_vc_id,
        enriched_at=payload.enriched_at,
        raw_payload=payload.model_dump(mode="json"),
        depth=payload.depth,
        branch_traces=[trace.model_dump(mode="json") for trace in payload.branch_traces],
    )


# ── deletes ───────────────────────────────────────────────────────────────────

def _delete_children(session: Session, external_vc_id: int) -> None:
    _delete_members(session, external_vc_id)
    _delete_funds(session, external_vc_id)
    _delete_portfolio(session, external_vc_id)
    session.flush()


def _delete_members(session: Session, external_vc_id: int) -> None:
    statement = select(VCMember).where(VCMember.vc_id == external_vc_id)
    for row in session.exec(statement).all():
        session.delete(row)


def _delete_funds(session: Session, external_vc_id: int) -> None:
    statement = select(VCFund).where(VCFund.vc_id == external_vc_id)
    for row in session.exec(statement).all():
        session.delete(row)


def _delete_portfolio(session: Session, external_vc_id: int) -> None:
    statement = select(PortfolioCompany).where(PortfolioCompany.vc_id == external_vc_id)
    for portco in session.exec(statement).all():
        _delete_portco_team(session, portco.id)
        session.delete(portco)


def _delete_portco_team(session: Session, portfolio_company_id: UUID) -> None:
    statement = select(PortcoTeamMember).where(
        PortcoTeamMember.portfolio_company_id == portfolio_company_id
    )
    for row in session.exec(statement).all():
        session.delete(row)
