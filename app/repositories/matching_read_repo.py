from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.matching import FounderMatchRequest


def get_enriched_investors_for_structured_retrieval(
    db: Session,
    request: FounderMatchRequest,
    limit: int = 300,
    include_unenriched: bool = False,
) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT *, (
            CASE WHEN :stage = ANY(COALESCE(rounds, '{}')) THEN 25 ELSE 0 END +
            CASE WHEN :stage = ANY(COALESCE(stages, '{}')) THEN 18 ELSE 0 END +
            CASE WHEN sectors && :sectors THEN 25 ELSE 0 END +
            CASE WHEN geo_focus && :geographies THEN 15 ELSE 0 END +
            CASE WHEN geographies && :geographies THEN 10 ELSE 0 END +
            CASE WHEN :raise_amount BETWEEN COALESCE(ticket_size_min, first_cheque_min, 0)
                 AND COALESCE(ticket_size_max, first_cheque_max, 1000000000000) THEN 20 ELSE 0 END
        ) AS retrieval_score
        FROM investors
        WHERE (:include_unenriched OR enrichment_status = 'completed')
        ORDER BY retrieval_score DESC, last_enriched_at DESC NULLS LAST
        LIMIT :limit
    """), {
        "stage": request.stage or "",
        "sectors": request.sectors,
        "geographies": request.geographies,
        "raise_amount": request.raise_amount or 0,
        "include_unenriched": include_unenriched,
        "limit": limit,
    }).mappings().all()
    return [dict(row) for row in rows]


def full_text_retrieve_investor_docs(
    db: Session,
    query: str,
    document_types: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT investor_id, document_type, title, content,
               ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) AS rank_score
        FROM retrieval_documents
        WHERE investor_id IS NOT NULL
          AND document_type = ANY(:document_types)
          AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
        ORDER BY rank_score DESC
        LIMIT :limit
    """), {"query": query, "document_types": document_types, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]


def full_text_retrieve_company_docs(
    db: Session,
    query: str,
    document_types: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT entity_id AS company_id, document_type, title, content,
               ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) AS rank_score
        FROM retrieval_documents
        WHERE entity_type = 'company'
          AND document_type = ANY(:document_types)
          AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
        ORDER BY rank_score DESC
        LIMIT :limit
    """), {"query": query, "document_types": document_types, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]


def vector_retrieve_docs(
    db: Session,
    query_embedding: list[float],
    document_types: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    return []


def get_investors_for_company_ids(db: Session, company_ids: list[str]) -> dict[str, list[str]]:
    rows = db.execute(text("""
        SELECT company_id, array_agg(investor_id::text) AS investor_ids
        FROM investor_company_relationships
        WHERE company_id = ANY(:company_ids)
        GROUP BY company_id
    """), {"company_ids": company_ids}).mappings().all()
    return {str(row["company_id"]): list(row["investor_ids"] or []) for row in rows}


def get_enriched_investor_detail_db(
    db: Session,
    investor_id: str,
    include_unenriched: bool = False,
) -> dict[str, Any] | None:
    row = db.execute(text("""
        SELECT *
        FROM investors
        WHERE id = :investor_id
          AND (:include_unenriched OR enrichment_status = 'completed')
    """), {
        "investor_id": investor_id,
        "include_unenriched": include_unenriched,
    }).mappings().first()
    if not row:
        return None
    return dict(row)


def get_investor_id_by_slug(db: Session, slug: str) -> str | None:
    row = db.execute(text("""
        SELECT id
        FROM investors
        WHERE slug = :slug
    """), {"slug": slug}).scalar()
    if not row:
        return None
    return str(row)


def get_investor_id_by_external_vc_id(db: Session, external_vc_id: int) -> str | None:
    row = db.execute(text("""
        SELECT id
        FROM investors
        WHERE external_vc_id = :external_vc_id
    """), {"external_vc_id": external_vc_id}).scalar()
    if not row:
        return None
    return str(row)


def get_enriched_portfolio_for_investor_db(db: Session, investor_id: str) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT pc.*, icr.company_id AS canonical_company_id
        FROM investors i
        JOIN portfolio_companies pc ON pc.vc_id = i.external_vc_id
        LEFT JOIN investor_company_relationships icr
               ON icr.investor_id = i.id
              AND lower(icr.raw_data ->> 'name') = lower(pc.name)
        WHERE i.id = :investor_id
        ORDER BY pc.name
    """), {"investor_id": investor_id}).mappings().all()
    return [dict(row) for row in rows]


def get_vc_team_members_db(db: Session, investor_id: str) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT vm.*
        FROM investors i
        JOIN vc_members vm ON vm.vc_id = i.external_vc_id
        WHERE i.id = :investor_id
        ORDER BY vm.name
    """), {"investor_id": investor_id}).mappings().all()
    return [dict(row) for row in rows]


def get_company_analysis_db(db: Session, company_id: str) -> dict[str, Any] | None:
    row = db.execute(text("""
        SELECT *
        FROM portfolio_company_analyses
        WHERE company_id = :company_id
    """), {"company_id": company_id}).mappings().first()
    if not row:
        return None
    return dict(row)


def graph_retrieve_investors(db: Session, target_values: list[str], edge_types: list[str], limit: int) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT icr.investor_id, SUM(ee.weight) AS graph_score
        FROM entity_edges ee
        JOIN investor_company_relationships icr ON icr.company_id::text = ee.source_id::text
        WHERE lower(ee.target_id) = ANY(:target_values)
          AND ee.edge_type = ANY(:edge_types)
        GROUP BY icr.investor_id
        ORDER BY graph_score DESC
        LIMIT :limit
    """), {"target_values": target_values, "edge_types": edge_types, "limit": limit}).mappings().all()
    return [dict(row) for row in rows]


def count_completed_investors(db: Session) -> int:
    count = db.execute(text("""
        SELECT COUNT(*)
        FROM investors
        WHERE enrichment_status = 'completed'
    """)).scalar()
    return int(count or 0)
