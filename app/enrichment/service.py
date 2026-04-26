"""Service layer for the enrichment context.

Skeleton: ``EnrichmentService`` is instantiated with a SQLModel
``Session`` and exposes the read + write operations the routes call.
Bodies are filled in the GREEN phase.
"""

from sqlmodel import Session

from app.enrichment.schemas import DeepEnrichedVC, EnrichmentSnapshot


class InvestorNotFoundError(Exception):
    """Raised when no investor matches the requested external VC id."""


class EnrichmentAlreadyExistsError(Exception):
    """Raised when ``create_enrichment`` would conflict with an existing row."""


class EnrichmentNotFoundError(Exception):
    """Raised when ``update_enrichment`` finds no existing record to replace."""


class EnrichmentService:
    """Read and write operations over the enrichment-owned tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_snapshot(self, external_vc_id: int) -> EnrichmentSnapshot:
        """Return the full enrichment snapshot for a VC.

        Raises
        ------
        InvestorNotFoundError
            When no investor has the supplied ``external_vc_id``.
        """
        raise NotImplementedError

    def create_enrichment(
        self,
        external_vc_id: int,
        payload: DeepEnrichedVC,
    ) -> EnrichmentSnapshot:
        """Insert enrichment data for a VC and return the resulting snapshot.

        Raises
        ------
        InvestorNotFoundError
            When no investor matches ``external_vc_id``.
        EnrichmentAlreadyExistsError
            When an enrichment record already exists for this VC.
        """
        raise NotImplementedError

    def update_enrichment(
        self,
        external_vc_id: int,
        payload: DeepEnrichedVC,
    ) -> EnrichmentSnapshot:
        """Replace enrichment data for a VC and return the resulting snapshot.

        Raises
        ------
        InvestorNotFoundError
            When no investor matches ``external_vc_id``.
        EnrichmentNotFoundError
            When no existing enrichment record exists to replace.
        """
        raise NotImplementedError
