from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.matching import (
    FounderMatchRequest,
    FounderMatchResponse,
    VCExplanationRequest,
    VCExplanationResponse,
)
from app.services.matching.matching_service import explain_vc_for_founder, rank_vcs_for_founder

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post("/rank", response_model=FounderMatchResponse)
def rank_vcs(payload: FounderMatchRequest, db: Session = Depends(get_db)) -> FounderMatchResponse:
    return rank_vcs_for_founder(db, payload)


@router.post("/explain-vc", response_model=VCExplanationResponse)
def explain_vc(payload: VCExplanationRequest, db: Session = Depends(get_db)) -> VCExplanationResponse:
    try:
        return explain_vc_for_founder(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
