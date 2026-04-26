import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.importer.normalise import normalize_name, clean_website, extract_domain
from app.models.investors import (
    InvestorCreate,
    InvestorUpdate,
    InvestorSearchBody,
    UPDATABLE_COLUMNS,
)

router = APIRouter(prefix="/investors", tags=["investors"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "investor"


def make_unique_slug(db: Session, canonical_name: str) -> str:
    base_slug = slugify(canonical_name)
    slug = base_slug
    counter = 2

    while db.execute(
        text("SELECT 1 FROM investors WHERE slug = :slug"),
        {"slug": slug},
    ).scalar():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT
            COUNT(*)                                                        AS total_investors,
            COUNT(*) FILTER (WHERE enrichment_status = 'completed')        AS enriched,
            COUNT(*) FILTER (WHERE enrichment_status = 'pending')          AS pending,
            COUNT(*) FILTER (WHERE enrichment_status = 'not_started')      AS not_started,
            COUNT(*) FILTER (WHERE needs_review = TRUE)                    AS needs_review,
            COUNT(*) FILTER (WHERE source_count > 1)                       AS multi_source
        FROM investors
    """)).mappings().first()

    sources = db.execute(text("""
        SELECT COUNT(*) AS total FROM investor_sources
    """)).scalar()

    members = db.execute(text("SELECT COUNT(*) FROM vc_members")).scalar()
    funds = db.execute(text("SELECT COUNT(*) FROM vc_funds")).scalar()
    portcos = db.execute(text("SELECT COUNT(*) FROM portfolio_companies")).scalar()

    return {
        "investors": dict(row),
        "investor_sources": sources,
        "vc_members": members,
        "vc_funds": funds,
        "portfolio_companies": portcos,
    }


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
def list_investors(
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT
            id,
            external_vc_id,
            canonical_name,
            slug,
            website,
            domain,
            stages,
            sectors,
            geographies,
            rounds,
            geo_focus,
            investor_type,
            status,
            hq_country,
            location,
            short_description,
            enrichment_status,
            first_cheque_min,
            first_cheque_max,
            source_count,
            needs_review
        FROM investors
        ORDER BY canonical_name
        LIMIT :limit OFFSET :offset
    """), {"limit": limit, "offset": offset}).mappings().all()

    return {"count": len(rows), "results": [dict(r) for r in rows]}


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_investor(body: InvestorCreate, db: Session = Depends(get_db)):
    website = clean_website(body.website)
    domain = extract_domain(website)
    slug = make_unique_slug(db, body.canonical_name)

    # Block duplicate domain
    if domain:
        existing = db.execute(
            text("SELECT id FROM investors WHERE domain = :domain"),
            {"domain": domain},
        ).scalar()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Investor with domain {domain} already exists (id={existing})",
            )

    result = db.execute(text("""
        INSERT INTO investors (
            canonical_name, normalized_name, website, domain, slug,
            investor_type, status, hq_city, hq_country,
            stages, sectors, geographies,
            description, investment_thesis,
            first_cheque_min, first_cheque_max, first_cheque_currency,
            enrichment_status, source_count, source_names,
            dedupe_key, dedupe_confidence, needs_review
        ) VALUES (
            :canonical_name, :normalized_name, :website, :domain, :slug,
            :investor_type, :status, :hq_city, :hq_country,
            :stages, :sectors, :geographies,
            :description, :investment_thesis,
            :first_cheque_min, :first_cheque_max, :first_cheque_currency,
            'not_started', 0, '{}',
            :dedupe_key, 0.9, FALSE
        )
        RETURNING id, external_vc_id, slug
    """), {
        "canonical_name": body.canonical_name,
        "normalized_name": normalize_name(body.canonical_name),
        "website": website,
        "domain": domain,
        "slug": slug,
        "investor_type": body.investor_type,
        "status": body.status,
        "hq_city": body.hq_city,
        "hq_country": body.hq_country,
        "stages": body.stages,
        "sectors": body.sectors,
        "geographies": body.geographies,
        "description": body.description,
        "investment_thesis": body.investment_thesis,
        "first_cheque_min": body.first_cheque_min,
        "first_cheque_max": body.first_cheque_max,
        "first_cheque_currency": body.first_cheque_currency,
        "dedupe_key": f"domain:{domain}" if domain else f"name:{normalize_name(body.canonical_name)}",
    })

    row = result.mappings().first()
    db.commit()

    return {
        "id": str(row["id"]),
        "external_vc_id": row["external_vc_id"],
        "slug": row["slug"],
    }


