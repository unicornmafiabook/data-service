import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enrichment import EnrichedVC, VC, VCStatus

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
        "id":                row["external_vc_id"],
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


@router.post("/vc/{vc_id}/complete")
def complete_enrichment(vc_id: int, payload: EnrichedVC, db: Session = Depends(get_db)):
    investor = db.execute(text("""
        SELECT id FROM investors WHERE external_vc_id = :vc_id
    """), {"vc_id": vc_id}).mappings().first()
    if not investor:
        raise HTTPException(status_code=404, detail=f"No investor with vc_id={vc_id}")
    investor_uuid = investor["id"]

    vc = payload.vc

    # ── Update investors ──────────────────────────────────────────────────────
    db.execute(text("""
        UPDATE investors SET
            canonical_name       = :name,
            short_description    = :short_description,
            long_description     = :long_description,
            stated_thesis        = :stated_thesis,
            revealed_thesis      = :revealed_thesis,
            rounds               = :rounds,
            sectors              = :sectors,
            ticket_size_min      = :ticket_size_min,
            ticket_size_max      = :ticket_size_max,
            investment_tendency  = :tendency,
            year_founded         = :year_founded,
            geo_focus            = :geo_focus,
            location             = :location,
            website_url          = :website_url,
            status               = :status,
            slug                 = :slug,
            enrichment_status    = 'completed',
            last_enriched_at     = NOW()
        WHERE external_vc_id = :vc_id
    """), {
        "vc_id":             vc_id,
        "name":              vc.name,
        "short_description": vc.short_description,
        "long_description":  vc.long_description,
        "stated_thesis":     vc.stated_thesis,
        "revealed_thesis":   vc.revealed_thesis,
        "rounds":            [r.value for r in vc.rounds],
        "sectors":           vc.sectors,
        "ticket_size_min":   vc.ticket_size_min,
        "ticket_size_max":   vc.ticket_size_max,
        "tendency":          vc.tendency.value if vc.tendency else None,
        "year_founded":      vc.year_founded,
        "geo_focus":         vc.geo_focus,
        "location":          vc.location,
        "website_url":       str(vc.website_url),
        "status":            vc.status.value if vc.status else None,
        "slug":              vc.slug,
    })

    # ── Replace vc_members ────────────────────────────────────────────────────
    db.execute(text("DELETE FROM vc_members WHERE vc_id = :vc_id"), {"vc_id": vc_id})
    for m in payload.members:
        db.execute(text("""
            INSERT INTO vc_members
                (vc_id, name, position, expertise, description, linkedin, email, joined_at)
            VALUES
                (:vc_id, :name, :position, :expertise, :description, :linkedin, :email, :joined_at)
        """), {
            "vc_id":       vc_id,
            "name":        m.name,
            "position":    m.position,
            "expertise":   m.expertise or [],
            "description": m.description,
            "linkedin":    m.linkedin,
            "email":       m.email,
            "joined_at":   m.joined_at,
        })

    # ── Replace vc_funds ──────────────────────────────────────────────────────
    db.execute(text("DELETE FROM vc_funds WHERE vc_id = :vc_id"), {"vc_id": vc_id})
    for f in vc.funds:
        db.execute(text("""
            INSERT INTO vc_funds (vc_id, fund_name, fund_size, fund_size_raw, vintage_year)
            VALUES (:vc_id, :fund_name, :fund_size, :fund_size_raw, :vintage_year)
        """), {
            "vc_id":        vc_id,
            "fund_name":    f.fund_name,
            "fund_size":    f.fund_size,
            "fund_size_raw": f.fund_size_raw,
            "vintage_year": f.vintage_year,
        })

    # ── Replace portfolio_companies (cascade deletes portco_team) ─────────────
    db.execute(text("DELETE FROM portfolio_companies WHERE vc_id = :vc_id"), {"vc_id": vc_id})
    for company in payload.portfolio:
        row = db.execute(text("""
            INSERT INTO portfolio_companies
                (vc_id, name, overview, sectors, stage, status,
                 hq, founded_year, company_size, valuation_usd, website_url, investment_date)
            VALUES
                (:vc_id, :name, :overview, :sectors, :stage, :status,
                 :hq, :founded_year, :company_size, :valuation_usd, :website_url, :investment_date)
            RETURNING id
        """), {
            "vc_id":           vc_id,
            "name":            company.name,
            "overview":        company.overview,
            "sectors":         company.sectors,
            "stage":           [s.value for s in company.stages],
            "status":          company.status.value if company.status else None,
            "hq":              company.hq,
            "founded_year":    company.founded_year,
            "company_size":    company.company_size,
            "valuation_usd":   company.valuation_usd,
            "website_url":     company.website_url,
            "investment_date": company.investment_date,
        })
        company_id = str(row.scalar())

        for tm in company.team:
            db.execute(text("""
                INSERT INTO portco_team
                    (portfolio_company_id, name, position, description, linkedin, email)
                VALUES
                    (:pcid, :name, :position, :description, :linkedin, :email)
            """), {
                "pcid":        company_id,
                "name":        tm.name,
                "position":    tm.position,
                "description": tm.description,
                "linkedin":    tm.linkedin,
                "email":       tm.email,
            })

    # ── Upsert vc_enrichments ─────────────────────────────────────────────────
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

    # ── Log to enrichment_runs ────────────────────────────────────────────────
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
            "funds_count":     len(vc.funds),
        }),
    })

    db.commit()
    return {
        "status":            "completed",
        "vc_id":             vc_id,
        "members_updated":   len(payload.members),
        "portfolio_updated": len(payload.portfolio),
        "funds_updated":     len(vc.funds),
    }


