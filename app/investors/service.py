"""Service layer for the investors context.

Skeleton: ``InvestorsService`` is instantiated with a SQLModel
``Session`` and exposes the CRUD + lookup methods the routes (and
other contexts) call. Bodies are filled in the GREEN phase.
"""

from uuid import UUID

from sqlmodel import Session

from app.investors.schemas import VC, InvestorCreate


class InvestorNotFoundError(Exception):
    """Raised when no investor matches the given lookup."""


class InvestorAlreadyExistsError(Exception):
    """Raised when ``create`` would conflict with an existing investor."""


class InvestorsService:
    """Read/write operations over the ``investors`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, payload: InvestorCreate) -> VC:
        """Insert an investor and return its public ``VC`` representation."""
        raise NotImplementedError

    def get_by_id(self, investor_id: UUID) -> VC:
        """Return the investor whose primary key is ``investor_id``."""
        raise NotImplementedError

    def get_by_external_vc_id(self, external_vc_id: int) -> VC:
        """Return the investor whose ``external_vc_id`` matches."""
        raise NotImplementedError

    def get_by_slug(self, slug: str) -> VC:
        """Return the investor whose ``slug`` matches."""
        raise NotImplementedError

    def list_paginated(self, *, limit: int, offset: int) -> list[VC]:
        """Return a page of investors ordered by ``canonical_name``."""
        raise NotImplementedError
