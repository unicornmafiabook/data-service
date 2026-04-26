"""Integration tests for the enrichment write endpoints.

Covers ``POST /enrichment/vc/by-slug/{slug}/create``,
``PUT /enrichment/vc/by-slug/{slug}`` and
``POST /enrichment/vc/by-slug/{slug}/complete``.
"""

from datetime import datetime

from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.enrichment.schemas import (
    VC,
    DeepEnrichedVC,
    EnrichedPortfolioCompany,
    EnrichedVCMember,
)
from app.investors.schemas import InvestorCreate
from app.investors.service import InvestorsService


# ── POST /enrichment/vc/by-slug/{slug}/create ────────────────────────────────

def test_post_enrichment_create_returns_201_with_snapshot(
    client: TestClient, session: Session
) -> None:
    external_vc_id = 1001
    slug = _seed_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)

    response = _post_create(client, slug=slug, payload=payload)

    assert response.status_code == 201


def test_post_enrichment_create_returns_404_when_investor_missing(
    client: TestClient,
) -> None:
    payload = _make_payload(external_vc_id=999_001)

    response = _post_create(client, slug="missing-vc", payload=payload)
    detail = response.json()["detail"]

    assert response.status_code == 404
    assert "investor" in detail.lower()


def test_post_enrichment_create_returns_409_when_already_exists(
    client: TestClient, session: Session
) -> None:
    external_vc_id = 1002
    slug = _seed_existing_enrichment(client, session, external_vc_id=external_vc_id)
    duplicate_payload = _make_payload(external_vc_id=external_vc_id)

    response = _post_create(client, slug=slug, payload=duplicate_payload)

    assert response.status_code == 409


# ── PUT /enrichment/vc/by-slug/{slug} ────────────────────────────────────────

def test_put_enrichment_update_returns_200_with_snapshot(
    client: TestClient, session: Session
) -> None:
    external_vc_id = 1003
    slug = _seed_existing_enrichment(client, session, external_vc_id=external_vc_id)
    updated_payload = _make_payload(external_vc_id=external_vc_id)

    response = _put_update(client, slug=slug, payload=updated_payload)

    assert response.status_code == 200


def test_put_enrichment_update_returns_404_when_investor_missing(
    client: TestClient,
) -> None:
    payload = _make_payload(external_vc_id=999_002)

    response = _put_update(client, slug="missing-vc", payload=payload)

    assert response.status_code == 404


def test_put_enrichment_update_returns_404_when_no_existing_record(
    client: TestClient, session: Session
) -> None:
    external_vc_id = 1004
    slug = _seed_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)

    response = _put_update(client, slug=slug, payload=payload)

    assert response.status_code == 404


# ── POST /enrichment/vc/by-slug/{slug}/complete (upsert) ─────────────────────

def test_post_enrichment_complete_creates_when_no_record_exists(
    client: TestClient, session: Session
) -> None:
    external_vc_id = 1005
    slug = _seed_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)

    response = _post_complete(client, slug=slug, payload=payload)

    assert response.status_code == 200


def test_post_enrichment_complete_updates_when_record_exists(
    client: TestClient, session: Session
) -> None:
    external_vc_id = 1006
    slug = _seed_existing_enrichment(client, session, external_vc_id=external_vc_id)
    second_payload = _make_payload(external_vc_id=external_vc_id)

    response = _post_complete(client, slug=slug, payload=second_payload)

    assert response.status_code == 200


def test_post_enrichment_complete_returns_404_when_investor_missing(
    client: TestClient,
) -> None:
    payload = _make_payload(external_vc_id=999_003)

    response = _post_complete(client, slug="missing-vc", payload=payload)
    detail = response.json()["detail"]

    assert response.status_code == 404
    assert "investor" in detail.lower()


# ── module-level helpers ─────────────────────────────────────────────────────

def _seed_investor(session: Session, *, external_vc_id: int) -> str:
    slug = f"vc-{external_vc_id}"
    payload = InvestorCreate(
        canonical_name=f"VC {external_vc_id}",
        slug=slug,
        website_url=f"https://vc-{external_vc_id}.com",
        external_vc_id=external_vc_id,
    )
    service = InvestorsService(session)
    service.create(payload)
    return slug


def _seed_existing_enrichment(
    client: TestClient, session: Session, *, external_vc_id: int
) -> str:
    slug = _seed_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)
    _post_create(client, slug=slug, payload=payload)
    return slug


def _make_payload(*, external_vc_id: int) -> DeepEnrichedVC:
    return DeepEnrichedVC(
        vc=_make_base_vc(external_vc_id=external_vc_id),
        team=[EnrichedVCMember(name="Alice", position="Partner")],
        portfolio=[EnrichedPortfolioCompany(name="Acme Co", sectors=["fintech"])],
        enriched_at=datetime(2026, 4, 26, 12, 0, 0),
    )


def _make_base_vc(*, external_vc_id: int) -> VC:
    return VC(
        id=str(external_vc_id),
        name=f"VC {external_vc_id}",
        website_url=f"https://vc-{external_vc_id}.com",
        slug=f"vc-{external_vc_id}",
    )


def _post_create(
    client: TestClient, *, slug: str, payload: DeepEnrichedVC
) -> Response:
    body = payload.model_dump(mode="json")
    return client.post(f"/enrichment/vc/by-slug/{slug}/create", json=body)


def _put_update(
    client: TestClient, *, slug: str, payload: DeepEnrichedVC
) -> Response:
    body = payload.model_dump(mode="json")
    return client.put(f"/enrichment/vc/by-slug/{slug}", json=body)


def _post_complete(
    client: TestClient, *, slug: str, payload: DeepEnrichedVC
) -> Response:
    body = payload.model_dump(mode="json")
    return client.post(f"/enrichment/vc/by-slug/{slug}/complete", json=body)
