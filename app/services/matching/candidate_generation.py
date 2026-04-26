from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.repositories.matching_read_repo import (
    full_text_retrieve_company_docs,
    full_text_retrieve_investor_docs,
    get_enriched_investors_for_structured_retrieval,
    get_investors_for_company_ids,
    graph_retrieve_investors,
)
from app.schemas.matching import FounderMatchRequest
from app.services.matching.founder_intent import FounderIntent

INVESTOR_DOCUMENT_TYPES = [
    "vc_profile",
    "vc_stated_thesis",
    "vc_revealed_thesis",
    "vc_team_profile",
]

COMPANY_DOCUMENT_TYPES = [
    "company_overview",
    "company_customer_profile",
    "company_product_profile",
    "company_market_profile",
]


class CandidateGenerationResult(BaseModel):
    retrieval_scores: dict[str, float] = Field(default_factory=dict)
    competitor_hits: dict[str, list[str]] = Field(default_factory=dict)
    ordered_investor_ids: list[str] = Field(default_factory=list)


def generate_candidates(
    db: Session,
    request: FounderMatchRequest,
    intent: FounderIntent,
    include_unenriched: bool = False,
) -> CandidateGenerationResult:
    structured = _structured_candidates(db, request, include_unenriched)
    investor_docs = _investor_doc_candidates(db, intent)
    company_docs = _company_doc_candidates(db, intent)
    graph_docs = _graph_candidates(db, intent)
    scores = reciprocal_rank_fusion([structured, investor_docs, company_docs, graph_docs])
    competitor_hits = _competitor_hits(db, intent)
    return _candidate_result(scores, structured, competitor_hits)


def reciprocal_rank_fusion(candidate_lists: list[list[str]], fusion_constant: int = 60) -> dict[str, float]:
    scores: defaultdict[str, float] = defaultdict(float)
    for candidate_list in candidate_lists:
        _add_candidate_list(scores, candidate_list, fusion_constant)
    return dict(scores)


def _structured_candidates(
    db: Session,
    request: FounderMatchRequest,
    include_unenriched: bool,
) -> list[str]:
    rows = get_enriched_investors_for_structured_retrieval(db, request, include_unenriched=include_unenriched)
    return [str(row["id"]) for row in rows]


def _investor_doc_candidates(db: Session, intent: FounderIntent) -> list[str]:
    if not intent.query_text:
        return []
    rows = full_text_retrieve_investor_docs(db, intent.query_text, INVESTOR_DOCUMENT_TYPES, 200)
    return [str(row["investor_id"]) for row in rows if row.get("investor_id")]


def _company_doc_candidates(db: Session, intent: FounderIntent) -> list[str]:
    if not intent.query_text:
        return []
    rows = full_text_retrieve_company_docs(db, intent.query_text, COMPANY_DOCUMENT_TYPES, 200)
    return _investors_from_company_rows(db, rows)


def _graph_candidates(db: Session, intent: FounderIntent) -> list[str]:
    targets = [value.lower() for value in [*intent.target_buyers, *intent.target_customers, *intent.competitor_categories]]
    if not targets:
        return []
    rows = graph_retrieve_investors(db, targets, _positive_graph_edge_types(), 200)
    return [str(row["investor_id"]) for row in rows]


def _competitor_hits(db: Session, intent: FounderIntent) -> dict[str, list[str]]:
    query = " ".join(intent.competitor_categories)
    if not query:
        return {}
    rows = full_text_retrieve_company_docs(db, query, COMPANY_DOCUMENT_TYPES, 200)
    return _competitor_map(db, rows)


def _positive_graph_edge_types() -> list[str]:
    return [
        "company_operates_in_sector",
        "company_targets_buyer_persona",
        "company_serves_customer_segment",
        "company_solves_pain_point",
        "company_integrates_with_category",
    ]


def _investors_from_company_rows(db: Session, rows: list[dict[str, Any]]) -> list[str]:
    company_ids = [str(row["company_id"]) for row in rows]
    investor_map = get_investors_for_company_ids(db, company_ids)
    ordered: list[str] = []
    for company_id in company_ids:
        ordered.extend(investor_map.get(company_id, []))
    return _dedupe(ordered)


def _competitor_map(db: Session, rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    company_ids = [str(row["company_id"]) for row in rows]
    investor_map = get_investors_for_company_ids(db, company_ids)
    result: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        _add_competitor_titles(result, investor_map, row)
    return dict(result)


def _add_competitor_titles(
    result: dict[str, list[str]],
    investor_map: dict[str, list[str]],
    row: dict[str, Any],
) -> None:
    company_id = str(row["company_id"])
    for investor_id in investor_map.get(company_id, []):
        result[investor_id].append(str(row.get("title") or "portfolio company"))


def _candidate_result(
    scores: dict[str, float],
    structured: list[str],
    competitor_hits: dict[str, list[str]],
) -> CandidateGenerationResult:
    ordered = _ordered_candidates(scores, structured)
    return CandidateGenerationResult(
        retrieval_scores=_normalised_scores(scores, ordered),
        competitor_hits=competitor_hits,
        ordered_investor_ids=ordered,
    )


def _ordered_candidates(scores: dict[str, float], structured: list[str]) -> list[str]:
    if scores:
        return sorted(scores, key=lambda investor_id: scores[investor_id], reverse=True)[:200]
    return structured[:200]


def _normalised_scores(scores: dict[str, float], ordered: list[str]) -> dict[str, float]:
    if not scores:
        return {investor_id: 20.0 for investor_id in ordered}
    maximum = max(scores.values())
    return {investor_id: round(100 * scores.get(investor_id, 0) / maximum, 2) for investor_id in ordered}


def _add_candidate_list(scores: defaultdict[str, float], candidate_list: list[str], fusion_constant: int) -> None:
    for rank, investor_id in enumerate(candidate_list, start=1):
        scores[investor_id] += 1 / (fusion_constant + rank)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
