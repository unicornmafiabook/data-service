from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session
from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Legacy alias — still used by health.py and scripts/import_vc_data.py.
# Those callers use raw SQL only (.execute / .query) so a plain
# SQLAlchemy Session is fine for them.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    """FastAPI dependency: yields a SQLModel Session (has .exec())."""
    with Session(engine) as db:
        yield db
