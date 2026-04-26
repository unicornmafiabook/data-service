"""Integration tests for the investors HTTP routes.

Each test goes through a real ``TestClient`` and the SQLite ``session``
fixture so routing, dependency overrides, JSON serialisation, and
exception mapping are exercised end-to-end. Setup data is created via
``InvestorsService.create`` — never raw ``session.add`` — so the tests
go through the same write path the routes use.
"""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.investors.schemas import VC, InvestmentStage, InvestorCreate, VCStatus
from app.investors.service import InvestorsService


def _make_investor_create(
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


def _payload_dict(
    *,
    canonical_name: str = "Acme Ventures",
    slug: str = "acme-ventures",
    external_vc_id: int | None = 1,
) -> dict[str, object]:
    payload = _make_investor_create(
        canonical_name=canonical_name,
        slug=slug,
        external_vc_id=external_vc_id,
    )
    return payload.model_dump(mode="json")


def _seed_investor(
    session: Session,
    *,
    canonical_name: str = "Acme Ventures",
    slug: str = "acme-ventures",
    external_vc_id: int | None = 1,
) -> VC:
    payload = _make_investor_create(
        canonical_name=canonical_name,
        slug=slug,
        external_vc_id=external_vc_id,
    )
    service = InvestorsService(session)
    return service.create(payload)


def _seed_three_investors(session: Session) -> None:
    service = InvestorsService(session)
    service.create(_make_investor_create(canonical_name="Acme A", slug="acme-a", external_vc_id=1))
    service.create(_make_investor_create(canonical_name="Acme B", slug="acme-b", external_vc_id=2))
    service.create(_make_investor_create(canonical_name="Acme C", slug="acme-c", external_vc_id=3))


# ── POST /investors/create ────────────────────────────────────────────────────

def test_post_investors_creates_and_returns_vc(client: TestClient) -> None:
    # Arrange
    payload = _payload_dict()

    # Act
    response = client.post("/investors/create", json=payload)

    # Assert
    assert response.status_code == 201
    assert response.json()["name"] == "Acme Ventures"
    assert response.json()["slug"] == "acme-ventures"


# ── GET /investors/search ─────────────────────────────────────────────────────

def test_get_investors_lists_paginated_returns_array(
    client: TestClient, session: Session,
) -> None:
    # Arrange
    _seed_three_investors(session)

    # Act
    response = client.get("/investors/search", params={"limit": 2, "offset": 0})

    # Assert
    assert response.status_code == 200
    assert len(response.json()) == 2


# ── GET /investors/by-id/{investor_id} ────────────────────────────────────────

def test_get_investors_by_id_returns_matching_vc(
    client: TestClient, session: Session,
) -> None:
    # Arrange
    seeded = _seed_investor(session)

    # Act
    response = client.get(f"/investors/by-id/{seeded.id}")

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == seeded.id


def test_get_investors_by_id_returns_404_when_missing(client: TestClient) -> None:
    # Arrange
    missing_id = uuid4()

    # Act
    response = client.get(f"/investors/by-id/{missing_id}")

    # Assert
    assert response.status_code == 404


# ── GET /investors/by-external/{external_vc_id} ───────────────────────────────

def test_get_investors_by_external_vc_id_returns_matching_vc(
    client: TestClient, session: Session,
) -> None:
    # Arrange
    _seed_investor(session, external_vc_id=42)

    # Act
    response = client.get("/investors/by-external/42")

    # Assert
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Ventures"


def test_get_investors_by_external_vc_id_returns_404_when_missing(
    client: TestClient,
) -> None:
    # Arrange
    unknown_external_vc_id = 999_999

    # Act
    response = client.get(f"/investors/by-external/{unknown_external_vc_id}")

    # Assert
    assert response.status_code == 404


# ── GET /investors/by-slug-v2/{slug} ──────────────────────────────────────────

def test_get_investors_by_slug_returns_enrichment_snapshot(
    client: TestClient, session: Session,
) -> None:
    # Arrange
    _seed_investor(session, slug="acme-ventures")

    # Act
    response = client.get("/investors/by-slug-v2/acme-ventures")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["investor"]["canonical_name"]
    assert body["members"] == [] and body["funds"] == [] and body["portfolio"] == []


def test_get_investors_by_slug_returns_404_when_missing(client: TestClient) -> None:
    # Arrange
    unknown_slug = "does-not-exist"

    # Act
    response = client.get(f"/investors/by-slug-v2/{unknown_slug}")

    # Assert
    assert response.status_code == 404
