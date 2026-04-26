"""Service layer for the enrichment context.

Skeleton: signatures only. Bodies are filled in the GREEN phase.
"""

from sqlmodel import Session

from app.enrichment.schemas import EnrichmentSnapshot


class InvestorNotFoundError(Exception):
    """Raised when no investor matches the requested external VC id."""


def get_enrichment_snapshot(
    db: Session, external_vc_id: int
) -> EnrichmentSnapshot:
    """
    Build the full enrichment snapshot for a VC.

    Parameters
    ----------
    db : Session
        SQLModel session bound to the active engine.
    external_vc_id : int
        Legacy integer VC id used by the frontend and the agent
        pipeline. Maps to ``investors.external_vc_id``.

    Returns
    -------
    EnrichmentSnapshot
        Investor summary plus members, funds, and portfolio companies
        (with their teams nested).

    Raises
    ------
    InvestorNotFoundError
        When no investor has the supplied ``external_vc_id``.
    """
    raise NotImplementedError


def seed_enrichment_for_investor(
    db: Session,
    *,
    external_vc_id: int,
    canonical_name: str,
    enrichment_status: str = "completed",
) -> None:
    """
    Test-helper service: insert a fully-enriched VC fixture.

    Mirrors the row shape that ``POST /enrichment/vc/{id}/complete``
    writes today, so tests exercise the same data the production agent
    pipeline produces.
    """
    raise NotImplementedError
