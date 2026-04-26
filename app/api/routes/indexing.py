from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.indexing.retrieval_indexer import index_investor_for_retrieval

router = APIRouter(prefix="/indexing", tags=["indexing"])


@router.post("/investor/{investor_id}/rebuild")
def rebuild_investor_index(investor_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    result = index_investor_for_retrieval(db, investor_id)
    db.commit()
    return result


@router.post("/rebuild-all")
def rebuild_all_indexes(db: Session = Depends(get_db)) -> dict[str, object]:
    investor_ids = _completed_investor_ids(db)
    results = [index_investor_for_retrieval(db, investor_id) for investor_id in investor_ids]
    db.commit()
    return {"count": len(results), "results": results}


def _completed_investor_ids(db: Session) -> list[str]:
    rows = db.execute(text("""
        SELECT id
        FROM investors
        WHERE enrichment_status = 'completed'
        ORDER BY canonical_name
    """)).mappings().all()
    return [str(row["id"]) for row in rows]
