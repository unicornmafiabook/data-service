"""Shared pytest fixtures.

In-memory SQLite per test gives a fresh schema and isolates state.
SQLModel's metadata is populated by importing every per-context
``models`` module at module level; ``create_all`` then creates the
schema for the tables we own.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

import app.enrichment.models  # noqa: F401  — populates SQLModel.metadata
import app.investors.models  # noqa: F401  — populates SQLModel.metadata
from app.db.session import get_db
from app.main import app


class _SessionOverride:
    """Callable used by FastAPI to resolve ``get_db`` to the test session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __call__(self) -> Iterator[Session]:
        yield self._session


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Function-scoped in-memory SQLite engine with a fresh schema."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A SQLModel session bound to the test engine, rolled back at end."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    """FastAPI ``TestClient`` with ``get_db`` overridden to yield ``session``."""
    app.dependency_overrides[get_db] = _SessionOverride(session)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
