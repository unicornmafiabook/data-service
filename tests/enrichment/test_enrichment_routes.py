"""Integration tests for the enrichment write endpoints.

Covers ``POST /enrichment/vc/{external_vc_id}/create`` and
``PUT /enrichment/vc/{external_vc_id}``. Tests are RED until the
``EnrichmentService`` write methods are implemented; the route
handlers translate ``NotImplementedError`` into a 500 today, so every
non-500 assertion fails for the right reason.

The legacy enrichment router still owns ``GET /enrichment/vc/{vc_id}``
on the same path, so the new GET handler is intentionally not exercised
here — a separate file covers the snapshot service-level behaviour.
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


# ── POST /enrichment/vc/{external_vc_id}/create ──────────────────────────────

def test_post_enrichment_create_returns_201_with_snapshot(
    client: TestClient, session: Session
) -> None:
    # Arrange
    external_vc_id = 1001
    _seed_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)

    # Act
    response = _post_create(client, external_vc_id=external_vc_id, payload=payload)

    # Assert
    assert response.status_code == 201


def test_post_enrichment_create_returns_404_when_investor_missing(
    client: TestClient,
) -> None:
    # Arrange
    missing_external_vc_id = 999_001
    payload = _make_payload(external_vc_id=missing_external_vc_id)

    # Act
    response = _post_create(client, external_vc_id=missing_external_vc_id, payload=payload)
    detail = response.json()["detail"]

    # Assert
    assert response.status_code == 404
    assert "investor" in detail.lower()


def test_post_enrichment_create_returns_409_when_already_exists(
    client: TestClient, session: Session
) -> None:
    # Arrange
    external_vc_id = 1002
    _seed_existing_enrichment(client, session, external_vc_id=external_vc_id)
    duplicate_payload = _make_payload(external_vc_id=external_vc_id)

    # Act
    response = _post_create(client, external_vc_id=external_vc_id, payload=duplicate_payload)

    # Assert
    assert response.status_code == 409


# ── PUT /enrichment/vc/{external_vc_id} ──────────────────────────────────────

def test_put_enrichment_update_returns_200_with_snapshot(
    client: TestClient, session: Session
) -> None:
    # Arrange
    external_vc_id = 1003
    _seed_existing_enrichment(client, session, external_vc_id=external_vc_id)
    updated_payload = _make_payload(external_vc_id=external_vc_id)

    # Act
    response = _put_update(client, external_vc_id=external_vc_id, payload=updated_payload)

    # Assert
    assert response.status_code == 200


def test_put_enrichment_update_returns_404_when_investor_missing(
    client: TestClient,
) -> None:
    # Arrange
    missing_external_vc_id = 999_002
    payload = _make_payload(external_vc_id=missing_external_vc_id)

    # Act
    response = _put_update(client, external_vc_id=missing_external_vc_id, payload=payload)

    # Assert
    assert response.status_code == 404


def test_put_enrichment_update_returns_404_when_no_existing_record(
    client: TestClient, session: Session
) -> None:
    # Arrange
    external_vc_id = 1004
    _seed_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)

    # Act
    response = _put_update(client, external_vc_id=external_vc_id, payload=payload)

    # Assert
    assert response.status_code == 404


# ── module-level helpers ─────────────────────────────────────────────────────

def _seed_investor(session: Session, *, external_vc_id: int) -> None:
    payload = InvestorCreate(
        canonical_name=f"VC {external_vc_id}",
        slug=f"vc-{external_vc_id}",
        website_url=f"https://vc-{external_vc_id}.com",
        external_vc_id=external_vc_id,
    )
    service = InvestorsService(session)
    service.create(payload)


def _seed_existing_enrichment(
    client: TestClient, session: Session, *, external_vc_id: int
) -> None:
    _seed_investor(session, external_vc_id=external_vc_id)
    payload = _make_payload(external_vc_id=external_vc_id)
    _post_create(client, external_vc_id=external_vc_id, payload=payload)


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
    client: TestClient, *, external_vc_id: int, payload: DeepEnrichedVC
) -> Response:
    body = payload.model_dump(mode="json")
    return client.post(f"/enrichment/vc/{external_vc_id}/create", json=body)


def _put_update(
    client: TestClient, *, external_vc_id: int, payload: DeepEnrichedVC
) -> Response:
    body = payload.model_dump(mode="json")
    return client.put(f"/enrichment/vc/{external_vc_id}", json=body)
