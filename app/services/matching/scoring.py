from typing import Any

from pydantic import BaseModel, Field

from app.services.matching.founder_intent import FounderIntent
from app.services.matching.relationship_classifier import RelationshipClassification


class ScoreBreakdown(BaseModel):
    overall_score: float
    score_band: str
    retrieval_score: float
    direct_vc_fit_score: float
    semantic_thesis_score: float
    portfolio_network_score: float
    commercial_access_score: float
    team_relevance_score: float
    data_confidence_score: float
    competitor_penalty: float
    max_competition_risk_score: float
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


def score_vc_match(
    investor: dict[str, Any],
    intent: FounderIntent,
    relationships: list[RelationshipClassification],
    team_members: list[dict[str, Any]],
    retrieval_score: float,
    competitor_hits: list[str],
) -> ScoreBreakdown:
    direct_score = _direct_vc_fit(investor, intent)
    semantic_score = _semantic_thesis_score(investor, intent)
    team_score = _team_relevance(team_members, intent)
    portfolio_score = _portfolio_network_score(relationships)
    commercial_score = _commercial_access_score(relationships, team_score)
    confidence_score = _data_confidence_score(investor, relationships)
    max_competition = _max_competition(relationships, competitor_hits)
    penalty = _competitor_penalty(max_competition)
    overall = _overall_score(direct_score, semantic_score, portfolio_score, commercial_score, team_score, confidence_score, retrieval_score, penalty, max_competition)
    return _breakdown(overall, retrieval_score, direct_score, semantic_score, portfolio_score, commercial_score, team_score, confidence_score, penalty, max_competition, investor, relationships)


def _direct_vc_fit(investor: dict[str, Any], intent: FounderIntent) -> float:
    score = 0.0
    score += 22 if _contains(investor.get("rounds") or investor.get("stages"), intent.stage) else 0
    score += 22 if _overlaps(investor.get("sectors"), _list(intent.company_category)) else 0
    score += 14 if _overlaps(investor.get("geo_focus") or investor.get("geographies") or investor.get("location"), intent.geographies) else 0
    score += 20 if _raise_fits(investor, intent.raise_amount) else 0
    score += 8 if str(investor.get("status")).lower() == "active" else 0
    score += _tendency_score(investor)
    score += 6 if investor.get("enrichment_status") == "completed" else 0
    score -= 30 if str(investor.get("status")).lower() == "inactive" else 0
    return _clamp(score)


def _semantic_thesis_score(investor: dict[str, Any], intent: FounderIntent) -> float:
    investor_text = _investor_text(investor)
    score = 0.0
    score += 25 if _term_in_text(intent.company_category, investor_text) else 0
    score += 20 if _term_in_text(intent.business_model, investor_text) else 0
    score += 20 if _any_term_in_text([*intent.target_customers, *intent.target_buyers], investor_text) else 0
    score += 20 * _overlap_ratio(intent.keywords, investor_text)
    score += 15 if investor.get("revealed_thesis") and _overlap_ratio(intent.keywords, str(investor.get("revealed_thesis")).lower()) > 0 else 0
    return _clamp(score)


def _portfolio_network_score(relationships: list[RelationshipClassification]) -> float:
    if not relationships:
        return 25
    positives = [item.fit_score for item in relationships if item.relationship_type != "competitor" and item.fit_score > 0]
    competition = sorted([item.competition_risk_score for item in relationships], reverse=True)
    raw = _clamp(0.75 * _average(positives[:3]) + 0.25 * _average(positives) - 0.65 * _first_score(competition) - 0.35 * _average(competition[:2]))
    # floor at 15 when relationships exist but classifications are ambiguous and no high competition risk
    return max(raw, 15) if _first_score(competition) < 50 else raw


