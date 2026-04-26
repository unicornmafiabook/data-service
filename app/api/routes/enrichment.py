"""Legacy enrichment routes — only the queue + stats endpoints remain.

``GET /vc/{vc_id}`` and ``POST /vc/{vc_id}/complete`` were moved to
``app.enrichment.routes`` (slice 1 + 2 of the migration). The two
queue endpoints below still use raw SQL against Postgres-specific
features (``FOR UPDATE SKIP LOCKED`` etc.) and will migrate later.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.enrichment.schemas import VC, VCStatus

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


_STAGE_TO_ENUM = {
    "pre_seed": "Pre-Seed",
    "seed":     "Seed",
    "series_a": "Series A",
    "series_b": "Series B",
    "series_c": "Series C",
    "growth":   "Growth",
}

_STATUS_MAP = {
    "active":   VCStatus.ACTIVE,
    "inactive": VCStatus.INACTIVE,
}


def _map_status(raw: str | None) -> VCStatus | None:
    if not raw:
        return None
    return _STATUS_MAP.get(raw.lower())


def _row_to_vc(row, funds: list) -> dict:
    rounds = list(row["rounds"] or [])
    if not rounds:
        rounds = [_STAGE_TO_ENUM[s] for s in (row["stages"] or []) if s in _STAGE_TO_ENUM]

    return {
        "id":                str(row["external_vc_id"]),
        "name":              row["canonical_name"],
        "short_description": row["short_description"],
        "long_description":  row["long_description"],
        "stated_thesis":     row["stated_thesis"] or row["investment_thesis"],
        "revealed_thesis":   row["revealed_thesis"],
        "rounds":            rounds,
        "sectors":           list(row["sectors"] or []),
        "ticket_size_min":   row["ticket_size_min"] or row["first_cheque_min"],
        "ticket_size_max":   row["ticket_size_max"] or row["first_cheque_max"],
        "tendency":          row["investment_tendency"],
        "year_founded":      row["year_founded"],
        "funds":             [dict(f) for f in funds],
        "location":          row["location"],
        "geo_focus":         list(row["geo_focus"] or row["geographies"] or []),
        "website_url":       row["website_url"] or row["website"] or "",
        "status":            _map_status(row["status"]),
        "slug":              row["slug"] or "",
    }


@router.get("/next-vc", response_model=VC)
def get_next_vc(db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT external_vc_id, canonical_name,
               stages, rounds, sectors, geographies, geo_focus,
               short_description, long_description,
               investment_thesis, stated_thesis, revealed_thesis,
               investment_tendency, year_founded,
               ticket_size_min, ticket_size_max,
               first_cheque_min, first_cheque_max,
               location, website_url, website, status, slug
        FROM investors
        WHERE enrichment_status IN ('not_started', 'pending')
          AND external_vc_id IS NOT NULL
        ORDER BY
            CASE enrichment_status WHEN 'pending' THEN 0 ELSE 1 END,
            created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    """)).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No investors pending enrichment")

    funds = db.execute(text("""
        SELECT fund_name, fund_size, fund_size_raw, vintage_year
        FROM vc_funds WHERE vc_id = :vc_id
        ORDER BY vintage_year NULLS LAST
    """), {"vc_id": row["external_vc_id"]}).mappings().all()

    return _row_to_vc(row, list(funds))


@router.get("/stats")
def enrichment_stats(db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE enrichment_status = 'not_started') AS not_started,
            COUNT(*) FILTER (WHERE enrichment_status = 'pending')     AS pending,
            COUNT(*) FILTER (WHERE enrichment_status = 'completed')   AS completed,
            COUNT(*)                                                   AS total
        FROM investors
    """)).mappings().first()
    if not row:
        return {}
    return dict(row)