# ── Rich search (POST body) ───────────────────────────────────────────────────

@router.post("/search")
def search_post(body: InvestorSearchBody, db: Session = Depends(get_db)):
    sql = """
        SELECT
            id,
            external_vc_id,
            canonical_name,
            slug,
            website,
            domain,
            investor_type,
            status,
            hq_city,
            hq_country,
            location,
            stages,
            sectors,
            geographies,
            rounds,
            geo_focus,
            short_description,
            stated_thesis,
            revealed_thesis,
            investment_tendency,
            year_founded,
            first_cheque_min,
            first_cheque_max,
            first_cheque_currency,
            ticket_size_min,
            ticket_size_max,
            source_count,
            dedupe_confidence,
            needs_review,
            enrichment_status
        FROM investors
        WHERE 1 = 1
    """

    params: dict = {
        "limit": min(body.limit, 200),
        "offset": body.offset,
    }

    if body.name:
        sql += " AND canonical_name ILIKE :name"
        params["name"] = f"%{body.name}%"

    if body.q:
        sql += """
            AND (
                canonical_name ILIKE :q
                OR stated_thesis ILIKE :q
                OR revealed_thesis ILIKE :q
                OR investment_thesis ILIKE :q
                OR description ILIKE :q
                OR short_description ILIKE :q
                OR long_description ILIKE :q
            )
        """
        params["q"] = f"%{body.q}%"

    if body.stages:
        sql += " AND (stages && :stages OR rounds && :stages)"
        params["stages"] = body.stages

    if body.sectors:
        sql += " AND sectors && :sectors"
        params["sectors"] = body.sectors

    if body.geographies:
        sql += " AND (geographies && :geos OR geo_focus && :geos)"
        params["geos"] = body.geographies

    if body.investor_type:
        sql += " AND investor_type ILIKE :investor_type"
        params["investor_type"] = f"%{body.investor_type}%"

    if body.enrichment_status:
        sql += " AND enrichment_status = :enrichment_status"
        params["enrichment_status"] = body.enrichment_status

    if body.needs_review is not None:
        sql += " AND needs_review = :needs_review"
        params["needs_review"] = body.needs_review

    if body.cheque_max is not None:
        sql += """
            AND (
                ticket_size_min IS NULL
                OR ticket_size_min <= :cheque_max
                OR first_cheque_min IS NULL
                OR first_cheque_min <= :cheque_max
            )
        """
        params["cheque_max"] = body.cheque_max

    if body.cheque_min is not None:
        sql += """
            AND (
                ticket_size_max IS NULL
                OR ticket_size_max >= :cheque_min
                OR first_cheque_max IS NULL
                OR first_cheque_max >= :cheque_min
            )
        """
        params["cheque_min"] = body.cheque_min

    sql += " ORDER BY canonical_name LIMIT :limit OFFSET :offset"

    rows = db.execute(text(sql), params).mappings().all()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


# ── GET search (simple, query-param) ─────────────────────────────────────────

