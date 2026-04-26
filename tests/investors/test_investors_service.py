"""Unit tests for ``InvestorsService``.

Covers the public surface declared by the skeleton:
- ``create``
- ``get_by_id`` (+ not-found branch)
- ``get_by_external_vc_id`` (+ not-found branch)
- ``get_by_slug`` (+ not-found branch)
- ``list_paginated``

Tests follow the AAA pattern. Setup data is created via
``InvestorsService.create`` so we never bypass service-level validation
with raw ``session.add`` calls.
"""

from uuid import UUID, uuid4

import pytest
from sqlmodel import Session

from app.investors.schemas import VC, InvestmentStage, InvestorCreate, VCStatus
from app.investors.service import (
    InvestorNotFoundError,
    InvestorsService,
)


def _make_payload(
    *,
    canonical_name: str = "Acme Ventures",
    slug: str = "acme-ventures",
    external_vc_id: int | None = 1,
) -> InvestorCreate:
    return InvestorCreate(
        canonical_name=canonical_name,
        slug=slug,
        website_url="https://acmevc.com",
        external_vc_id=external_vc_id,
        location="London, United Kingdom",
        sector="fintech",
        rounds=[InvestmentStage.SEED, InvestmentStage.SERIES_A],
        status=VCStatus.ACTIVE,
    )


# ── create ────────────────────────────────────────────────────────────────────

def test_investors_service_create_returns_vc_with_persisted_id(
    session: Session,
) -> None:
    # Arrange
    service = InvestorsService(session)

    # Act
    created = service.create(_make_payload())

    # Assert
    assert isinstance(created, VC)
    assert created.name == "Acme Ventures"
    assert created.slug == "acme-ventures"
    assert UUID(created.id)


def test_investors_service_create_persists_round_list_through_typedecorator(
    session: Session,
) -> None:
    # Arrange
    service = InvestorsService(session)

    # Act
    created = service.create(_make_payload())
    fetched = service.get_by_id(UUID(created.id))

    # Assert
    assert fetched.rounds == [InvestmentStage.SEED, InvestmentStage.SERIES_A]


# ── get_by_id ─────────────────────────────────────────────────────────────────

def test_investors_service_get_by_id_returns_matching_investor(
    session: Session,
) -> None:
    # Arrange
    service = InvestorsService(session)
    created = service.create(_make_payload())

    # Act
    fetched = service.get_by_id(UUID(created.id))

    # Assert
    assert fetched.id == created.id
    assert fetched.name == "Acme Ventures"


def test_investors_service_get_by_id_raises_when_missing(
    session: Session,
) -> None:
    # Arrange
    service = InvestorsService(session)
    missing_id = uuid4()

    # Act / Assert
    with pytest.raises(InvestorNotFoundError):
        service.get_by_id(missing_id)


# ── get_by_external_vc_id ─────────────────────────────────────────────────────

def test_investors_service_get_by_external_vc_id_returns_matching_investor(
    session: Session,
) -> None:
    # Arrange
    service = InvestorsService(session)
    service.create(_make_payload(external_vc_id=42))

    # Act
    fetched = service.get_by_external_vc_id(42)

    # Assert
    assert fetched.name == "Acme Ventures"


def test_investors_service_get_by_external_vc_id_raises_when_missing(
    session: Session,
) -> None:
    # Arrange
    service = InvestorsService(session)
    unknown_external_vc_id = 999_999

    # Act / Assert
    with pytest.raises(InvestorNotFoundError):
        service.get_by_external_vc_id(unknown_external_vc_id)


# ── get_by_slug ───────────────────────────────────────────────────────────────

def test_investors_service_get_by_slug_returns_matching_investor(
    session: Session,
) -> None:
    # Arrange
    service = InvestorsService(session)
    service.create(_make_payload(slug="acme-ventures"))

    # Act
    fetched = service.get_by_slug("acme-ventures")

    # Assert
    assert fetched.slug == "acme-ventures"


def test_investors_service_get_by_slug_raises_when_missing(
    session: Session,
) -> None:
    # Arrange
    service = InvestorsService(session)

    # Act / Assert
    with pytest.raises(InvestorNotFoundError):
        service.get_by_slug("does-not-exist")


# ── list_paginated ────────────────────────────────────────────────────────────

def test_investors_service_list_paginated_returns_requested_slice(
    session: Session,
) -> None:
    # Arrange
    service = _seed_three_investors(session)

    # Act
    page = service.list_paginated(limit=2, offset=0)

    # Assert
    assert len(page) == 2
    assert all(isinstance(record, VC) for record in page)


def test_investors_service_list_paginated_returns_empty_when_offset_beyond_rows(
    session: Session,
) -> None:
    # Arrange
    service = _seed_three_investors(session)

    # Act
    page = service.list_paginated(limit=10, offset=99)

    # Assert
    assert page == []


def _seed_three_investors(session: Session) -> InvestorsService:
    service = InvestorsService(session)
    service.create(_make_payload(canonical_name="Acme A", slug="acme-a", external_vc_id=1))
    service.create(_make_payload(canonical_name="Acme B", slug="acme-b", external_vc_id=2))
    service.create(_make_payload(canonical_name="Acme C", slug="acme-c", external_vc_id=3))
    return service
