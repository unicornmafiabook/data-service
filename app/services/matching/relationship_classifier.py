from typing import Any

from pydantic import BaseModel

from app.schemas.matching import RelationshipType
from app.services.matching.founder_intent import FounderIntent


class RelationshipClassification(BaseModel):
    company_id: str | None = None
    name: str
    relationship_type: RelationshipType
    fit_score: float
    competition_risk_score: float
    customer_fit_score: float
    supplier_fit_score: float
    complementarity_score: float
    strategic_intro_score: float
    reasoning: str | None = None


def classify_portfolio_company(
    intent: FounderIntent,
    company: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> RelationshipClassification:
    company_text = _company_text(company, analysis)
    competition_risk = _competition_risk(intent, company, company_text)
    customer_fit = _overlap_score([*intent.target_customers, *intent.target_buyers], company_text)
    supplier_fit = _overlap_score(intent.complementary_categories, company_text)
    complementarity = _overlap_score([*intent.keywords, *intent.complementary_categories], company_text) * 0.8
    strategic_intro = max(customer_fit, complementarity) * 0.85
    relationship_type = _relationship_type(competition_risk, customer_fit, supplier_fit, complementarity, strategic_intro)
    return _classification(company, relationship_type, competition_risk, customer_fit, supplier_fit, complementarity, strategic_intro)


def _competition_risk(intent: FounderIntent, company: dict[str, Any], company_text: str) -> float:
    sector_overlap = _overlap_score(_company_sectors(intent), " ".join(_list(company.get("sectors"))))
    product_overlap = _overlap_score([*intent.keywords, *intent.competitor_categories], company_text)
    customer_overlap = _overlap_score([*intent.target_customers, *intent.target_buyers], company_text)
    business_overlap = _overlap_score(_list(intent.business_model), company_text)
    return _clamp(0.30 * sector_overlap + 0.30 * product_overlap + 0.25 * customer_overlap + 0.15 * business_overlap)


def _relationship_type(
    competition_risk: float,
    customer_fit: float,
    supplier_fit: float,
    complementarity: float,
    strategic_intro: float,
) -> RelationshipType:
    if competition_risk >= 70:
        return "competitor"
    if customer_fit >= 65:
        return "potential_client"
    if supplier_fit >= 65:
        return "potential_supplier"
    if complementarity >= 60:
        return "complement"
    if strategic_intro >= 60:
        return "partner"
    return "irrelevant"


def _classification(
    company: dict[str, Any],
    relationship_type: RelationshipType,
    competition_risk: float,
    customer_fit: float,
    supplier_fit: float,
    complementarity: float,
    strategic_intro: float,
) -> RelationshipClassification:
    positive_score = 0.40 * customer_fit + 0.20 * supplier_fit + 0.20 * complementarity + 0.20 * strategic_intro
    fit_score = _clamp(positive_score - 0.75 * competition_risk)
    return RelationshipClassification(
        company_id=str(company.get("canonical_company_id") or company.get("id")) if company.get("id") else None,
        name=str(company.get("name") or "Unknown company"),
        relationship_type=relationship_type,
        fit_score=round(fit_score, 1),
        competition_risk_score=round(competition_risk, 1),
        customer_fit_score=round(customer_fit, 1),
        supplier_fit_score=round(supplier_fit, 1),
        complementarity_score=round(complementarity, 1),
        strategic_intro_score=round(strategic_intro, 1),
        reasoning=_reasoning(relationship_type, competition_risk),
    )


def _company_text(company: dict[str, Any], analysis: dict[str, Any] | None) -> str:
    values = [company.get("name"), company.get("overview"), company.get("status"), company.get("company_size")]
    values.extend(_list(company.get("sectors")))
    values.extend(_analysis_values(analysis))
    return " ".join(str(value).lower() for value in values if value)


def _analysis_values(analysis: dict[str, Any] | None) -> list[str]:
    if not analysis:
        return []
    values = [analysis.get("overview"), analysis.get("market_category"), analysis.get("business_model")]
    values.extend(_list(analysis.get("products")))
    values.extend(_list(analysis.get("pain_points")))
    values.extend(_list(analysis.get("customer_segments")))
    values.extend(_list(analysis.get("buyer_personas")))
    return [str(value) for value in values if value]


def _overlap_score(needles: list[str], haystack: str) -> float:
    cleaned = [needle.lower() for needle in needles if needle]
    if not cleaned:
        return 0
    matches = sum(1 for needle in cleaned if needle in haystack)
    return _clamp(100 * matches / max(len(cleaned), 1))


def _company_sectors(intent: FounderIntent) -> list[str]:
    return [value for value in [intent.company_category, *intent.competitor_categories] if value]


def _reasoning(relationship_type: RelationshipType, competition_risk: float) -> str:
    if relationship_type == "competitor":
        return f"Likely competitor based on overlapping market, product, or customer signals ({competition_risk:.1f}/100 risk)."
    return f"Classified as {relationship_type.replace('_', ' ')} from enriched portfolio overlap."


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if not value:
        return []
    return [str(value)]


def _clamp(value: float) -> float:
    return max(0, min(100, value))
