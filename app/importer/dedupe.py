from collections import defaultdict
from typing import Any


def get_dedupe_key(record: dict[str, Any]) -> str:
    if record.get("domain"):
        return f"domain:{record['domain']}"
    if record.get("normalized_name") and record.get("hq_country"):
        return f"name_country:{record['normalized_name']}:{record['hq_country'].lower()}"
    if record.get("normalized_name"):
        return f"name:{record['normalized_name']}"
    return f"unique:{record['source_name']}:{record.get('source_row_id')}"


def choose_best_text(values):
    values = [v for v in values if v is not None and str(v).strip()]
    if not values:
        return None
    return max(values, key=lambda x: len(str(x)))


def choose_best_name(values):
    values = [v for v in values if v is not None and str(v).strip()]
    if not values:
        return None
    return values[0]


def flatten_unique(records, key):
    values = []
    for record in records:
        values.extend(record.get(key) or [])
    return sorted(set(v for v in values if v))


def min_non_null(values):
    values = [v for v in values if v is not None]
    return min(values) if values else None


def max_non_null(values):
    values = [v for v in values if v is not None]
    return max(values) if values else None


def merge_records(records: list[dict[str, Any]], dedupe_key: str) -> dict[str, Any]:
    source_names = sorted(set(r["source_name"] for r in records))
    raw_combined = {}
    for r in records:
        raw_combined.setdefault(r["source_name"], [])
        raw_combined[r["source_name"]].append(r["raw_data"])

    return {
        "canonical_name": choose_best_name([r["name"] for r in records]),
        "normalized_name": choose_best_text([r["normalized_name"] for r in records]),
        "website": choose_best_text([r["website"] for r in records]),
        "domain": choose_best_text([r["domain"] for r in records]),
        "investor_type": choose_best_text([r["investor_type"] for r in records]),
        "status": choose_best_text([r["status"] for r in records]),
        "hq_city": choose_best_text([r["hq_city"] for r in records]),
        "hq_country": choose_best_text([r["hq_country"] for r in records]),
        "hq_address": choose_best_text([r["hq_address"] for r in records]),
        "stages": flatten_unique(records, "stages"),
        "sectors": flatten_unique(records, "sectors"),
        "geographies": flatten_unique(records, "geographies"),
        "first_cheque_min": min_non_null([r["first_cheque_min"] for r in records]),
        "first_cheque_max": max_non_null([r["first_cheque_max"] for r in records]),
        "first_cheque_currency": choose_best_text([r["first_cheque_currency"] for r in records]),
        "capital_under_management": max_non_null([r["capital_under_management"] for r in records]),
        "fund_size_raw": choose_best_text([r["fund_size_raw"] for r in records]),
        "deal_count_raw": choose_best_text([r["deal_count_raw"] for r in records]),
        "funds_raw_json": choose_best_text([r["funds_raw_json"] for r in records]),
        "description": choose_best_text([r["description"] for r in records]),
        "investment_thesis": choose_best_text([r["investment_thesis"] for r in records]),
        "source_names": source_names,
        "source_count": len(source_names),
        "dedupe_key": dedupe_key,
        "dedupe_confidence": 0.98 if dedupe_key.startswith("domain:") else 0.8,
        "needs_review": False if dedupe_key.startswith("domain:") else True,
        "raw_combined": raw_combined,
        "portfolio_companies": flatten_unique(records, "portfolio_companies"),
        "source_records": records,
    }


def group_and_merge(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = defaultdict(list)
    for record in records:
        grouped[get_dedupe_key(record)].append(record)
    return [merge_records(group, key) for key, group in grouped.items()]
