"""
Clean investors.sectors: if any single element has more than 3 words,
set the entire sectors array to [] for that row.
"""
import argparse
from sqlalchemy import text
from app.db.session import engine

PREVIEW_SQL = """
SELECT id, canonical_name, sectors
FROM investors
WHERE EXISTS (
    SELECT 1 FROM unnest(sectors) s
    WHERE array_length(regexp_split_to_array(s, '_'), 1) > 3
)
ORDER BY canonical_name;
"""

UPDATE_SQL = """
UPDATE investors
SET sectors = '{}'
WHERE EXISTS (
    SELECT 1 FROM unnest(sectors) s
    WHERE array_length(regexp_split_to_array(s, '_'), 1) > 3
);
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--run", dest="dry_run", action="store_false")
    args = parser.parse_args()

    with engine.connect() as conn:
        rows = conn.execute(text(PREVIEW_SQL)).mappings().all()

    print(f"Rows affected: {len(rows)}")
    print()
    for r in rows[:30]:
        print(f"  {r['canonical_name'][:40]:<40}  {r['sectors']}")
    if len(rows) > 30:
        print(f"  ... and {len(rows) - 30} more")

    if args.dry_run:
        print("\nDry run — pass --run to apply.")
        return

    with engine.begin() as conn:
        result = conn.execute(text(UPDATE_SQL))
    print(f"\nUpdated {result.rowcount} rows.")


if __name__ == "__main__":
    main()
