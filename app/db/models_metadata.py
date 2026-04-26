from sqlmodel import SQLModel
from app.investors.models import Investor
from app.enrichment.models import PortfolioCompany, VCMember, VCFund, VCEnrichment

# Naming convention for database constraints
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Set naming convention for SQLModel metadata
metadata = SQLModel.metadata
metadata.naming_convention = NAMING_CONVENTION
