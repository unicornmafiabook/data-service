"""Bulk-import VC CSVs into the wide ``investors`` table.

Reads the four source CSVs under ``data/raw/``, parses each row,
dedupes across sources, and persists one ``Investor`` row per deduped
firm. Populates the full schema the public ``InvestorSummary`` /
``InvestorDetail`` API contracts surface.
"""

import re
from pathlib import Path
from typing import Any

import pandas as pd
from sqlmodel import Session, delete

from app.importer.dedupe import group_and_merge
from app.importer.parsers import (
    parse_source_1_row,
    parse_source_2_row,
    parse_source_3_row,
    parse_source_4_row,
)
from app.investors.models import Investor

REPO_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_DIR / "data" / "raw"

SOURCE_CONFIG = [
    ("source_1", DATA_DIR / "source1.csv", parse_source_1_row),
    ("source_2", DATA_DIR / "source2.csv", parse_source_2_row),
    ("source_3", DATA_DIR / "source3.csv", parse_source_3_row),
    ("source_4", DATA_DIR / "source4.csv", parse_source_4_row),
]

# Maps the importer's normalised stage tokens back to the public
# ``InvestmentStage`` enum values (mirrors the SQL backfill from
# migration_enrichment_contract.sql).
STAGE_TO_ROUND = {
    "pre_seed": "Pre-Seed",
    "seed": "Seed",
    "series_a": "Series A",
    "series_b": "Series B",
    "series_c": "Series C",
    "growth": "Growth",
}

VALID_STATUSES = {"Active", "Inactive"}

COMMIT_BATCH_SIZE = 250


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def load_all_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source_name, path, parser in SOURCE_CONFIG:
        if not path.exists():
            raise FileNotFoundError(f"Missing {source_name}: {path}")
        df = read_csv(path)
        for _, row in df.iterrows():
            parsed = parser(row)
            if parsed.get("name"):
                records.append(parsed)
    return records


def _slug_from_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    slug = re.sub(r"\s+", "-", cleaned).strip("-").lower()
    return slug or "investor"


def _disambiguate_slug(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


def _location_from_hq(merged: dict[str, Any]) -> str | None:
    city = merged.get("hq_city") or None
    country = merged.get("hq_country") or None
    if city and country:
        return f"{city}, {country}"
    return country or city


def _first_value(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]


def _rounds_from_stages(stages: list[str] | None) -> list[str]:
    if not stages:
        return []
    mapped = {STAGE_TO_ROUND[stage] for stage in stages if stage in STAGE_TO_ROUND}
    return sorted(mapped)


def _status_value(status: str | None) -> str | None:
    if not status:
        return None
    return status if status in VALID_STATUSES else None


def _row_from_merged(merged: dict[str, Any], slug: str) -> Investor:
    canonical_name = merged["canonical_name"]
    sectors = merged.get("sectors") or []
    geographies = merged.get("geographies") or []
    stages = merged.get("stages") or []
    return Investor(
        canonical_name=canonical_name,
        slug=slug,
        website=merged.get("website") or None,
        website_url=merged.get("website") or None,
        domain=merged.get("domain") or None,
        investor_type=merged.get("investor_type") or None,
        status=_status_value(merged.get("status")),
        hq_city=merged.get("hq_city") or None,
        hq_country=merged.get("hq_country") or None,
        location=_location_from_hq(merged),
        stages=stages,
        rounds=_rounds_from_stages(stages),
        sector=_first_value(sectors),
        sectors=sectors,
        geographies=geographies,
        geo_focus=geographies,
        description=merged.get("description") or None,
        investment_thesis=merged.get("investment_thesis") or None,
        first_cheque_min=merged.get("first_cheque_min"),
        first_cheque_max=merged.get("first_cheque_max"),
        first_cheque_currency=merged.get("first_cheque_currency") or None,
        ticket_size_min=merged.get("first_cheque_min"),
        ticket_size_max=merged.get("first_cheque_max"),
        source_count=int(merged.get("source_count") or 1),
        source_names=merged.get("source_names") or [],
        dedupe_confidence=merged.get("dedupe_confidence"),
        needs_review=bool(merged.get("needs_review")),
    )


def reset_imported_data(db: Session) -> None:
    db.execute(delete(Investor))


def import_vc_data(
    db: Session,
    *,
    dry_run: bool = False,
    reset: bool = False,
) -> dict[str, Any]:
    records = load_all_records()
    merged_investors = group_and_merge(records)
    stats: dict[str, Any] = {
        "raw_records": len(records),
        "merged_investors": len(merged_investors),
        "dry_run": dry_run,
        "reset": reset,
    }
    if dry_run:
        return stats
    if reset:
        reset_imported_data(db)
    imported = 0
    taken_slugs: set[str] = set()
    for merged in merged_investors:
        slug = _disambiguate_slug(_slug_from_name(merged["canonical_name"]), taken_slugs)
        taken_slugs.add(slug)
        db.add(_row_from_merged(merged, slug))
        imported += 1
        if imported % COMMIT_BATCH_SIZE == 0:
            db.commit()
    db.commit()
    stats["imported_investors"] = imported
    return stats
