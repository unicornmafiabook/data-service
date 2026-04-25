from pydantic import BaseModel


class InvestorCreate(BaseModel):
    canonical_name: str
    website: str | None = None
    investor_type: str | None = None
    status: str | None = None
    hq_city: str | None = None
    hq_country: str | None = None
    stages: list[str] = []
    sectors: list[str] = []
    geographies: list[str] = []
    description: str | None = None
    investment_thesis: str | None = None
    first_cheque_min: float | None = None
    first_cheque_max: float | None = None
    first_cheque_currency: str | None = None


class InvestorUpdate(BaseModel):
    canonical_name: str | None = None
    website: str | None = None
    investor_type: str | None = None
    status: str | None = None
    hq_city: str | None = None
    hq_country: str | None = None
    location: str | None = None
    stages: list[str] | None = None
    sectors: list[str] | None = None
    geographies: list[str] | None = None
    geo_focus: list[str] | None = None
    rounds: list[str] | None = None
    description: str | None = None
    investment_thesis: str | None = None
    stated_thesis: str | None = None
    revealed_thesis: str | None = None
    short_description: str | None = None
    long_description: str | None = None
    investment_tendency: str | None = None
    year_founded: int | None = None
    first_cheque_min: float | None = None
    first_cheque_max: float | None = None
    first_cheque_currency: str | None = None
    ticket_size_min: float | None = None
    ticket_size_max: float | None = None
    enrichment_status: str | None = None


# Whitelist of columns safe to use in dynamic UPDATE
UPDATABLE_COLUMNS = {
    "canonical_name", "website", "investor_type", "status",
    "hq_city", "hq_country", "location",
    "stages", "sectors", "geographies", "geo_focus", "rounds",
    "description", "investment_thesis", "stated_thesis", "revealed_thesis",
    "short_description", "long_description",
    "investment_tendency", "year_founded",
    "first_cheque_min", "first_cheque_max", "first_cheque_currency",
    "ticket_size_min", "ticket_size_max",
    "enrichment_status",
}


class InvestorSearchBody(BaseModel):
    name: str | None = None          # prefix/substring match on canonical_name
    q: str | None = None             # full-text across name, thesis, description
    stages: list[str] = []           # match any of these stages
    sectors: list[str] = []          # match any of these sectors
    geographies: list[str] = []      # match any of these geographies
    investor_type: str | None = None
    enrichment_status: str | None = None
    needs_review: bool | None = None
    cheque_min: float | None = None  # investor's min cheque <= this
    cheque_max: float | None = None  # investor's min cheque <= this (affordable)
    limit: int = 50
    offset: int = 0
