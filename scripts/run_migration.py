"""Run a SQL migration file against the configured database.

Usage:
    python scripts/run_migration.py                          # runs migration_v2_expanded_fields.sql
    python scripts/run_migration.py --file sql/schema.sql   # runs any specific file
"""
import argparse
from pathlib import Path
from sqlalchemy import text
from app.db.session import engine

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MIGRATION = REPO_ROOT / "sql" / "migration_v2_expanded_fields.sql"


def run(sql_file: Path):
    resolved_sql_file = sql_file.resolve()
    sql = resolved_sql_file.read_text()
    with engine.begin() as conn:
        conn.execute(text(sql))
    print(f"Applied: {resolved_sql_file.relative_to(REPO_ROOT)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_MIGRATION)
    args = parser.parse_args()
    run(args.file)


if __name__ == "__main__":
    main()
