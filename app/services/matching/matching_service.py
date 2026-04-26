import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.matching_read_repo import (
    count_completed_investors,
    get_company_analysis_db,
    get_enriched_investor_detail_db,
    get_enriched_portfolio_for_investor_db,
    get_investor_id_by_external_vc_id,
    get_investor_id_by_slug,
    get_vc_team_members_db,
)
from app.repositories.retrieval_repo import retrieval_document_count
from app.schemas.matching import (
    FounderMatchRequest,
    FounderMatchResponse,
    PortfolioOpportunityResult,
    VCExplanationRequest,
    VCExplanationResponse,
    VCMatchResult,
    VCMemoExplanation,
)
from app.services.matching.candidate_generation import generate_candidates
from app.services.matching.explanation import generate_explanation
from app.services.matching.founder_intent import FounderIntent, build_founder_intent, is_sparse_intent
from app.services.matching.llm_explanation import LLMExplanationResult, generate_llm_explanation
from app.services.matching.relationship_classifier import RelationshipClassification, classify_portfolio_company
from app.services.matching.scoring import ScoreBreakdown, score_vc_match


def rank_vcs_for_founder(db: Session, request: FounderMatchRequest) -> FounderMatchResponse:
    warnings = _initial_warnings(db, request)
    use_fallback = _use_unenriched_fallback(db, request, warnings)
    if count_completed_investors(db) == 0 and not use_fallback:
        return _empty_response(warnings)
    intent = build_founder_intent(request)
    warnings.extend(_intent_warnings(intent))
    candidates = generate_candidates(db, request, intent, use_fallback)
    results = _score_candidates(db, intent, candidates.ordered_investor_ids, candidates.retrieval_scores, candidates.competitor_hits, warnings, use_fallback)
    return FounderMatchResponse(
        count=len(results[: request.limit]),
        data_scope=_data_scope(use_fallback),
        top_vcs=_ranked_results(results, request.limit),
        warnings=warnings,
    )


def explain_vc_for_founder(db: Session, request: VCExplanationRequest) -> VCExplanationResponse:
    investor_id = _resolve_explanation_investor_id(db, request)
    intent = build_founder_intent(request.founder)
    match_result = _score_candidate(db, intent, investor_id, {investor_id: 0}, {}, False)
    if not match_result:
        raise ValueError("Investor is not enriched or could not be scored.")
    llm_result = generate_llm_explanation(_llm_evidence(request, match_result))
    return _explanation_response(match_result, llm_result)


def _score_candidates(
    db: Session,
    intent: FounderIntent,
    investor_ids: list[str],
    retrieval_scores: dict[str, float],
    competitor_hits: dict[str, list[str]],
    warnings: list[str],
    include_unenriched: bool,
) -> list[VCMatchResult]:
    results: list[VCMatchResult] = []
    for investor_id in investor_ids[:200]:
        _append_scored_candidate(db, intent, investor_id, retrieval_scores, competitor_hits, warnings, results, include_unenriched)
    return sorted(results, key=lambda result: result.overall_score, reverse=True)


def _resolve_explanation_investor_id(db: Session, request: VCExplanationRequest) -> str:
    if request.investor_id:
        return str(request.investor_id)
    if request.slug:
        return _resolved_or_error(get_investor_id_by_slug(db, request.slug))
    if request.external_vc_id:
        return _resolved_or_error(get_investor_id_by_external_vc_id(db, request.external_vc_id))
    raise ValueError("Provide one of investor_id, slug, or external_vc_id.")


def _resolved_or_error(investor_id: str | None) -> str:
    if investor_id:
        return investor_id
    raise ValueError("Investor identifier did not match an investor.")


def _llm_evidence(request: VCExplanationRequest, match_result: VCMatchResult) -> dict[str, Any]:
    return {
        "founder": request.founder.model_dump(exclude={"founder_name", "company_name"}),
        "vc_match": match_result.model_dump(mode="json"),
        "task": "Create a clearer explanation for this one VC match.",
    }


def _explanation_response(
    match_result: VCMatchResult,
    llm_result: LLMExplanationResult,
) -> VCExplanationResponse:
    warnings = [llm_result.warning] if llm_result.warning else []
    memo = VCMemoExplanation(**llm_result.explanation.model_dump()) if llm_result.explanation else None
    return VCExplanationResponse(
        investor_id=match_result.investor_id,
        external_vc_id=match_result.external_vc_id,
        slug=match_result.slug,
        name=match_result.name,
        model=llm_result.model,
        llm_status=llm_result.status,
        deterministic_score=match_result,
        memo=memo,
        warnings=warnings,
    )


def _llm_warnings(llm_result: LLMExplanationResult) -> list[str]:
    if llm_result.warning:
        return [llm_result.warning]
    return []


def _append_scored_candidate(
    db: Session,
    intent: FounderIntent,
    investor_id: str,
    retrieval_scores: dict[str, float],
    competitor_hits: dict[str, list[str]],
    warnings: list[str],
    results: list[VCMatchResult],
    include_unenriched: bool,
) -> None:
    try:
        result = _score_candidate(db, intent, investor_id, retrieval_scores, competitor_hits, include_unenriched)
    except Exception as exc:
        warnings.append(f"Skipped investor {investor_id} after scoring failed: {exc}")
        return
    if result:
        results.append(result)