# ── Enrichment snapshot for a VC ──────────────────────────────────────────────

@router.get("/vc/{vc_id}")
def get_enrichment(vc_id: int, db: Session = Depends(get_db)):
    investor = db.execute(text("""
        SELECT id, canonical_name, enrichment_status, last_enriched_at
        FROM investors WHERE external_vc_id = :vc_id
    """), {"vc_id": vc_id}).mappings().first()
    if not investor:
        raise HTTPException(404, f"No investor with vc_id={vc_id}")

    snapshot = db.execute(text("""
        SELECT enriched_at, raw_payload, updated_at
        FROM vc_enrichments WHERE vc_id = :vc_id
    """), {"vc_id": vc_id}).mappings().first()

    members = db.execute(text("""
        SELECT name, position, expertise, description, linkedin, email, joined_at
        FROM vc_members WHERE vc_id = :vc_id ORDER BY name
    """), {"vc_id": vc_id}).mappings().all()

    funds = db.execute(text("""
        SELECT fund_name, fund_size, fund_size_raw, vintage_year
        FROM vc_funds WHERE vc_id = :vc_id ORDER BY vintage_year NULLS LAST
    """), {"vc_id": vc_id}).mappings().all()

    portfolio = db.execute(text("""
        SELECT pc.name, pc.overview, pc.sectors, pc.stage AS stages,
               pc.status, pc.hq, pc.founded_year, pc.company_size,
               pc.valuation_usd, pc.website_url, pc.investment_date,
               COALESCE(
                   json_agg(
                       json_build_object(
                           'name', pt.name,
                           'position', pt.position,
                           'linkedin', pt.linkedin,
                           'email', pt.email
                       )
                   ) FILTER (WHERE pt.id IS NOT NULL),
                   '[]'
               ) AS team
        FROM portfolio_companies pc
        LEFT JOIN portco_team pt ON pt.portfolio_company_id = pc.id
        WHERE pc.vc_id = :vc_id
        GROUP BY pc.id
        ORDER BY pc.name
    """), {"vc_id": vc_id}).mappings().all()

    return {
        "investor":       dict(investor),
        "enriched_at":    snapshot["enriched_at"] if snapshot else None,
        "members":        [dict(r) for r in members],
        "funds":          [dict(r) for r in funds],
        "portfolio":      [dict(r) for r in portfolio],
    }


# ── Enrichment queue stats ────────────────────────────────────────────────────

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
    return dict(row)
