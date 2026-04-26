"""Service layer for the enrichment context.

Skeleton: ``EnrichmentService`` is instantiated with a SQLModel
``Session`` and exposes the read operations the routes call. Bodies
are filled in the GREEN phase.
"""

from sqlmodel import Session

from app.enrichment.schemas import EnrichmentSnapshot


class InvestorNotFoundError(Exception):
    """Raised when no investor matches the requested external VC id."""


class EnrichmentService:
    """Read operations over the enrichment-owned tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_snapshot(self, external_vc_id: int) -> EnrichmentSnapshot:
        """
        Build the full enrichment snapshot for a VC.

        Parameters
        ----------
        external_vc_id : int
            Legacy integer VC id used by the frontend and the agent
            pipeline. Maps to ``investors.external_vc_id``.

        Returns
        -------
        EnrichmentSnapshot
            Investor summary plus members, funds, and portfolio
            companies (with their teams nested).

        Raises
        ------
        InvestorNotFoundError
            When no investor has the supplied ``external_vc_id``.
        """
        raise NotImplementedError
