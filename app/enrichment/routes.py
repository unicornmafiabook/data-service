"""HTTP routes for the enrichment context.

Skeleton: route signatures only. Bodies are filled in the GREEN phase.
"""

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


@router.get("/vc/{external_vc_id}", response_model=EnrichmentSnapshot)
def get_enrichment(
    external_vc_id: int,
    db: Session = Depends(get_db),
) -> EnrichmentSnapshot:
    """Return the full enrichment snapshot for the given VC."""
    service = EnrichmentService(db)
    try:
        return service.get_snapshot(external_vc_id)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/vc/{external_vc_id}/create",
    response_model=EnrichmentSnapshot,
    status_code=201,
)
def create_enrichment(
    external_vc_id: int,
    payload: DeepEnrichedVC,
    db: Session = Depends(get_db),
) -> EnrichmentSnapshot:
    """Insert enrichment data for a VC and return the resulting snapshot."""
    service = EnrichmentService(db)
    try:
        return service.create_enrichment(external_vc_id, payload)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except EnrichmentAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put(
    "/vc/{external_vc_id}",
    response_model=EnrichmentSnapshot,
)
def update_enrichment(
    external_vc_id: int,
    payload: DeepEnrichedVC,
    db: Session = Depends(get_db),
) -> EnrichmentSnapshot:
    """Replace enrichment data for a VC and return the resulting snapshot."""
    service = EnrichmentService(db)
    try:
        return service.update_enrichment(external_vc_id, payload)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except EnrichmentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
