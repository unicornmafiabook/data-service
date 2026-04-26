"""HTTP routes for the enrichment context.

Skeleton: route signatures only. Bodies are filled in the GREEN phase.
"""

from venv import logger

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_db
from app.enrichment.schemas import DeepEnrichedVC, EnrichmentSnapshot
from app.enrichment.service import (
    EnrichmentAlreadyExistsError,
    EnrichmentNotFoundError,
    EnrichmentService,
    InvestorNotFoundError,
)

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


@router.get("/vc/by-slug/{slug}", response_model=EnrichmentSnapshot)
def get_enrichment(
    slug: str,
    db: Session = Depends(get_db),
) -> EnrichmentSnapshot:
    """Return the full enrichment snapshot for the investor with the given slug."""
    service = EnrichmentService(db)
    try:
        return service.get_snapshot(slug)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/vc/by-slug/{slug}/create",
    response_model=EnrichmentSnapshot,
    status_code=201,
)
def create_enrichment(
    slug: str,
    payload: DeepEnrichedVC,
    db: Session = Depends(get_db),
) -> EnrichmentSnapshot:
    """Insert enrichment data for a VC and return the resulting snapshot."""
    service = EnrichmentService(db)
    try:
        return service.create_enrichment(slug, payload)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except EnrichmentAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put(
    "/vc/by-slug/{slug}",
    response_model=EnrichmentSnapshot,
)
def update_enrichment(
    slug: str,
    payload: DeepEnrichedVC,
    db: Session = Depends(get_db),
) -> EnrichmentSnapshot:
    """Replace enrichment data for a VC and return the resulting snapshot."""
    service = EnrichmentService(db)
    try:
        return service.update_enrichment(slug, payload)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except EnrichmentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/vc/by-slug/{slug}/complete",
    response_model=EnrichmentSnapshot,
)
def complete_enrichment(
    slug: str,
    payload: DeepEnrichedVC,
    db: Session = Depends(get_db),
) -> EnrichmentSnapshot:
    """Upsert enrichment data — create if missing, replace if present."""
    service = EnrichmentService(db)
    try:
        return service.complete_enrichment(slug, payload)
    except InvestorNotFoundError as error:
        logger.error(f"Investor not found for slug={slug}: {error}")
        raise HTTPException(status_code=404, detail=str(error)) from error