def _commercial_access_score(relationships: list[RelationshipClassification], team_score: float) -> float:
    if not relationships:
        return 25
    clients = _scores_for(relationships, "potential_client")
    suppliers = _scores_for(relationships, "potential_supplier")
    partners = [*_scores_for(relationships, "complement"), *_scores_for(relationships, "partner")]
    raw = _clamp(0.50 * _average(clients[:3]) + 0.20 * _average(suppliers[:3]) + 0.20 * _average(partners[:3]) + 0.10 * team_score)
    # floor at 15 when relationships exist but yield weak commercial signals
    return max(raw, 15)


def _team_relevance(team_members: list[dict[str, Any]], intent: FounderIntent) -> float:
    if not team_members:
        return 50
    text = " ".join(_member_text(member) for member in team_members)
    overlap = _overlap_ratio([*intent.keywords, *intent.competitor_categories], text)
    contact_bonus = 10 if any(member.get("email") or member.get("linkedin") for member in team_members) else 0
    return _clamp(45 + 45 * overlap + contact_bonus)


def _data_confidence_score(investor: dict[str, Any], relationships: list[RelationshipClassification]) -> float:
    score = 50.0
    score += 25 if investor.get("enrichment_status") == "completed" else 0
    score += 15 if relationships else 0
    score += 5 if int(investor.get("source_count") or 0) >= 2 else 0
    score += 5 if not investor.get("needs_review") else 0
    return _clamp(score)


def _overall_score(
    direct_score: float,
    semantic_score: float,
    portfolio_score: float,
    commercial_score: float,
    team_score: float,
    confidence_score: float,
    retrieval_score: float,
    penalty: float,
    max_competition: float,
) -> float:
    base_score = 0.20 * direct_score + 0.20 * semantic_score + 0.25 * portfolio_score
    base_score += 0.15 * commercial_score + 0.10 * team_score + 0.05 * confidence_score + 0.05 * retrieval_score
    return round(_clamp(min(base_score - penalty, _max_allowed_score(max_competition))), 1)


def _breakdown(
    overall_score: float,
    retrieval_score: float,
    direct_score: float,
    semantic_score: float,
    portfolio_score: float,
    commercial_score: float,
    team_score: float,
    confidence_score: float,
    penalty: float,
    max_competition: float,
    investor: dict[str, Any],
    relationships: list[RelationshipClassification],
) -> ScoreBreakdown:
    return ScoreBreakdown(
        overall_score=overall_score,
        score_band=_score_band(overall_score),
        retrieval_score=round(retrieval_score, 1),
        direct_vc_fit_score=round(direct_score, 1),
        semantic_thesis_score=round(semantic_score, 1),
        portfolio_network_score=round(portfolio_score, 1),
        commercial_access_score=round(commercial_score, 1),
        team_relevance_score=round(team_score, 1),
        data_confidence_score=round(confidence_score, 1),
        competitor_penalty=penalty,
        max_competition_risk_score=round(max_competition, 1),
        positive_signals=_positive_signals(investor, relationships),
        negative_signals=_negative_signals(investor, relationships),
        risks=_risks(max_competition),
    )


def _competitor_penalty(max_competition: float) -> float:
    if max_competition >= 90:
        return 70
    if max_competition >= 80:
        return 55
    if max_competition >= 70:
        return 40
    if max_competition >= 60:
        return 25
    if max_competition >= 50:
        return 12
    return 0


def _max_allowed_score(max_competition: float) -> float:
    if max_competition >= 90:
        return 35
    if max_competition >= 80:
        return 45
    if max_competition >= 70:
        return 60
    if max_competition >= 65:
        return 72
    return 100


def _score_band(score: float) -> str:
    if score >= 80:
        return "strong_fit"
    if score >= 65:
        return "good_fit"
    if score >= 50:
        return "possible_fit"
    if score >= 35:
        return "weak_fit"
    return "poor_fit"


