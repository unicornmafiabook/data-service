import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.importer.dedupe import group_and_merge
from app.importer.normalise import normalize_name
from app.importer.parsers import (
    parse_source_1_row,
    parse_source_2_row,
    parse_source_3_row,
    parse_source_4_row,
)

REPO_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_DIR / "data" / "raw"

SOURCE_CONFIG = [
    ("source_1", DATA_DIR / "source1.csv", parse_source_1_row),
    ("source_2", DATA_DIR / "source2.csv", parse_source_2_row),
    ("source_3", DATA_DIR / "source3.csv", parse_source_3_row),
    ("source_4", DATA_DIR / "source4.csv", parse_source_4_row),
]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def load_all_records() -> list[dict]:
    records = []
    for source_name, path, parser in SOURCE_CONFIG:
        if not path.exists():
            raise FileNotFoundError(f"Missing {source_name}: {path}")
        df = read_csv(path)
        for _, row in df.iterrows():
            parsed = parser(row)
            if parsed.get("name"):
                records.append(parsed)
    return records


def reset_imported_data(db: Session):
    db.execute(text("TRUNCATE investor_company_relationships, investor_sources, companies, investors RESTART IDENTITY CASCADE;"))


def insert_investor(db: Session, investor: dict) -> str:
    sql = text("""
        INSERT INTO investors (
            canonical_name, normalized_name, website, domain, investor_type, status,
            hq_city, hq_country, hq_address, stages, sectors, geographies,
            first_cheque_min, first_cheque_max, first_cheque_currency,
            capital_under_management, fund_size_raw, deal_count_raw, funds_raw_json,
            description, investment_thesis, source_names, source_count,
            dedupe_key, dedupe_confidence, needs_review, raw_combined
        )
        VALUES (
            :canonical_name, :normalized_name, :website, :domain, :investor_type, :status,
            :hq_city, :hq_country, :hq_address, :stages, :sectors, :geographies,
            :first_cheque_min, :first_cheque_max, :first_cheque_currency,
            :capital_under_management, :fund_size_raw, :deal_count_raw, CAST(:funds_raw_json AS jsonb),
            :description, :investment_thesis, :source_names, :source_count,
            :dedupe_key, :dedupe_confidence, :needs_review, CAST(:raw_combined AS jsonb)
        )
        RETURNING id;
    """)
    params = {
        **investor,
        "funds_raw_json": json.dumps(investor.get("funds_raw_json") or {}),
        "raw_combined": json.dumps(investor.get("raw_combined") or {}),
    }
    result = db.execute(sql, params)
    return str(result.scalar())


def insert_source_record(db: Session, investor_id: str, source_record: dict):
    db.execute(text("""
        INSERT INTO investor_sources (
            investor_id, source_name, source_row_id, original_name, original_website, raw_data
        )
        VALUES (
            :investor_id, :source_name, :source_row_id, :original_name, :original_website, CAST(:raw_data AS jsonb)
        );
    """), {
        "investor_id": investor_id,
        "source_name": source_record["source_name"],
        "source_row_id": source_record.get("source_row_id"),
        "original_name": source_record.get("name"),
        "original_website": source_record.get("website"),
        "raw_data": json.dumps(source_record.get("raw_data") or {}),
    })


def get_or_create_company(db: Session, company_name: str) -> str:
    normalized_name = normalize_name(company_name)
    existing = db.execute(text("""
        SELECT id FROM companies WHERE normalized_name = :normalized_name LIMIT 1;
    """), {"normalized_name": normalized_name}).scalar()
    if existing:
        return str(existing)
    result = db.execute(text("""
        INSERT INTO companies (canonical_name, normalized_name)
        VALUES (:canonical_name, :normalized_name)
        RETURNING id;
    """), {"canonical_name": company_name, "normalized_name": normalized_name})
    return str(result.scalar())


def link_investor_company(db: Session, investor_id: str, company_id: str, source: str = "import"):
    db.execute(text("""
        INSERT INTO investor_company_relationships (investor_id, company_id, source, confidence_score)
        VALUES (:investor_id, :company_id, :source, 0.7)
        ON CONFLICT (investor_id, company_id) DO NOTHING;
    """), {"investor_id": investor_id, "company_id": company_id, "source": source})


def import_vc_data(db: Session, dry_run: bool = False, reset: bool = False) -> dict:
    records = load_all_records()
    merged_investors = group_and_merge(records)
    stats = {
        "raw_records": len(records),
        "merged_investors": len(merged_investors),
        "portfolio_company_mentions": sum(len(i.get("portfolio_companies", [])) for i in merged_investors),
        "dry_run": dry_run,
        "reset": reset,
    }
    if dry_run:
        return stats
    if reset:
        reset_imported_data(db)
    imported = 0
    for investor in merged_investors:
        investor_id = insert_investor(db, investor)
        for source_record in investor["source_records"]:
            insert_source_record(db, investor_id, source_record)
        for company_name in investor.get("portfolio_companies", []):
            company_id = get_or_create_company(db, company_name)
            link_investor_company(db, investor_id, company_id)
        imported += 1
        if imported % 250 == 0:
            db.commit()
    db.commit()
    stats["imported_investors"] = imported
    return stats
