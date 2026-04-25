"""Run sql/migration_enrichment_contract.sql against the configured database."""
from pathlib import Path
from sqlalchemy import text
from app.db.session import engine

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "migration_enrichment_contract.sql"


def main():
    sql = SQL_FILE.read_text()
    with engine.begin() as conn:
        conn.execute(text(sql))
    print("Migration applied successfully.")


if __name__ == "__main__":
    main()
