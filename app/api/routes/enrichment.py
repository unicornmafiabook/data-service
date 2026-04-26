from traceback import format_exc
import json
import logging
from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enrichment import DeepEnrichedVC, VC, VCStatus
from app.services.indexing.retrieval_indexer import index_investor_for_retrieval

router = APIRouter(prefix="/enrichment", tags=["enrichment"])
logger = logging.getLogger(__name__)


def _nonempty(value: str | None) -> str | None:
    """Return None for empty/whitespace strings so COALESCE keeps the existing DB value."""
    if not value or not value.strip():
        return None
    return value


def _nonempty_list(value: list | None) -> list | None:
    """Return None for empty lists so COALESCE keeps the existing DB value."""
    if not value:
        return None
    return value
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
def complete_enrichment(vc_id: str, payload: DeepEnrichedVC, db: Session = Depends(get_db)):
    try:
        investor = _resolve_investor_for_enrichment(db, vc_id)
        if not investor:
            raise HTTPException(status_code=404, detail=f"No investor with vc_id={vc_id}")
        investor_uuid = investor["id"]
        external_vc_id = investor["external_vc_id"]

        vc      = payload.vc
        profile = payload.profile or None
        ident   = profile.identity    if profile else None
        prefs   = profile.preferences if profile else None
        rt      = payload.revealed_thesis

        # ── Resolve fields (profile overrides vc where both present) ─────────────
        short_desc    = (ident.short_description if ident else None) or vc.short_description
        long_desc     = (ident.long_description  if ident else None) or vc.long_description
        stated_thesis = (ident.stated_thesis     if ident else None) or vc.stated_thesis
        year_founded  = (ident.year_founded      if ident else None) or vc.year_founded
        location      = (ident.hq                if ident else None) or vc.location
        website_url   = _nonempty(
            (ident.website_url if ident else None) or str(vc.website_url)
        )

        rounds    = _nonempty_list((prefs.stages    if prefs else None) or [r.value for r in vc.rounds])
        sectors   = _nonempty_list((prefs.sectors   if prefs else None) or vc.sectors)
        geo_focus = _nonempty_list((prefs.geo_focus if prefs else None) or vc.geo_focus)
        tendency  = (prefs.tendency if prefs else None) or (vc.tendency.value if vc.tendency else None)
        ts_min    = (prefs.ticket_size.minimum_usd if prefs and prefs.ticket_size else None) or vc.ticket_size_min
        ts_max    = (prefs.ticket_size.maximum_usd if prefs and prefs.ticket_size else None) or vc.ticket_size_max
        ts_currency = (prefs.ticket_size.currency  if prefs and prefs.ticket_size else None)
        funds_list  = prefs.funds if prefs else []

        revealed_text = rt.summary if rt else vc.revealed_thesis
        revealed_json = json.dumps(rt.model_dump(mode="json")) if rt else None

        # ── Update investors — COALESCE so null incoming values keep existing data ─
        db.execute(text("""
            UPDATE investors SET
                canonical_name       = COALESCE(:name,              canonical_name),
                short_description    = COALESCE(:short_description, short_description),
                long_description     = COALESCE(:long_description,  long_description),
                stated_thesis        = COALESCE(:stated_thesis,     stated_thesis),
                revealed_thesis      = COALESCE(:revealed_thesis,   revealed_thesis),
                revealed_thesis_json = COALESCE(
                                           CAST(:revealed_thesis_json AS jsonb),
                                           revealed_thesis_json
                                       ),
                rounds               = COALESCE(:rounds,      rounds),
                sectors              = COALESCE(:sectors,     sectors),
                ticket_size_min      = COALESCE(:ticket_size_min, ticket_size_min),
                ticket_size_max      = COALESCE(:ticket_size_max, ticket_size_max),
                first_cheque_currency = COALESCE(:currency,   first_cheque_currency),
                investment_tendency  = COALESCE(:tendency,    investment_tendency),
                year_founded         = COALESCE(:year_founded, year_founded),
                geo_focus            = COALESCE(:geo_focus,   geo_focus),
                location             = COALESCE(:location,    location),
                website_url          = COALESCE(:website_url, website_url),
                status               = COALESCE(:status,      status),
                slug                 = COALESCE(:slug,        slug),
                enrichment_status    = 'completed',
                last_enriched_at     = NOW()
            WHERE external_vc_id = :vc_id
        """), {
            "vc_id":                external_vc_id,
            "name":                 _nonempty(vc.name),
            "short_description":    short_desc,
            "long_description":     long_desc,
            "stated_thesis":        stated_thesis,
            "revealed_thesis":      revealed_text,
            "revealed_thesis_json": revealed_json,
            "rounds":               rounds,
            "sectors":              sectors,
            "ticket_size_min":      ts_min,
            "ticket_size_max":      ts_max,
            "currency":             ts_currency,
            "tendency":             tendency,
            "year_founded":         year_founded,
            "geo_focus":            geo_focus,
            "location":             location,
            "website_url":          website_url,
            "status":               vc.status.value if vc.status else None,
            "slug":                 _nonempty(vc.slug),
        })

        # ── Replace vc_members ────────────────────────────────────────────────────
        db.execute(text("DELETE FROM vc_members WHERE vc_id = :vc_id"), {"vc_id": external_vc_id})
        for m in payload.team:
            expertise = [m.area_of_expertise] if m.area_of_expertise else []
            db.execute(text("""
                INSERT INTO vc_members
                    (vc_id, name, position, expertise, description, linkedin, email, joined_at)
                VALUES
                    (:vc_id, :name, :position, :expertise, :description, :linkedin, :email, :joined_at)
            """), {
                "vc_id":       external_vc_id,
                "name":        m.name,
                "position":    m.position,
                "expertise":   expertise,
                "description": m.description,
                "linkedin":    m.linkedin,
                "email":       m.email,
                "joined_at":   m.joined_at,
            })

        # ── Replace vc_funds ──────────────────────────────────────────────────────
        db.execute(text("DELETE FROM vc_funds WHERE vc_id = :vc_id"), {"vc_id": external_vc_id})
        for f in funds_list:
            db.execute(text("""
                INSERT INTO vc_funds (vc_id, fund_name, fund_size, vintage_year)
                VALUES (:vc_id, :fund_name, :fund_size, :vintage_year)
            """), {
                "vc_id":        external_vc_id,
                "fund_name":    f.name,
                "fund_size":    f.size_usd,
                "vintage_year": f.vintage_year,
            })

        # ── Replace portfolio_companies (cascade deletes portco_team) ─────────────
        db.execute(text("DELETE FROM portfolio_companies WHERE vc_id = :vc_id"), {"vc_id": external_vc_id})
        for company in payload.portfolio:
            stage = [company.investment_stage] if company.investment_stage else []
            row = db.execute(text("""
                INSERT INTO portfolio_companies
                    (vc_id, name, overview, sectors, stage, status,
                    hq, founded_year, company_size, valuation_usd, website_url)
                VALUES
                    (:vc_id, :name, :overview, :sectors, :stage, :status,
                    :hq, :founded_year, :company_size, :valuation_usd, :website_url)
                RETURNING id
            """), {
                "vc_id":        external_vc_id,
                "name":         company.name,
                "overview":     company.overview,
                "sectors":      company.sectors,
                "stage":        stage,
                "status":       company.status,
                "hq":           company.hq,
                "founded_year": company.founded_in,
                "company_size": company.company_size,
                "valuation_usd": company.valuation,
                "website_url":  company.website_url,
            })
            company_id = str(row.scalar())

            for exec_ in (company.executives or []):
                exec_dict = exec_ if isinstance(exec_, dict) else exec_.model_dump(exclude_none=True) if hasattr(exec_, "model_dump") else {}
                db.execute(text("""
                    INSERT INTO portco_team
                        (portfolio_company_id, name, position, description, linkedin, email)
                    VALUES
                        (:pcid, :name, :position, :description, :linkedin, :email)
                """), {
                    "pcid":        company_id,
                    "name":        exec_dict.get("name", ""),
                    "position":    exec_dict.get("position"),
                    "description": exec_dict.get("description"),
                    "linkedin":    exec_dict.get("linkedin"),
                    "email":       exec_dict.get("email"),
                })

        # ── Upsert vc_enrichments ─────────────────────────────────────────────────
        db.execute(text("""
            INSERT INTO vc_enrichments (vc_id, enriched_at, raw_payload, depth, branch_traces)
            VALUES (:vc_id, :enriched_at, CAST(:raw_payload AS jsonb), :depth, CAST(:branch_traces AS jsonb))
            ON CONFLICT (vc_id) DO UPDATE SET
                enriched_at   = EXCLUDED.enriched_at,
                raw_payload   = EXCLUDED.raw_payload,
                depth         = EXCLUDED.depth,
                branch_traces = EXCLUDED.branch_traces,
                updated_at    = NOW()
        """), {
            "vc_id":         external_vc_id,
            "enriched_at":   payload.enriched_at,
            "raw_payload":   json.dumps(payload.model_dump(mode="json")),
            "depth":         payload.depth,
            "branch_traces": json.dumps([bt.model_dump(mode="json") for bt in payload.branch_traces]),
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
                "vc_id":           external_vc_id,
                "members_count":   len(payload.team),
                "portfolio_count": len(payload.portfolio),
                "funds_count":     len(funds_list),
                "depth":           payload.depth,
            }),
        })

        db.commit()
        indexing_status, warnings = _rebuild_retrieval_index(db, str(investor_uuid))
        return {
            "status":            "completed",
            "vc_id":             external_vc_id,
            "members_updated":   len(payload.team),
            "portfolio_updated": len(payload.portfolio),
            "funds_updated":     len(funds_list),
            "indexing_status":   indexing_status,
            "warnings":          warnings,
        }
    except Exception:
        db.rollback()
        logger.error(format_exc())
        raise



