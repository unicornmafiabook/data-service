import re

from pydantic import BaseModel, Field

from app.schemas.matching import FounderMatchRequest

TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{2,}")

_STOPWORDS = {
    "the", "and", "are", "for", "that", "this", "with", "from", "they", "have",
    "been", "their", "our", "your", "its", "can", "not", "but", "all", "one",
    "who", "out", "use", "how", "was", "has", "had", "his", "her", "will",
    "also", "into", "via", "per", "any", "may", "more", "each", "both",
    "lets", "real", "time", "next", "new", "high", "low", "key", "top",
}


class FounderIntent(BaseModel):
    company_category: str | None = None
    business_model: str | None = None
    stage: str | None = None
    geographies: list[str] = Field(default_factory=list)
    raise_amount: float | None = None
    target_buyers: list[str] = Field(default_factory=list)
    target_customers: list[str] = Field(default_factory=list)
    customer_industries: list[str] = Field(default_factory=list)
    jobs_to_be_done: list[str] = Field(default_factory=list)
    complementary_categories: list[str] = Field(default_factory=list)
    competitor_categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    query_text: str = ""


def build_founder_intent(request: FounderMatchRequest) -> FounderIntent:
    tokens = _tokens_from_request(request)
    keywords = _dedupe([*request.keywords, *tokens[:20]])
    return FounderIntent(
        company_category=_first(request.sectors),
        business_model=request.business_model,
        stage=request.stage,
        geographies=request.geographies,
        raise_amount=request.raise_amount,
        target_buyers=request.buyer_personas,
        target_customers=request.target_customers,
        customer_industries=_dedupe([*request.sectors, *request.target_customers]),
        jobs_to_be_done=_jobs_to_be_done(tokens),
        complementary_categories=_dedupe([*request.target_suppliers, *_integration_terms(tokens)]),
        competitor_categories=_dedupe([*request.sectors, *keywords[:12]]),
        keywords=keywords,
        query_text=_query_text(request, keywords),
    )


def is_sparse_intent(intent: FounderIntent) -> bool:
    signal_count = len(intent.keywords) + len(intent.target_customers) + len(intent.target_buyers)
    if intent.company_category:
        signal_count += 1
    return signal_count < 4


def _tokens_from_request(request: FounderMatchRequest) -> list[str]:
    source = " ".join(_text_fields(request))
    return _dedupe([t for t in TOKEN_PATTERN.findall(source.lower()) if t not in _STOPWORDS])


def _text_fields(request: FounderMatchRequest) -> list[str]:
    return [
        request.founder_thesis or "",
        request.product_description or "",
        request.short_description or "",
        request.business_model or "",
        " ".join(request.sectors),
        " ".join(request.target_customers),
        " ".join(request.buyer_personas),
        " ".join(request.keywords),
    ]


def _jobs_to_be_done(tokens: list[str]) -> list[str]:
    job_terms = [token for token in tokens if token.endswith("ing") or token in {"automate", "automation", "workflow"}]
    return _dedupe(job_terms)


def _integration_terms(tokens: list[str]) -> list[str]:
    markers = {"integration", "integrations", "api", "supplier", "suppliers", "workflow", "platform"}
    return [token for token in tokens if token in markers]


def _query_text(request: FounderMatchRequest, keywords: list[str]) -> str:
    values = [* _text_fields(request), " ".join(request.geographies), " ".join(keywords)]
    return " ".join(value for value in values if value).strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        _append_unique(result, seen, value)
    return result


def _append_unique(result: list[str], seen: set[str], value: str) -> None:
    normalised = value.strip().lower()
    if not normalised or normalised in seen:
        return
    seen.add(normalised)
    result.append(normalised)


def _first(values: list[str]) -> str | None:
    if not values:
        return None
    return values[0]
