import json
import re
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.orm import Session


def content_hash_for(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def load_investor(db: Session, investor_id: str) -> dict[str, Any] | None:
    row = db.execute(text("SELECT * FROM investors WHERE id = :id"), {"id": investor_id})
    mapping = row.mappings().first()
    if not mapping:
        return None
    return dict(mapping)


def load_vc_members(db: Session, external_vc_id: int) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT id, name, position, expertise, description, linkedin, email, joined_at
        FROM vc_members
        WHERE vc_id = :vc_id
        ORDER BY name
    """), {"vc_id": external_vc_id}).mappings().all()
    return [dict(row) for row in rows]


def load_vc_funds(db: Session, external_vc_id: int) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT id, fund_name, fund_size, fund_size_raw, vintage_year
        FROM vc_funds
        WHERE vc_id = :vc_id
        ORDER BY vintage_year NULLS LAST
    """), {"vc_id": external_vc_id}).mappings().all()
    return [dict(row) for row in rows]


def load_portfolio_companies(db: Session, external_vc_id: int) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT id, name, overview, sectors, stage, status, hq, founded_year,
               company_size, valuation_usd, website_url, investment_date
        FROM portfolio_companies
        WHERE vc_id = :vc_id
        ORDER BY name
    """), {"vc_id": external_vc_id}).mappings().all()
    return [dict(row) for row in rows]


def load_portco_team(db: Session, portfolio_company_id: str) -> list[dict[str, Any]]:
    rows = db.execute(text("""
        SELECT id, name, position, description, linkedin, email
        FROM portco_team
        WHERE portfolio_company_id = :portfolio_company_id
        ORDER BY name
    """), {"portfolio_company_id": portfolio_company_id}).mappings().all()
    return [dict(row) for row in rows]


def load_company_analysis(db: Session, company_id: str) -> dict[str, Any] | None:
    row = db.execute(text("""
        SELECT *
        FROM portfolio_company_analyses
        WHERE company_id = :company_id
    """), {"company_id": company_id}).mappings().first()
    if not row:
        return None
    return dict(row)


def reset_investor_index(db: Session, investor_id: str) -> None:
    db.execute(text("DELETE FROM retrieval_documents WHERE investor_id = :investor_id"), {"investor_id": investor_id})
    db.execute(text("""
        DELETE FROM entity_edges
        WHERE source_type = 'investor' AND source_id = :investor_id
    """), {"investor_id": investor_id})


def reset_company_edges(db: Session, company_id: str) -> None:
    db.execute(text("""
        DELETE FROM entity_edges
        WHERE source_type = 'company' AND source_id = :company_id
    """), {"company_id": company_id})


def resolve_company_id(db: Session, company: dict[str, Any]) -> str:
    domain = _domain_from_url(_text_or_none(company.get("website_url")))
    existing = _find_company(db, company, domain)
    if existing:
        return str(existing)
    return _create_company(db, company, domain)


def upsert_investor_company_relationship(db: Session, investor_id: str, company_id: str, company: dict[str, Any]) -> str:
    row = db.execute(text("""
        INSERT INTO investor_company_relationships (
            investor_id, company_id, relationship_type, investment_stage,
            investment_date, source, raw_data
        ) VALUES (
            :investor_id, :company_id, 'portfolio', :investment_stage,
            NULLIF(:investment_date, '')::date, 'enriched_portfolio',
            CAST(:raw_data AS jsonb)
        )
        ON CONFLICT (investor_id, company_id) DO UPDATE SET
            investment_stage = EXCLUDED.investment_stage,
            investment_date = EXCLUDED.investment_date,
            source = EXCLUDED.source,
            raw_data = EXCLUDED.raw_data
        RETURNING id
    """), {
        "investor_id": investor_id,
        "company_id": company_id,
        "investment_stage": _first_text(company.get("stage")),
        "investment_date": _date_or_empty(company.get("investment_date")),
        "raw_data": _json_text(company),
    }).scalar()
    return str(row)


def upsert_retrieval_document(db: Session, document: dict[str, Any]) -> bool:
    content_hash = content_hash_for(str(document["content"]))
    existing_hash = _existing_document_hash(db, document)
    if existing_hash == content_hash:
        return False
    _delete_document_version(db, document)
    _insert_document(db, document, content_hash)
    return True


def insert_entity_edge(db: Session, edge: dict[str, Any]) -> None:
    db.execute(text("""
        INSERT INTO entity_edges (
            source_type, source_id, target_type, target_id, edge_type,
            weight, evidence, evidence_url, metadata
        ) VALUES (
            :source_type, :source_id, :target_type, :target_id, :edge_type,
            :weight, :evidence, :evidence_url, CAST(:metadata AS jsonb)
        )
    """), edge)


def retrieval_document_count(db: Session) -> int:
    count = db.execute(text("SELECT COUNT(*) FROM retrieval_documents")).scalar()
    return int(count or 0)


def _find_company(db: Session, company: dict[str, Any], domain: str | None) -> str | None:
    if domain:
        row = db.execute(text("SELECT id FROM companies WHERE domain = :domain"), {"domain": domain}).scalar()
        if row:
            return str(row)
    row = db.execute(text("""
        SELECT id FROM companies
        WHERE lower(canonical_name) = lower(:name)
        ORDER BY created_at
        LIMIT 1
    """), {"name": company["name"]}).scalar()
    if not row:
        return None
    return str(row)


def _create_company(db: Session, company: dict[str, Any], domain: str | None) -> str:
    row = db.execute(text("""
        INSERT INTO companies (
            canonical_name, normalized_name, website, domain, description,
            sector, hq_country, founded_year, enrichment_status
        ) VALUES (
            :name, lower(:name), :website, :domain, :description,
            :sector, :hq, :founded_year, 'completed'
        )
        RETURNING id
    """), {
        "name": company["name"],
        "website": company.get("website_url"),
        "domain": domain,
        "description": company.get("overview"),
        "sector": _first_text(company.get("sectors")),
        "hq": company.get("hq"),
        "founded_year": company.get("founded_year"),
    }).scalar()
    return str(row)


def _insert_document(db: Session, document: dict[str, Any], content_hash: str) -> None:
    db.execute(text("""
        INSERT INTO retrieval_documents (
            entity_type, entity_id, investor_id, document_type, title, content,
            keywords, sectors, stages, geographies, buyer_personas,
            customer_segments, metadata, content_hash
        ) VALUES (
            :entity_type, :entity_id, :investor_id, :document_type, :title,
            :content, :keywords, :sectors, :stages, :geographies,
            :buyer_personas, :customer_segments, CAST(:metadata AS jsonb),
            :content_hash
        )
    """), {**document, "content_hash": content_hash})


def _existing_document_hash(db: Session, document: dict[str, Any]) -> str | None:
    row = db.execute(text("""
        SELECT content_hash
        FROM retrieval_documents
        WHERE entity_type = :entity_type
          AND entity_id = :entity_id
          AND document_type = :document_type
        LIMIT 1
    """), document).scalar()
    if not row:
        return None
    return str(row)


def _delete_document_version(db: Session, document: dict[str, Any]) -> None:
    db.execute(text("""
        DELETE FROM retrieval_documents
        WHERE entity_type = :entity_type
          AND entity_id = :entity_id
          AND document_type = :document_type
    """), document)


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.removeprefix("www.") or None


def _first_text(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    if value:
        return str(value)
    return None


def _text_or_empty(value: Any) -> str:
    if not value:
        return ""
    return str(value)


def _date_or_empty(value: Any) -> str:
    text_value = _text_or_empty(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text_value):
        return text_value
    return ""


def _text_or_none(value: Any) -> str | None:
    if not value:
        return None
    return str(value)


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, default=str)
