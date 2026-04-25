import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enrichment import EnrichedVC, VC, VCStatus

router = APIRouter(prefix="/enrichment", tags=["enrichment"])

# Maps internal stage keys to InvestmentStage enum values
_STAGE_TO_ENUM = {
    "pre_seed": "Pre-Seed",
    "seed": "Seed",
    "series_a": "Series A",
    "series_b": "Series B",
    "series_c": "Series C",
    "growth": "Growth",
}

_STATUS_MAP = {
    "active": VCStatus.ACTIVE,
    "inactive": VCStatus.INACTIVE,
}


def _map_status(raw: str | None) -> VCStatus | None:
    if not raw:
        return None
    return _STATUS_MAP.get(raw.lower())


def _row_to_vc(row) -> dict:
    # Prefer pre-computed rounds column; fall back to deriving from stages
    rounds = list(row["rounds"] or [])
    if not rounds:
        rounds = [_STAGE_TO_ENUM[s] for s in (row["stages"] or []) if s in _STAGE_TO_ENUM]
    return {
        "id": row["external_vc_id"],
        "name": row["canonical_name"],
        "rounds": rounds,
        "location": row["location"],
        "sector": row["sector"],
        "website_url": row["website_url"] or row["website"] or "",
        "status": _map_status(row["status"]),
        "slug": row["slug"] or "",
    }


@router.get("/next-vc", response_model=VC)
def get_next_vc(db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT external_vc_id, canonical_name, stages, rounds,
               location, sector, website_url, website, status, slug
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
    return _row_to_vc(row)


@router.post("/vc/{vc_id}/complete")
def complete_enrichment(vc_id: int, payload: EnrichedVC, db: Session = Depends(get_db)):
    investor = db.execute(text("""
        SELECT id FROM investors WHERE external_vc_id = :vc_id
    """), {"vc_id": vc_id}).mappings().first()
    if not investor:
        raise HTTPException(status_code=404, detail=f"No investor with vc_id={vc_id}")
    investor_uuid = investor["id"]

    vc = payload.vc
    rounds = [r.value for r in vc.rounds]

    # Update canonical investor row
    db.execute(text("""
        UPDATE investors SET
            canonical_name      = :name,
            rounds              = :rounds,
            location            = :location,
            sector              = :sector,
            website_url         = :website_url,
            status              = :status,
            slug                = :slug,
            enrichment_status   = 'completed',
            last_enriched_at    = NOW()
        WHERE external_vc_id = :vc_id
    """), {
        "vc_id":       vc_id,
        "name":        vc.name,
        "rounds":      rounds,
        "location":    vc.location,
        "sector":      vc.sector,
        "website_url": str(vc.website_url),
        "status":      vc.status.value if vc.status else None,
        "slug":        vc.slug,
    })

    # Replace vc_members
    db.execute(text("DELETE FROM vc_members WHERE vc_id = :vc_id"), {"vc_id": vc_id})
    for member in payload.members:
        db.execute(text("""
            INSERT INTO vc_members (vc_id, name, role) VALUES (:vc_id, :name, :role)
        """), {"vc_id": vc_id, "name": member.name, "role": member.role})

    # Replace portfolio_companies
    db.execute(text("DELETE FROM portfolio_companies WHERE vc_id = :vc_id"), {"vc_id": vc_id})
    for company in payload.portfolio:
        db.execute(text("""
            INSERT INTO portfolio_companies (vc_id, name, sector, stage, investment_date, valuation_usd)
            VALUES (:vc_id, :name, :sector, :stage, :investment_date, :valuation_usd)
        """), {
            "vc_id":           vc_id,
            "name":            company.name,
            "sector":          company.sector,
            "stage":           company.stage.value if company.stage else None,
            "investment_date": company.investment_date,
            "valuation_usd":   company.valuation_usd,
        })

    # Upsert vc_enrichments
    db.execute(text("""
        INSERT INTO vc_enrichments (vc_id, enriched_at, raw_payload)
        VALUES (:vc_id, :enriched_at, CAST(:raw_payload AS jsonb))
        ON CONFLICT (vc_id) DO UPDATE SET
            enriched_at = EXCLUDED.enriched_at,
            raw_payload = EXCLUDED.raw_payload,
            updated_at  = NOW()
    """), {
        "vc_id":       vc_id,
        "enriched_at": payload.enriched_at,
        "raw_payload": json.dumps(payload.model_dump(mode="json")),
    })

    # Log to enrichment_runs
    db.execute(text("""
        INSERT INTO enrichment_runs
            (target_type, target_id, status, completed_at, output_json)
        VALUES
            ('investor', :target_id, 'completed', NOW(), CAST(:output_json AS jsonb))
    """), {
        "target_id":   str(investor_uuid),
        "output_json": json.dumps({
            "vc_id":           vc_id,
            "members_count":   len(payload.members),
            "portfolio_count": len(payload.portfolio),
        }),
    })

    db.commit()
    return {
        "status":            "completed",
        "vc_id":             vc_id,
        "members_updated":   len(payload.members),
        "portfolio_updated": len(payload.portfolio),
    }