def _score_candidate(
    db: Session,
    intent: FounderIntent,
    investor_id: str,
    retrieval_scores: dict[str, float],
    competitor_hits: dict[str, list[str]],
    include_unenriched: bool,
) -> VCMatchResult | None:
    investor = get_enriched_investor_detail_db(db, investor_id, include_unenriched)
    if not investor:
        return None
    relationships = _relationships_for_investor(db, intent, investor_id)
    team_members = get_vc_team_members_db(db, investor_id)
    score = score_vc_match(investor, intent, relationships, team_members, retrieval_scores.get(investor_id, 0), competitor_hits.get(investor_id, []))
    return _match_result(investor, score, relationships)


def _relationships_for_investor(db: Session, intent: FounderIntent, investor_id: str) -> list[RelationshipClassification]:
    portfolio = get_enriched_portfolio_for_investor_db(db, investor_id)
    return [_relationship_for_company(db, intent, company) for company in portfolio]


def _relationship_for_company(
    db: Session,
    intent: FounderIntent,
    company: dict[str, Any],
) -> RelationshipClassification:
    company_id = company.get("canonical_company_id") or company.get("id")
    analysis = get_company_analysis_db(db, str(company_id)) if company_id else None
    return classify_portfolio_company(intent, company, analysis)


def _match_result(
    investor: dict[str, Any],
    score: ScoreBreakdown,
    relationships: list[RelationshipClassification],
) -> VCMatchResult:
    return VCMatchResult(
        rank=0,
        investor_id=UUID(str(investor["id"])),
        external_vc_id=_optional_int(investor.get("external_vc_id")),
        slug=_slug(investor),
        name=str(investor.get("canonical_name") or "Unknown investor"),
        website=investor.get("website_url") or investor.get("website"),
        overall_score=score.overall_score,
        score_band=score.score_band,
        retrieval_score=score.retrieval_score,
        direct_vc_fit_score=score.direct_vc_fit_score,
        semantic_thesis_score=score.semantic_thesis_score,
        portfolio_network_score=score.portfolio_network_score,
        commercial_access_score=score.commercial_access_score,
        team_relevance_score=score.team_relevance_score,
        data_confidence_score=score.data_confidence_score,
        competitor_penalty=score.competitor_penalty,
        max_competition_risk_score=score.max_competition_risk_score,
        explanation=generate_explanation(score, relationships),
        positive_signals=score.positive_signals,
        negative_signals=score.negative_signals,
        risks=score.risks,
        portfolio_opportunities=_portfolio_opportunities(relationships),
    )


def _portfolio_opportunities(relationships: list[RelationshipClassification]) -> list[PortfolioOpportunityResult]:
    ordered = sorted(relationships, key=lambda item: max(item.fit_score, item.competition_risk_score), reverse=True)
    return [_portfolio_opportunity(item) for item in ordered if item.relationship_type != "irrelevant"][:8]


def _portfolio_opportunity(item: RelationshipClassification) -> PortfolioOpportunityResult:
    return PortfolioOpportunityResult(
        company_id=_optional_uuid(item.company_id),
        name=item.name,
        relationship_type=item.relationship_type,
        fit_score=item.fit_score,
        competition_risk_score=item.competition_risk_score,
        reasoning=item.reasoning,
    )


def _ranked_results(results: list[VCMatchResult], limit: int) -> list[VCMatchResult]:
    limited = results[:limit]
    for rank, result in enumerate(limited, start=1):
        result.rank = rank
    return limited


def _initial_warnings(db: Session, request: FounderMatchRequest) -> list[str]:
    warnings: list[str] = []
    if retrieval_document_count(db) == 0:
        warnings.append("Retrieval index is empty; used enriched structured fields only.")
    return warnings


def _use_unenriched_fallback(
    db: Session,
    request: FounderMatchRequest,
    warnings: list[str],
) -> bool:
    completed_count = count_completed_investors(db)
    if completed_count > 0:
        return False
    if not request.allow_unenriched_fallback:
        return False
    warnings.append("No enriched investors were available; used unenriched structured fallback.")
    return True


def _data_scope(use_fallback: bool) -> str:
    if use_fallback:
        return "unenriched_fallback"
    return "enriched_only"


def _intent_warnings(intent: FounderIntent) -> list[str]:
    if is_sparse_intent(intent):
        return ["Founder profile is sparse; ranking confidence is limited."]
    return []


def _empty_response(warnings: list[str]) -> FounderMatchResponse:
    return FounderMatchResponse(
        count=0,
        data_scope="enriched_only",
        top_vcs=[],
        warnings=[*warnings, "No enriched investors available for matching."],
    )


def _slug(investor: dict[str, Any]) -> str | None:
    slug = investor.get("slug")
    if slug:
        return str(slug)
    name = str(investor.get("canonical_name") or "")
    generated = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return generated or None


def _optional_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
