from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.import_service import import_vc_data

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/run")
def run_ingest(dry_run: bool = Query(True), reset: bool = Query(False), db: Session = Depends(get_db)):
    # Hackathon-only endpoint. Protect/remove this in production.
    return import_vc_data(db=db, dry_run=dry_run, reset=reset)