def _resolve_investor_for_enrichment(db: Session, vc_id: str) -> dict[str, Any] | None:
    if vc_id.isdigit():
        return _investor_by_external_vc_id(db, int(vc_id))
    if not _is_uuid(vc_id):
        return None
    return _investor_by_uuid(db, vc_id)


def _investor_by_external_vc_id(db: Session, external_vc_id: int) -> dict[str, Any] | None:
    row = db.execute(text("""
        SELECT id, external_vc_id
        FROM investors
        WHERE external_vc_id = :external_vc_id
    """), {"external_vc_id": external_vc_id}).mappings().first()
    if not row:
        return None
    return dict(row)


def _investor_by_uuid(db: Session, investor_id: str) -> dict[str, Any] | None:
    row = db.execute(text("""
        SELECT id, external_vc_id
        FROM investors
        WHERE id = CAST(:investor_id AS uuid)
    """), {"investor_id": investor_id}).mappings().first()
    if not row:
        return None
    return dict(row)


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _rebuild_retrieval_index(db: Session, investor_id: str) -> tuple[str, list[str]]:
    try:
        index_investor_for_retrieval(db, investor_id)
        db.commit()
        return "completed", []
    except Exception:
        db.rollback()
        return "failed", ["Enrichment saved but retrieval index rebuild failed."]


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
    if not row:
        return {}
    return dict(row)