@router.get("/search")
def search_get(
    name: str | None = None,
    stage: str | None = None,
    sector: str | None = None,
    geography: str | None = None,
    cheque_max: float | None = None,
    q: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    sql = """
        SELECT
            id,
            external_vc_id,
            canonical_name,
            slug,
            website,
            domain,
            investor_type,
            status,
            hq_city,
            hq_country,
            location,
            stages,
            sectors,
            geographies,
            rounds,
            geo_focus,
            short_description,
            stated_thesis,
            revealed_thesis,
            investment_tendency,
            year_founded,
            first_cheque_min,
            first_cheque_max,
            first_cheque_currency,
            ticket_size_min,
            ticket_size_max,
            source_count,
            dedupe_confidence,
            needs_review,
            enrichment_status
        FROM investors
        WHERE 1 = 1
    """

    params: dict = {
        "limit": limit,
        "offset": offset,
    }

    if name:
        sql += " AND canonical_name ILIKE :name"
        params["name"] = f"%{name}%"

    if stage:
        sql += " AND (:stage = ANY(stages) OR :stage = ANY(rounds))"
        params["stage"] = stage

    if sector:
        sql += " AND :sector = ANY(sectors)"
        params["sector"] = sector

    if geography:
        sql += " AND (:geography = ANY(geographies) OR :geography = ANY(geo_focus))"
        params["geography"] = geography

    if cheque_max is not None:
        sql += """
            AND (
                ticket_size_min IS NULL
                OR ticket_size_min <= :cheque_max
                OR first_cheque_min IS NULL
                OR first_cheque_min <= :cheque_max
            )
        """
        params["cheque_max"] = cheque_max

    if q:
        sql += """
            AND (
                canonical_name ILIKE :q
                OR stated_thesis ILIKE :q
                OR revealed_thesis ILIKE :q
                OR investment_thesis ILIKE :q
                OR description ILIKE :q
                OR short_description ILIKE :q
                OR long_description ILIKE :q
            )
        """
        params["q"] = f"%{q}%"

    sql += " ORDER BY canonical_name LIMIT :limit OFFSET :offset"

    rows = db.execute(text(sql), params).mappings().all()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


# ── Lookup by slug ────────────────────────────────────────────────────────────

@router.get("/by-slug/{slug}")
def get_by_slug(slug: str, db: Session = Depends(get_db)):
    investor = db.execute(
        text("SELECT * FROM investors WHERE slug = :slug"),
        {"slug": slug},
    ).mappings().first()

    if not investor:
        raise HTTPException(status_code=404, detail=f"No investor with slug '{slug}'")

    return dict(investor)


# ── Single investor ───────────────────────────────────────────────────────────

@router.get("/{investor_id}")
def get_investor(investor_id: str, db: Session = Depends(get_db)):
    investor = db.execute(
        text("SELECT * FROM investors WHERE id = :id"),
        {"id": investor_id},
    ).mappings().first()

    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    sources = db.execute(text("""
        SELECT source_name, source_row_id, original_name, original_website, raw_data
        FROM investor_sources
        WHERE investor_id = :id
        ORDER BY source_name
    """), {"id": investor_id}).mappings().all()

    return {
        "investor": dict(investor),
        "sources": [dict(r) for r in sources],
    }


# ── Partial update ────────────────────────────────────────────────────────────

@router.patch("/{investor_id}")
def update_investor(investor_id: str, body: InvestorUpdate, db: Session = Depends(get_db)):
    updates = {
        k: v for k, v in body.model_dump(exclude_none=True).items()
        if k in UPDATABLE_COLUMNS
    }

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    # Check investor exists
    exists = db.execute(
        text("SELECT 1 FROM investors WHERE id = :id"),
        {"id": investor_id},
    ).scalar()

    if not exists:
        raise HTTPException(status_code=404, detail="Investor not found")

    set_clause = ", ".join(f"{col} = :{col}" for col in updates)

    db.execute(
        text(f"UPDATE investors SET {set_clause}, updated_at = NOW() WHERE id = :id"),
        {**updates, "id": investor_id},
    )

    db.commit()

    return {"updated": list(updates.keys())}


# ── Team members ──────────────────────────────────────────────────────────────

@router.get("/{investor_id}/members")
def get_members(investor_id: str, db: Session = Depends(get_db)):
    vc_id = db.execute(
        text("SELECT external_vc_id FROM investors WHERE id = :id"),
        {"id": investor_id},
    ).scalar()

    if vc_id is None:
        raise HTTPException(status_code=404, detail="Investor not found")

    rows = db.execute(text("""
        SELECT name, position, expertise, description, linkedin, email, joined_at
        FROM vc_members
        WHERE vc_id = :vc_id
        ORDER BY name
    """), {"vc_id": vc_id}).mappings().all()

    return {"count": len(rows), "results": [dict(r) for r in rows]}


# ── Fund history ──────────────────────────────────────────────────────────────

@router.get("/{investor_id}/funds")
def get_funds(investor_id: str, db: Session = Depends(get_db)):
    vc_id = db.execute(
        text("SELECT external_vc_id FROM investors WHERE id = :id"),
        {"id": investor_id},
    ).scalar()

    if vc_id is None:
        raise HTTPException(status_code=404, detail="Investor not found")

    rows = db.execute(text("""
        SELECT fund_name, fund_size, fund_size_raw, vintage_year
        FROM vc_funds
        WHERE vc_id = :vc_id
        ORDER BY vintage_year NULLS LAST
    """), {"vc_id": vc_id}).mappings().all()

    return {"count": len(rows), "results": [dict(r) for r in rows]}


# ── Legacy portfolio (CSV-imported) ──────────────────────────────────────────

@router.get("/{investor_id}/portfolio")
def get_portfolio(investor_id: str, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT
            c.id,
            c.canonical_name,
            c.website,
            c.domain,
            c.sector,
            c.sub_sector,
            c.description,
            r.relationship_type,
            r.investment_stage,
            r.investment_round,
            r.investment_date,
            r.confidence_score,
            r.source
        FROM investor_company_relationships r
        JOIN companies c ON c.id = r.company_id
        WHERE r.investor_id = :id
        ORDER BY c.canonical_name
    """), {"id": investor_id}).mappings().all()

    return {"count": len(rows), "results": [dict(r) for r in rows]}


# ── Similar investors ─────────────────────────────────────────────────────────

@router.get("/{investor_id}/similar")
def get_similar(
    investor_id: str,
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    source = db.execute(
        text("SELECT stages, sectors, geographies, geo_focus FROM investors WHERE id = :id"),
        {"id": investor_id},
    ).mappings().first()

    if not source:
        raise HTTPException(status_code=404, detail="Investor not found")

    rows = db.execute(text("""
        SELECT
            id,
            external_vc_id,
            canonical_name,
            slug,
            website,
            domain,
            stages,
            sectors,
            geographies,
            geo_focus,
            short_description,
            enrichment_status,
            (
                COALESCE(array_length(
                    ARRAY(SELECT unnest(stages) INTERSECT SELECT unnest(:stages)), 1
                ), 0) * 2 +
                COALESCE(array_length(
                    ARRAY(SELECT unnest(sectors) INTERSECT SELECT unnest(:sectors)), 1
                ), 0) * 3 +
                COALESCE(array_length(
                    ARRAY(SELECT unnest(geographies) INTERSECT SELECT unnest(:geos)), 1
                ), 0) +
                COALESCE(array_length(
                    ARRAY(SELECT unnest(geo_focus) INTERSECT SELECT unnest(:geo_focus)), 1
                ), 0)
            ) AS similarity_score
        FROM investors
        WHERE id != :id
          AND (
              stages && :stages
              OR sectors && :sectors
              OR geographies && :geos
              OR geo_focus && :geo_focus
          )
        ORDER BY similarity_score DESC
        LIMIT :limit
    """), {
        "id": investor_id,
        "stages": list(source["stages"] or []),
        "sectors": list(source["sectors"] or []),
        "geos": list(source["geographies"] or []),
        "geo_focus": list(source["geo_focus"] or []),
        "limit": limit,
    }).mappings().all()

    return {"count": len(rows), "results": [dict(r) for r in rows]}


# ── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{investor_id}", status_code=200)
def delete_investor(investor_id: str, db: Session = Depends(get_db)):
    investor = db.execute(
        text("SELECT id, external_vc_id FROM investors WHERE id = :id"),
        {"id": investor_id},
    ).mappings().first()

    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    # enrichment_runs uses a polymorphic target_id with no FK — delete manually
    db.execute(
        text("DELETE FROM enrichment_runs WHERE target_type = 'investor' AND target_id = :id"),
        {"id": investor_id},
    )

    # FK cascades handle investor_sources, investor_company_relationships,
    # dedupe_candidates, vc_members, vc_funds, portfolio_companies,
    # portco_team, vc_enrichments, etc.
    db.execute(
        text("DELETE FROM investors WHERE id = :id"),
        {"id": investor_id},
    )

    db.commit()

    return {
        "deleted": investor_id,
        "external_vc_id": investor["external_vc_id"],
    }