"""HTTP routes for the investors context.

Thin wrappers over ``InvestorsService``: each handler instantiates the
service with a session from ``Depends(get_db)``, delegates, and maps
``InvestorNotFoundError`` to ``HTTPException(404)``.

``GET /investors/search`` returns the slim ``InvestorSummary`` rows the
data table renders. ``GET /investors/{investor_id}`` returns the full
``InvestorDetail`` shape — both contracts mirror the frontend types.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.db.session import get_db
from app.investors.schemas import (
    VC,
    InvestorCreate,
    InvestorDetail,
    InvestorSearchBody,
    InvestorSummary,
)
from app.investors.service import (
    InvestorNotFoundError,
    InvestorsService,
)

router = APIRouter(prefix="/investors", tags=["investors"])


@router.post("/create", response_model=VC, status_code=201)
def create_investor(
    payload: InvestorCreate,
    db: Session = Depends(get_db),
) -> VC:
    """Create a new investor and return the persisted ``VC`` schema."""
    service = InvestorsService(db)
    return service.create(payload)


@router.get("/search", response_model=list[InvestorSummary])
def search_investors(
    params: Annotated[InvestorSearchBody, Query()],
    db: Session = Depends(get_db),
) -> list[InvestorSummary]:
    """Return a paginated slice of investors as ``InvestorSummary`` rows.

    All ``InvestorSearchBody`` fields bind from the query string. List
    filters (``stages``, ``sectors``, ``geographies``) accept repeated
    values, e.g. ``?stages=seed&stages=series_a``.
    """
    service = InvestorsService(db)
    return service.list_summaries(params)


@router.get("/by-external/{external_vc_id}", response_model=VC)
def get_investor_by_external_vc_id(
    external_vc_id: int,
    db: Session = Depends(get_db),
) -> VC:
    """Return the investor with the given legacy external VC id."""
    service = InvestorsService(db)
    try:
        return service.get_by_external_vc_id(external_vc_id)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/by-slug-v2/{slug}", response_model=VC)
def get_investor_by_slug(
    slug: str,
    db: Session = Depends(get_db),
) -> VC:
    """Return the investor with the given slug."""
    service = InvestorsService(db)
    try:
        return service.get_by_slug(slug)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{investor_id}", response_model=InvestorDetail)
def get_investor_detail_by_id(
    investor_id: UUID,
    db: Session = Depends(get_db),
) -> InvestorDetail:
    """Return the full ``InvestorDetail`` shape for a given UUID id."""
    service = InvestorsService(db)
    try:
        return service.get_detail_by_id(investor_id)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
