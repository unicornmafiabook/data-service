from typing import Any

from sqlalchemy.orm import Session

from app.repositories.retrieval_repo import (
    insert_entity_edge,
    load_investor,
    load_company_analysis,
    load_portco_team,
    load_portfolio_companies,
    load_vc_funds,
    load_vc_members,
    reset_company_edges,
    reset_investor_index,
    resolve_company_id,
    upsert_investor_company_relationship,
    upsert_retrieval_document,
)
from app.services.indexing.document_builder import (
    build_company_documents,
    build_entity_edges,
    build_investor_documents,
    build_relationship_document,
)


def index_investor_for_retrieval(db: Session, investor_id: str) -> dict[str, Any]:
    investor = load_investor(db, investor_id)
    if not investor:
        return {"status": "skipped", "documents_updated": 0, "edges_created": 0}
    external_vc_id = int(investor["external_vc_id"])
    return _index_loaded_investor(db, investor, external_vc_id)


def _index_loaded_investor(db: Session, investor: dict[str, Any], external_vc_id: int) -> dict[str, Any]:
    members = load_vc_members(db, external_vc_id)
    funds = load_vc_funds(db, external_vc_id)
    portfolio = load_portfolio_companies(db, external_vc_id)
    reset_investor_index(db, str(investor["id"]))
    return _write_index(db, investor, members, funds, portfolio)


def _write_index(
    db: Session,
    investor: dict[str, Any],
    members: list[dict[str, Any]],
    funds: list[dict[str, Any]],
    portfolio: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = {"status": "completed", "documents_updated": 0, "edges_created": 0}
    counts["documents_updated"] += _write_documents(db, build_investor_documents(investor, members, funds))
    _write_portfolio_index(db, investor, portfolio, counts)
    return counts


def _write_portfolio_index(
    db: Session,
    investor: dict[str, Any],
    portfolio: list[dict[str, Any]],
    counts: dict[str, Any],
) -> None:
    for company in portfolio:
        _write_company_index(db, investor, company, counts)


def _write_company_index(
    db: Session,
    investor: dict[str, Any],
    company: dict[str, Any],
    counts: dict[str, Any],
) -> None:
    company_id = resolve_company_id(db, company)
    relationship_id = upsert_investor_company_relationship(db, str(investor["id"]), company_id, company)
    team = load_portco_team(db, str(company["id"]))
    counts["documents_updated"] += _write_documents(db, build_company_documents(company_id, company, team))
    counts["documents_updated"] += _write_documents(db, [build_relationship_document(relationship_id, str(investor["id"]), investor, company)])
    analysis = load_company_analysis(db, company_id)
    counts["edges_created"] += _write_edges(db, str(investor["id"]), company_id, company, analysis)


def _write_documents(db: Session, documents: list[dict[str, Any]]) -> int:
    return sum(1 for document in documents if upsert_retrieval_document(db, document))


def _write_edges(
    db: Session,
    investor_id: str,
    company_id: str,
    company: dict[str, Any],
    analysis: dict[str, Any] | None,
) -> int:
    reset_company_edges(db, company_id)
    edges = build_entity_edges(investor_id, company_id, company, analysis)
    for edge in edges:
        insert_entity_edge(db, edge)
    return len(edges)
