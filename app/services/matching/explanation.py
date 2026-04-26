from app.services.matching.relationship_classifier import RelationshipClassification
from app.services.matching.scoring import ScoreBreakdown


def generate_explanation(score: ScoreBreakdown, relationships: list[RelationshipClassification]) -> str:
    if score.max_competition_risk_score >= 70:
        return _competitor_explanation(score, relationships)
    if score.overall_score >= 65:
        return _positive_explanation(score, relationships)
    if score.data_confidence_score < 75:
        return _low_confidence_explanation()
    return _general_explanation(score)


def _competitor_explanation(score: ScoreBreakdown, relationships: list[RelationshipClassification]) -> str:
    competitor = _top_competitor(relationships)
    name = competitor.name if competitor else "an enriched portfolio company"
    return (
        "This VC has some fit signals, but is ranked lower because "
        f"{name} looks like a likely direct competitor. "
        "That competitor risk outweighs positive portfolio or thesis overlap."
    )


def _positive_explanation(score: ScoreBreakdown, relationships: list[RelationshipClassification]) -> str:
    opportunities = _opportunity_names(relationships)
    if opportunities:
        return (
            f"This VC is a {score.score_band.replace('_', ' ')} because its enriched thesis and profile align with "
            f"the founder inputs, and its portfolio includes relevant companies such as {opportunities}."
        )
    return (
        f"This VC is a {score.score_band.replace('_', ' ')} because its enriched profile, stage, sector, "
        "and thesis signals align with the founder inputs."
    )


def _low_confidence_explanation() -> str:
    return "This VC appears directionally relevant, but the ranking is lower confidence because enriched supporting data is limited."


def _general_explanation(score: ScoreBreakdown) -> str:
    return (
        f"This VC is ranked as a {score.score_band.replace('_', ' ')} based on the available enriched thesis, "
        "portfolio, team, and retrieval signals."
    )


def _top_competitor(relationships: list[RelationshipClassification]) -> RelationshipClassification | None:
    competitors = [item for item in relationships if item.relationship_type == "competitor"]
    if not competitors:
        return None
    return max(competitors, key=lambda item: item.competition_risk_score)


def _opportunity_names(relationships: list[RelationshipClassification]) -> str:
    names = [item.name for item in relationships if item.relationship_type != "competitor" and item.fit_score >= 35]
    return ", ".join(names[:3])
