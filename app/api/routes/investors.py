from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.investor_search import search_investors

router = APIRouter(prefix="/investors", tags=["investors"])


@router.get("")
def list_investors(limit: int = Query(50, le=200), offset: int = 0, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, canonical_name, website, domain, stages, sectors, geographies,
               first_cheque_min, first_cheque_max, source_count, needs_review
        FROM investors
        ORDER BY canonical_name
        LIMIT :limit OFFSET :offset;
    """), {"limit": limit, "offset": offset}).mappings().all()
    return {"count": len(rows), "results": [dict(row) for row in rows]}


@router.get("/search")
def search(stage: str | None = None, sector: str | None = None, geography: str | None = None,
           cheque_max: float | None = None, q: str | None = None,
           limit: int = Query(50, le=200), offset: int = 0, db: Session = Depends(get_db)):
    results = search_investors(db, stage, sector, geography, cheque_max, q, limit, offset)
    return {"count": len(results), "results": results}


@router.get("/{investor_id}")
def get_investor(investor_id: str, db: Session = Depends(get_db)):
    investor = db.execute(text("SELECT * FROM investors WHERE id = :investor_id;"), {"investor_id": investor_id}).mappings().first()
    if not investor:
        return {"error": "Investor not found"}
    sources = db.execute(text("""
        SELECT source_name, source_row_id, raw_data
        FROM investor_sources
        WHERE investor_id = :investor_id
        ORDER BY source_name;
    """), {"investor_id": investor_id}).mappings().all()
    return {"investor": dict(investor), "sources": [dict(row) for row in sources]}


@router.get("/{investor_id}/portfolio")
def get_portfolio(investor_id: str, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT c.id, c.canonical_name, c.website, c.domain, c.sector, c.sub_sector, c.description,
               r.relationship_type, r.investment_stage, r.investment_round, r.investment_date,
               r.confidence_score, r.source
        FROM investor_company_relationships r
        JOIN companies c ON c.id = r.company_id
        WHERE r.investor_id = :investor_id
        ORDER BY c.canonical_name;
    """), {"investor_id": investor_id}).mappings().all()
    return {"count": len(rows), "results": [dict(row) for row in rows]}


@router.post("/{investor_id}/mark-for-enrichment")
def mark_for_enrichment(investor_id: str, db: Session = Depends(get_db)):
    db.execute(text("""
        UPDATE investors
        SET enrichment_status = 'pending'
        WHERE id = :investor_id;
    """), {"investor_id": investor_id})
    db.commit()
    return {"status": "pending", "investor_id": investor_id}
