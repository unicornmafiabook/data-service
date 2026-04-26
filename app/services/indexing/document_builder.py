import json
import re
from typing import Any

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


def build_investor_documents(
    investor: dict[str, Any],
    members: list[dict[str, Any]],
    funds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    investor_id = str(investor["id"])
    return [
        _investor_document(investor, funds, investor_id),
        _thesis_document(investor, investor_id, "vc_stated_thesis", "stated_thesis"),
        _thesis_document(investor, investor_id, "vc_revealed_thesis", "revealed_thesis"),
        _team_document(investor, members, investor_id),
    ]


def build_company_documents(company_id: str, company: dict[str, Any], team: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _company_document(company_id, company, team, "company_overview"),
        _company_document(company_id, company, team, "company_customer_profile"),
        _company_document(company_id, company, team, "company_product_profile"),
        _company_document(company_id, company, team, "company_market_profile"),
    ]


def build_relationship_document(
    relationship_id: str,
    investor_id: str,
    investor: dict[str, Any],
    company: dict[str, Any],
) -> dict[str, Any]:
    content = _lines([
        f"Investor: {investor.get('canonical_name')}",
        f"Portfolio company: {company.get('name')}",
        f"Investment stages: {_join(company.get('stage'))}",
        "Relationship source: enriched portfolio",
        f"Company overview: {company.get('overview')}",
    ])
    return _document("investor_company_relationship", relationship_id, investor_id, "investment_relationship", content, company)


def build_entity_edges(
    investor_id: str,
    company_id: str,
    company: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    edges = [_edge("investor", investor_id, "company", company_id, "investor_invested_in_company", company)]
    edges.extend(_company_edges(company_id, company, "sectors", "sector", "company_operates_in_sector"))
    edges.extend(_analysis_edges(company_id, company, analysis))
    return edges


def _investor_document(investor: dict[str, Any], funds: list[dict[str, Any]], investor_id: str) -> dict[str, Any]:
    content = _lines([
        f"VC: {investor.get('canonical_name')}",
        f"Short description: {investor.get('short_description') or investor.get('description')}",
        f"Long description: {investor.get('long_description')}",
        f"Rounds: {_join(investor.get('rounds') or investor.get('stages'))}",
        f"Sectors: {_join(investor.get('sectors'))}",
        f"Geo focus: {_join(investor.get('geo_focus') or investor.get('geographies'))}",
        f"Ticket size: {investor.get('ticket_size_min')} to {investor.get('ticket_size_max')}",
        f"Funds: {_funds_text(funds)}",
        f"Tendency: {investor.get('investment_tendency')}",
    ])
    return _document("investor", investor_id, investor_id, "vc_profile", content, investor)


def _thesis_document(investor: dict[str, Any], investor_id: str, document_type: str, field_name: str) -> dict[str, Any]:
    content = _lines([
        f"VC: {investor.get('canonical_name')}",
        f"Thesis: {investor.get(field_name) or investor.get('investment_thesis')}",
        f"Sectors: {_join(investor.get('sectors'))}",
        f"Stages: {_join(investor.get('rounds') or investor.get('stages'))}",
    ])
    return _document("investor", investor_id, investor_id, document_type, content, investor)


def _team_document(investor: dict[str, Any], members: list[dict[str, Any]], investor_id: str) -> dict[str, Any]:
    member_text = " ".join(_member_text(member) for member in members)
    content = _lines([
        f"VC: {investor.get('canonical_name')}",
        f"Team expertise: {member_text}",
    ])
    return _document("investor", investor_id, investor_id, "vc_team_profile", content, investor)


def _company_document(
    company_id: str,
    company: dict[str, Any],
    team: list[dict[str, Any]],
    document_type: str,
) -> dict[str, Any]:
    content = _company_content(company, team, document_type)
    return _document("company", company_id, None, document_type, content, company)


def _company_content(company: dict[str, Any], team: list[dict[str, Any]], document_type: str) -> str:
    team_text = " ".join(_member_text(member) for member in team)
    return _lines([
        f"Company: {company.get('name')}",
        f"Document type: {document_type}",
        f"Overview: {company.get('overview')}",
        f"Sectors: {_join(company.get('sectors'))}",
        f"Stage: {_join(company.get('stage'))}",
        f"Status: {company.get('status')}",
        f"Headquarters: {company.get('hq')}",
        f"Team: {team_text}",
    ])


def _document(
    entity_type: str,
    entity_id: str,
    investor_id: str | None,
    document_type: str,
    content: str,
    source: dict[str, Any],
) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "investor_id": investor_id,
        "document_type": document_type,
        "title": _title(source),
        "content": content,
        "keywords": _keywords(content),
        "sectors": _list(source.get("sectors")),
        "stages": _list(source.get("rounds") or source.get("stages") or source.get("stage")),
        "geographies": _list(source.get("geo_focus") or source.get("geographies") or source.get("hq")),
        "buyer_personas": [],
        "customer_segments": [],
        "metadata": json.dumps({"source": "enrichment_indexer"}),
    }


def _edge(
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    edge_type: str,
    source: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "target_type": target_type,
        "target_id": target_id,
        "edge_type": edge_type,
        "weight": 1.0,
        "evidence": source.get("overview"),
        "evidence_url": source.get("website_url"),
        "metadata": json.dumps({"source": "enrichment_indexer"}),
    }


def _company_edges(company_id: str, company: dict[str, Any], field_name: str, target_type: str, edge_type: str) -> list[dict[str, Any]]:
    return [_edge("company", company_id, target_type, value, edge_type, company) for value in _list(company.get(field_name))]


def _analysis_edges(
    company_id: str,
    company: dict[str, Any],
    analysis: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not analysis:
        return []
    edges = _analysis_edge_group(company_id, company, analysis, "buyer_personas", "buyer_persona", "company_targets_buyer_persona")
    edges.extend(_analysis_edge_group(company_id, company, analysis, "customer_segments", "customer_segment", "company_serves_customer_segment"))
    edges.extend(_analysis_edge_group(company_id, company, analysis, "pain_points", "pain_point", "company_solves_pain_point"))
    edges.extend(_analysis_edge_group(company_id, company, analysis, "integration_points", "category", "company_integrates_with_category"))
    edges.extend(_analysis_edge_group(company_id, company, analysis, "competitors", "category", "company_competes_in_category"))
    return edges


def _analysis_edge_group(
    company_id: str,
    company: dict[str, Any],
    analysis: dict[str, Any],
    field_name: str,
    target_type: str,
    edge_type: str,
) -> list[dict[str, Any]]:
    return [_edge("company", company_id, target_type, value, edge_type, company) for value in _list(analysis.get(field_name))]


def _member_text(member: dict[str, Any]) -> str:
    return _lines([
        str(member.get("name") or ""),
        str(member.get("position") or ""),
        _join(member.get("expertise")),
        str(member.get("description") or ""),
    ])


def _funds_text(funds: list[dict[str, Any]]) -> str:
    return "; ".join(_lines([str(fund.get("fund_name") or ""), str(fund.get("fund_size") or "")]) for fund in funds)


def _keywords(content: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", content.lower())
    return sorted(set(tokens))[:40]


def _title(source: dict[str, Any]) -> str | None:
    title = source.get("canonical_name") or source.get("name")
    if not title:
        return None
    return str(title)


def _join(value: Any) -> str:
    return ", ".join(_list(value))


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if not value:
        return []
    return [str(value)]


def _lines(values: list[str]) -> str:
    return "\n".join(value for value in values if value and value != "None")
