from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

RelationshipType = Literal[
    "potential_client",
    "potential_supplier",
    "complement",
    "partner",
    "competitor",
    "irrelevant",
]


class FounderMatchRequest(BaseModel):
    company_name: str | None = None
    founder_name: str | None = None
    stage: str | None = None
    sectors: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    raise_amount: float | None = None
    raise_currency: str = "USD"
    founder_thesis: str | None = None
    short_description: str | None = None
    product_description: str | None = None
    target_customers: list[str] = Field(default_factory=list)
    target_suppliers: list[str] = Field(default_factory=list)
    business_model: str | None = None
    buyer_personas: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)
    allow_unenriched_fallback: bool = False


class PortfolioOpportunityResult(BaseModel):
    company_id: UUID | None = None
    name: str
    relationship_type: RelationshipType
    fit_score: float
    competition_risk_score: float = 0
    reasoning: str | None = None


class VCMatchResult(BaseModel):
    rank: int
    investor_id: UUID
    external_vc_id: int | None = None
    slug: str | None = None
    name: str
    website: str | None = None
    overall_score: float
    score_band: str
    retrieval_score: float | None = None
    direct_vc_fit_score: float | None = None
    semantic_thesis_score: float | None = None
    portfolio_network_score: float | None = None
    commercial_access_score: float | None = None
    team_relevance_score: float | None = None
    data_confidence_score: float | None = None
    competitor_penalty: float = 0
    max_competition_risk_score: float = 0
    explanation: str
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    portfolio_opportunities: list[PortfolioOpportunityResult] = Field(default_factory=list)


class FounderMatchResponse(BaseModel):
    count: int
    algorithm_version: str = "v5_rag_graph_stateless_competitor_heavy"
    data_scope: str = "enriched_only"
    top_vcs: list[VCMatchResult]
    warnings: list[str] = Field(default_factory=list)


class VCExplanationRequest(BaseModel):
    founder: FounderMatchRequest
    investor_id: UUID | None = None
    external_vc_id: int | None = None
    slug: str | None = None


class VCMemoExplanation(BaseModel):
    explanation: str
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class VCExplanationResponse(BaseModel):
    investor_id: UUID
    external_vc_id: int | None = None
    slug: str | None = None
    name: str
    model: str | None = None
    llm_status: str
    deterministic_score: VCMatchResult
    memo: VCMemoExplanation | None = None
    warnings: list[str] = Field(default_factory=list)
