import argparse

from app.db.session import SessionLocal
from app.services.import_service import import_vc_data


def main():
    parser = argparse.ArgumentParser(description="Import VC CSVs into Supabase Postgres.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and dedupe without writing.")
    parser.add_argument("--reset", action="store_true", help="Truncate imported data before importing.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = import_vc_data(db=db, dry_run=args.dry_run, reset=args.reset)
        print(stats)
    finally:
        db.close()


if __name__ == "__main__":
    main()
