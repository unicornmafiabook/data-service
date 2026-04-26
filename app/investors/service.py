"""Service layer for the investors context.

``InvestorsService`` is instantiated with a SQLModel ``Session`` and
exposes the CRUD + lookup methods the routes (and other contexts)
call. The service is intentionally thin: SQLModel rows are converted
to the public ``VC`` schema via the module-level ``_vc_from_row``
helper so the class itself stays focused on session orchestration.
"""

from typing import Any
from uuid import UUID

from sqlmodel import Session, select
from sqlmodel.sql.expression import SelectOfScalar

from app.investors.models import Investor
from app.investors.schemas import (
    VC,
    EnrichmentStatus,
    InvestmentStage,
    InvestmentTendency,
    InvestorCreate,
    InvestorDetail,
    InvestorSummary,
    VCStatus,
)


class InvestorNotFoundError(Exception):
    """Raised when no investor matches the given lookup."""


class InvestorAlreadyExistsError(Exception):
    """Raised when ``create`` would conflict with an existing investor."""


def _row_from_payload(payload: InvestorCreate) -> Investor:
    payload_rounds = payload.rounds
    rounds = [stage.value for stage in payload_rounds]
    payload_status = payload.status
    status = _status_text(payload_status)
    return Investor(
        external_vc_id=payload.external_vc_id,
        canonical_name=payload.canonical_name,
        slug=payload.slug,
        website_url=payload.website_url,
        location=payload.location,
        sector=payload.sector,
        rounds=rounds,
        status=status,
    )


def _status_text(status: VCStatus | None) -> str | None:
    if status is None:
        return None
    return status.value


def _vc_from_row(row: Investor) -> VC:
    rounds = [InvestmentStage(value) for value in row.rounds]
    status = _cast_status(row.status)
    return VC(
        id=str(row.id),
        name=row.canonical_name,
        rounds=rounds,
        location=row.location,
        sector=row.sector,
        website_url=row.website_url or "",
        status=status,
        slug=row.slug or "",
    )


def _cast_status(status: str | None) -> VCStatus | None:
    if status is None:
        return None
    return VCStatus(status)


def _cast_enrichment_status(value: str) -> EnrichmentStatus:
    return EnrichmentStatus(value)


def _cast_tendency(value: str | None) -> InvestmentTendency | None:
    if value is None:
        return None
    return InvestmentTendency(value)


def _summary_from_row(row: Investor) -> InvestorSummary:
    return InvestorSummary(
        id=str(row.id),
        canonical_name=row.canonical_name,
        slug=row.slug,
        website=row.website,
        domain=row.domain,
        investor_type=row.investor_type,
        status=row.status,
        hq_city=row.hq_city,
        hq_country=row.hq_country,
        stages=row.stages,
        sectors=row.sectors,
        geographies=row.geographies,
        first_cheque_min=row.first_cheque_min,
        first_cheque_max=row.first_cheque_max,
        first_cheque_currency=row.first_cheque_currency,
        description=row.description,
        investment_thesis=row.investment_thesis,
        source_count=row.source_count,
        dedupe_confidence=row.dedupe_confidence,
        needs_review=row.needs_review,
        enrichment_status=_cast_enrichment_status(row.enrichment_status),
    )


def _detail_from_row(row: Investor) -> InvestorDetail:
    return InvestorDetail(
        id=str(row.id),
        external_vc_id=row.external_vc_id,
        canonical_name=row.canonical_name,
        slug=row.slug,
        website=row.website,
        website_url=row.website_url,
        domain=row.domain,
        investor_type=row.investor_type,
        status=row.status,
        hq_city=row.hq_city,
        hq_country=row.hq_country,
        location=row.location,
        stages=row.stages or None,
        rounds=row.rounds or None,
        sectors=row.sectors or None,
        geographies=row.geographies or None,
        geo_focus=row.geo_focus or None,
        short_description=row.short_description,
        long_description=row.long_description,
        investment_thesis=row.investment_thesis,
        stated_thesis=row.stated_thesis,
        revealed_thesis=row.revealed_thesis,
        investment_tendency=_cast_tendency(row.investment_tendency),
        year_founded=row.year_founded,
        ticket_size_min=row.ticket_size_min,
        ticket_size_max=row.ticket_size_max,
        first_cheque_min=row.first_cheque_min,
        first_cheque_max=row.first_cheque_max,
        first_cheque_currency=row.first_cheque_currency,
        enrichment_status=_cast_enrichment_status(row.enrichment_status),
        source_count=row.source_count,
        source_names=row.source_names,
        needs_review=row.needs_review,
        dedupe_confidence=row.dedupe_confidence,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _page_select(limit: int, offset: int) -> SelectOfScalar[Investor]:
    column = Investor.canonical_name
    statement = select(Investor).order_by(column)
    statement = statement.offset(offset)
    return statement.limit(limit)


class InvestorsService:
    """Read/write operations over the ``investors`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, payload: InvestorCreate) -> VC:
        row = _row_from_payload(payload)
        self._persist(row)
        return _vc_from_row(row)

    def get_by_id(self, investor_id: UUID) -> VC:
        condition = Investor.id == investor_id
        return self._require_one(condition, f"id={investor_id}")

    def get_by_external_vc_id(self, external_vc_id: int) -> VC:
        condition = Investor.external_vc_id == external_vc_id
        return self._require_one(condition, f"external_vc_id={external_vc_id}")

    def get_by_slug(self, slug: str) -> VC:
        condition = Investor.slug == slug
        return self._require_one(condition, f"slug={slug}")

    def list_paginated(self, *, limit: int, offset: int) -> list[VC]:
        rows = self._fetch_page(limit, offset)
        return [_vc_from_row(row) for row in rows]

    def list_summaries(self, *, limit: int, offset: int) -> list[InvestorSummary]:
        rows = self._fetch_page(limit, offset)
        return [_summary_from_row(row) for row in rows]

    def get_detail_by_id(self, investor_id: UUID) -> InvestorDetail:
        condition = Investor.id == investor_id
        row = self._first_matching(condition)
        if row is None:
            raise InvestorNotFoundError(f"No investor with id={investor_id}")
        return _detail_from_row(row)

    def _persist(self, row: Investor) -> None:
        session = self._session
        session.add(row)
        session.commit()
        session.refresh(row)

    def _require_one(self, condition: Any, identifier: str) -> VC:
        row = self._first_matching(condition)
        if row is None:
            raise InvestorNotFoundError(f"No investor with {identifier}")
        return _vc_from_row(row)

    def _first_matching(self, condition: Any) -> Investor | None:
        statement = select(Investor).where(condition)
        session = self._session
        result = session.exec(statement)
        return result.first()

    def _fetch_page(self, limit: int, offset: int) -> list[Investor]:
        statement = _page_select(limit, offset)
        session = self._session
        result = session.exec(statement)
        return list(result.all())
