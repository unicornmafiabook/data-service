"""Unit tests for ``EnrichmentService``.

Covers the service's three public methods:

- ``get_snapshot`` (read): not-found, empty, seeded, team-list-shape
- ``create_enrichment`` (write): happy path, investor-missing,
  conflict-when-already-exists
- ``update_enrichment`` (write): happy path, investor-missing,
  not-found-when-no-existing-record

Tests follow the AAA pattern. Investor rows are created via
``InvestorsService.create``; for the read tests, enrichment-owned
tables are seeded with direct ``session.add`` (documented testing-unit
exception). For the write tests, seeding goes through
``EnrichmentService.create_enrichment`` once it is implemented.
"""

from datetime import datetime

import pytest
from sqlmodel import Session

from app.enrichment.models import (
    PortcoTeamMember,
    PortfolioCompany,
    VCFund,
    VCMember,
)
from app.enrichment.schemas import (
    DeepEnrichedVC,
    EnrichedPortfolioCompany,
    EnrichedVCMember,
    EnrichmentSnapshot,
    VC,
)
from app.enrichment.service import (
    EnrichmentAlreadyExistsError,
    EnrichmentNotFoundError,
    EnrichmentService,
    InvestorNotFoundError,
)
from app.investors.schemas import InvestorCreate
from app.investors.service import InvestorsService


# ── get_snapshot — not-found branch ───────────────────────────────────────────

def test_enrichment_service_get_snapshot_raises_when_investor_missing(
    session: Session,
) -> None:
    # Arrange
    missing_external_vc_id = 999_999
    service = EnrichmentService(session)

    # Act / Assert
    with pytest.raises(InvestorNotFoundError):
        service.get_snapshot(missing_external_vc_id)


# ── get_snapshot — empty case ─────────────────────────────────────────────────