def _positive_signals(investor: dict[str, Any], relationships: list[RelationshipClassification]) -> list[str]:
    signals = ["Investor has completed enrichment data."] if investor.get("enrichment_status") == "completed" else []
    signals.extend(_relationship_signals(relationships))
    return signals[:5]


def _negative_signals(investor: dict[str, Any], relationships: list[RelationshipClassification]) -> list[str]:
    signals = []
    if str(investor.get("status")).lower() == "inactive":
        signals.append("Investor appears inactive.")
    if not relationships:
        signals.append("No enriched portfolio company data available.")
    return signals


def _relationship_signals(relationships: list[RelationshipClassification]) -> list[str]:
    return [f"{item.name} may be a {item.relationship_type.replace('_', ' ')}." for item in relationships if item.fit_score >= 35 and item.relationship_type != "competitor"]


def _risks(max_competition: float) -> list[str]:
    if max_competition >= 70:
        return ["Likely direct competitor found in the enriched portfolio."]
    if max_competition >= 50:
        return ["Some portfolio companies overlap with the founder's market."]
    return []


def _max_competition(relationships: list[RelationshipClassification], competitor_hits: list[str]) -> float:
    relationship_risk = max([item.competition_risk_score for item in relationships], default=0)
    retrieval_risk = 65 if competitor_hits else 0
    return max(relationship_risk, retrieval_risk)


def _scores_for(relationships: list[RelationshipClassification], relationship_type: str) -> list[float]:
    return sorted([item.fit_score for item in relationships if item.relationship_type == relationship_type], reverse=True)


def _raise_fits(investor: dict[str, Any], raise_amount: float | None) -> bool:
    if raise_amount is None:
        return False
    minimum = float(investor.get("ticket_size_min") or investor.get("first_cheque_min") or 0)
    maximum = float(investor.get("ticket_size_max") or investor.get("first_cheque_max") or 1000000000000)
    return minimum <= raise_amount <= maximum


def _tendency_score(investor: dict[str, Any]) -> float:
    tendency = str(investor.get("tendency") or investor.get("investment_tendency") or "").lower()
    if tendency == "lead":
        return 8
    if tendency == "unsure":
        return 3
    return 0


def _investor_text(investor: dict[str, Any]) -> str:
    values = [investor.get("stated_thesis"), investor.get("revealed_thesis"), investor.get("short_description")]
    values.extend(_list(investor.get("sectors")))
    return " ".join(str(value).lower() for value in values if value)


def _member_text(member: dict[str, Any]) -> str:
    values = [member.get("name"), member.get("position"), member.get("description")]
    values.extend(_list(member.get("expertise")))
    return " ".join(str(value).lower() for value in values if value)


def _overlap_ratio(needles: list[str], haystack: str) -> float:
    cleaned = [needle.lower() for needle in needles if needle]
    if not cleaned:
        return 0
    matches = sum(1 for needle in cleaned if needle in haystack)
    return matches / max(len(cleaned), 1)


def _overlaps(value: Any, candidates: list[str]) -> bool:
    values = {item.lower() for item in _list(value)}
    return any(candidate.lower() in values for candidate in candidates)


def _contains(value: Any, candidate: str | None) -> bool:
    if not candidate:
        return False
    return candidate.lower() in {item.lower() for item in _list(value)}


def _term_in_text(term: str | None, text: str) -> bool:
    return bool(term and term.lower() in text)


def _any_term_in_text(terms: list[str], text: str) -> bool:
    for term in terms:
        if not term:
            continue
        lowered = term.lower()
        if lowered in text:
            return True
        # also check each word of a multi-word term individually
        if any(word in text for word in lowered.split() if len(word) > 3):
            return True
    return False


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if not value:
        return []
    return [str(value)]


def _average(values: list[float]) -> float:
    if not values:
        return 0
    return sum(values) / len(values)


def _first_score(values: list[float]) -> float:
    if not values:
        return 0
    return values[0]


def _clamp(value: float) -> float:
    return max(0, min(100, value))
