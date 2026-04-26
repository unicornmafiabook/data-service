"""HTTP routes for the investors context.

Thin wrappers over ``InvestorsService``: each handler instantiates the
service with a session from ``Depends(get_db)``, delegates, and maps
``InvestorNotFoundError`` to ``HTTPException(404)``. Paths are renamed
relative to the legacy ``app.api.routes.investors`` router so both
routers can coexist under the same ``/investors`` prefix during the
incremental migration.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_db
from app.investors.schemas import VC, InvestorCreate
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


@router.get("/search", response_model=list[VC])
def list_investors(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[VC]:
    """Return a paginated slice of investors as ``VC`` schemas."""
    service = InvestorsService(db)
    return service.list_paginated(limit=limit, offset=offset)


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


@router.get("/by-id/{investor_id}", response_model=VC)
def get_investor_by_id(
    investor_id: UUID,
    db: Session = Depends(get_db),
) -> VC:
    """Return the investor with the given UUID id."""
    service = InvestorsService(db)
    try:
        return service.get_by_id(investor_id)
    except InvestorNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