def test_enrichment_service_get_snapshot_returns_investor_summary_when_no_enrichment_yet(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 5
    _create_investor(session, external_vc_id=external_vc_id)

    # Act
    snapshot = EnrichmentService(session).get_snapshot(external_vc_id)

    # Assert
    assert snapshot.enriched_at is None
    assert snapshot.members == [] and snapshot.funds == [] and snapshot.portfolio == []


# ── get_snapshot — seeded case ────────────────────────────────────────────────

def test_enrichment_service_get_snapshot_returns_seeded_members_funds_and_portfolio(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 6
    _seed_enriched_vc(session, external_vc_id=external_vc_id)

    # Act
    snapshot = EnrichmentService(session).get_snapshot(external_vc_id)

    # Assert
    counts = (len(snapshot.members), len(snapshot.funds), len(snapshot.portfolio))
    assert all(count >= 1 for count in counts)


# ── get_snapshot — portfolio team list shape ──────────────────────────────────

def test_enrichment_service_get_snapshot_returns_team_as_list_when_portco_has_no_team_rows(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 7
    _seed_portco_without_team(session, external_vc_id=external_vc_id)

    # Act
    snapshot = EnrichmentService(session).get_snapshot(external_vc_id)

    # Assert
    first_company = snapshot.portfolio[0]
    assert first_company.team == []


def test_enrichment_service_get_snapshot_returns_team_as_list_of_dicts_when_team_rows_exist(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 8
    _seed_enriched_vc(session, external_vc_id=external_vc_id)

    # Act
    snapshot = EnrichmentService(session).get_snapshot(external_vc_id)

    # Assert
    expected_keys = {"name", "position", "linkedin", "email"}
    assert expected_keys <= _first_team_member_keys(snapshot)


# ── helpers ───────────────────────────────────────────────────────────────────

def _create_investor(session: Session, *, external_vc_id: int) -> None:
    service = InvestorsService(session)
    payload = InvestorCreate(
        canonical_name=f"VC {external_vc_id}",
        slug=f"vc-{external_vc_id}",
        website_url=f"https://vc-{external_vc_id}.com",
        external_vc_id=external_vc_id,
    )
    service.create(payload)


def _seed_enriched_vc(session: Session, *, external_vc_id: int) -> None:
    _create_investor(session, external_vc_id=external_vc_id)
    portfolio_company = _add_portfolio_company(session, external_vc_id=external_vc_id)
    session.add(VCMember(vc_id=external_vc_id, name="Alice", position="Partner"))
    session.add(VCFund(vc_id=external_vc_id, fund_name="Fund I", fund_size=100.0))
    _add_team_member(session, portfolio_company=portfolio_company)


def _seed_portco_without_team(session: Session, *, external_vc_id: int) -> None:
    _create_investor(session, external_vc_id=external_vc_id)
    _add_portfolio_company(session, external_vc_id=external_vc_id)


def _add_portfolio_company(
    session: Session, *, external_vc_id: int
) -> PortfolioCompany:
    portfolio_company = PortfolioCompany(vc_id=external_vc_id, name="Portco")
    session.add(portfolio_company)
    session.commit()
    return portfolio_company


def _add_team_member(
    session: Session, *, portfolio_company: PortfolioCompany
) -> None:
    member = PortcoTeamMember(portfolio_company_id=portfolio_company.id, name="Bob")
    session.add(member)
    session.commit()


def _first_team_member_keys(snapshot: EnrichmentSnapshot) -> set[str]:
    first_company = snapshot.portfolio[0]
    first_team_member = first_company.team[0]
    member_dump = first_team_member.model_dump()
    return set(member_dump.keys())


# ── create_enrichment ─────────────────────────────────────────────────────────

def test_enrichment_service_create_enrichment_persists_records(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 100
    _create_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)

    # Act
    snapshot = EnrichmentService(session).create_enrichment(external_vc_id, payload)

    # Assert
    assert snapshot.enriched_at is not None
    assert len(snapshot.members) == 1


def test_enrichment_service_create_enrichment_raises_when_investor_missing(
    session: Session,
) -> None:
    # Arrange
    missing_external_vc_id = 999_999
    payload = _make_payload(external_vc_id=missing_external_vc_id)

    # Act / Assert
    with pytest.raises(InvestorNotFoundError):
        EnrichmentService(session).create_enrichment(missing_external_vc_id, payload)


def test_enrichment_service_create_enrichment_raises_when_already_exists(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 101
    service = _setup_existing_enrichment(session, external_vc_id=external_vc_id)
    duplicate_payload = _make_payload(external_vc_id=external_vc_id)

    # Act / Assert
    with pytest.raises(EnrichmentAlreadyExistsError):
        service.create_enrichment(external_vc_id, duplicate_payload)


# ── update_enrichment ─────────────────────────────────────────────────────────

def test_enrichment_service_update_enrichment_replaces_records(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 102
    service = _setup_existing_enrichment(session, external_vc_id=external_vc_id)
    updated_payload = _make_payload_with_two_members(external_vc_id=external_vc_id)

    # Act
    snapshot = service.update_enrichment(external_vc_id, updated_payload)

    # Assert
    assert len(snapshot.members) == 2


def test_enrichment_service_update_enrichment_raises_when_investor_missing(
    session: Session,
) -> None:
    # Arrange
    missing_external_vc_id = 999_999
    payload = _make_payload(external_vc_id=missing_external_vc_id)

    # Act / Assert
    with pytest.raises(InvestorNotFoundError):
        EnrichmentService(session).update_enrichment(missing_external_vc_id, payload)


def test_enrichment_service_update_enrichment_raises_when_no_existing_record(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 103
    _create_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)

    # Act / Assert
    with pytest.raises(EnrichmentNotFoundError):
        EnrichmentService(session).update_enrichment(external_vc_id, payload)


# ── write-path helpers ────────────────────────────────────────────────────────

def _make_payload(*, external_vc_id: int) -> DeepEnrichedVC:
    return DeepEnrichedVC(
        vc=_make_base_vc(external_vc_id=external_vc_id),
        team=[EnrichedVCMember(name="Alice", position="Partner")],
        portfolio=[EnrichedPortfolioCompany(name="Acme Co", sectors=["fintech"])],
        enriched_at=datetime(2026, 4, 26, 12, 0, 0),
    )


def _make_payload_with_two_members(*, external_vc_id: int) -> DeepEnrichedVC:
    base = _make_payload(external_vc_id=external_vc_id)
    base.team = [
        EnrichedVCMember(name="Alice", position="Partner"),
        EnrichedVCMember(name="Bob", position="Principal"),
    ]
    return base


def _make_base_vc(*, external_vc_id: int) -> VC:
    return VC(
        id=str(external_vc_id),
        name=f"VC {external_vc_id}",
        website_url=f"https://vc-{external_vc_id}.com",
        slug=f"vc-{external_vc_id}",
    )


def _setup_existing_enrichment(
    session: Session, *, external_vc_id: int
) -> EnrichmentService:
    _create_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)
    service = EnrichmentService(session)
    service.create_enrichment(external_vc_id, payload)
    return service


# ── complete_enrichment (upsert) ──────────────────────────────────────────────

def test_enrichment_service_complete_enrichment_creates_when_no_record_exists(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 200
    _create_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)

    # Act
    snapshot = EnrichmentService(session).complete_enrichment(external_vc_id, payload)

    # Assert
    assert snapshot.enriched_at is not None
    assert len(snapshot.members) == 1


def test_enrichment_service_complete_enrichment_updates_when_record_exists(
    session: Session,
) -> None:
    # Arrange
    external_vc_id = 201
    service = _setup_existing_enrichment(session, external_vc_id=external_vc_id)
    updated_payload = _make_payload_with_two_members(external_vc_id=external_vc_id)

    # Act
    snapshot = service.complete_enrichment(external_vc_id, updated_payload)

    # Assert
    assert len(snapshot.members) == 2


def test_enrichment_service_complete_enrichment_raises_when_investor_missing(
    session: Session,
) -> None:
    # Arrange
    missing_external_vc_id = 999_998
    payload = _make_payload(external_vc_id=missing_external_vc_id)

    # Act / Assert
    with pytest.raises(InvestorNotFoundError):
        EnrichmentService(session).complete_enrichment(missing_external_vc_id, payload)
