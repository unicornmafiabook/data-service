# VC Data Service — API Contract

**Base URL (local dev):** `http://127.0.0.1:8000`  
**Interactive docs:** `http://127.0.0.1:8000/docs`  
**Content-Type:** `application/json` for all requests and responses

---

## Quick reference

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness + DB check |
| `GET` | `/investors/stats` | Dashboard counts |
| `GET` | `/investors` | Paginated list of all investors |
| `POST` | `/investors` | Manually create an investor |
| `GET` | `/investors/search` | Filtered search (query params) |
| `POST` | `/investors/search` | Filtered search (JSON body, supports arrays) |
| `GET` | `/investors/{investor_id}` | Single investor + raw source rows |
| `PATCH` | `/investors/{investor_id}` | Partial field update |
| `GET` | `/investors/{investor_id}/members` | VC team members |
| `GET` | `/investors/{investor_id}/funds` | Fund history |
| `GET` | `/investors/{investor_id}/portfolio` | Legacy CSV-imported portfolio companies |
| `GET` | `/investors/{investor_id}/similar` | Investors with overlapping stages/sectors |
| `POST` | `/investors/{investor_id}/mark-for-enrichment` | Queue investor for enrichment |
| `GET` | `/enrichment/stats` | Enrichment queue depth |
| `GET` | `/enrichment/next-vc` | Pull next investor to enrich |
| `GET` | `/enrichment/vc/{vc_id}` | Full enrichment snapshot |
| `POST` | `/enrichment/vc/{vc_id}/complete` | Submit enrichment results |
| `POST` | `/ingest/run` | Re-run CSV import (admin only) |

---

## IDs — important

Two investor ID types exist. Use the right one per endpoint.

| Field | Type | Used in |
|-------|------|---------|
| `id` | UUID string | All `/investors/{investor_id}` endpoints |
| `external_vc_id` | integer | All `/enrichment/vc/{vc_id}` endpoints |

`external_vc_id` is the sequential integer the enrichment agent uses as `VC.id`. For all standard browsing and search, use the UUID `id`.

---

## Endpoints

---

### `GET /health`

```json
{ "status": "ok", "database": "connected" }
```

---

### `GET /investors/stats`

Dashboard summary counts.

```json
{
  "investors": {
    "total_investors": 8495,
    "enriched": 12,
    "pending": 3,
    "not_started": 8480,
    "needs_review": 237,
    "multi_source": 842
  },
  "investor_sources": 10131,
  "vc_members": 48,
  "vc_funds": 21,
  "portfolio_companies": 94
}
```

| Field | Description |
|-------|-------------|
| `enriched` | Investors with `enrichment_status = completed` |
| `needs_review` | Deduplicated by name only — lower confidence |
| `multi_source` | Appeared in more than one CSV source |

---

### `GET /investors`

Paginated alphabetical list.

**Query params:** `limit` (default 50, max 200), `offset` (default 0)

**Response**
```json
{
  "count": 50,
  "results": [
    {
      "id": "b264da2c-...",
      "canonical_name": ".406 Ventures",
      "website": "https://406ventures.com",
      "domain": "406ventures.com",
      "investor_type": null,
      "status": "Active",
      "hq_country": "United States",
      "location": "Boston, United States",
      "stages": ["seed", "series_a"],
      "sectors": ["deeptech"],
      "geographies": ["United States"],
      "rounds": ["Seed", "Series A"],
      "geo_focus": ["United States"],
      "short_description": null,
      "enrichment_status": "not_started",
      "first_cheque_min": null,
      "first_cheque_max": null,
      "source_count": 1,
      "needs_review": false
    }
  ]
}
```

---

### `POST /investors`

Manually create an investor. Rejects duplicate domains with `409`.

**Request body**
```json
{
  "canonical_name": "Acme Ventures",
  "website": "https://acmevc.com",
  "investor_type": "VC",
  "status": "Active",
  "hq_city": "London",
  "hq_country": "United Kingdom",
  "stages": ["seed", "series_a"],
  "sectors": ["fintech", "b2b"],
  "geographies": ["United Kingdom", "Europe"],
  "description": "Early-stage fintech investor.",
  "investment_thesis": "We back founders reimagining financial infrastructure.",
  "first_cheque_min": 250000,
  "first_cheque_max": 2000000,
  "first_cheque_currency": "GBP"
}
```

All fields except `canonical_name` are optional.

**Response (201)**
```json
{ "id": "uuid", "external_vc_id": 8496 }
```

---

### `GET /investors/search`

Simple filtered search via query params.

**Query params**

| Param | Description |
|-------|-------------|
| `stage` | Single stage value — investors whose `stages` contains this |
| `sector` | Single sector value |
| `geography` | Single geography value |
| `cheque_max` | Investors whose `first_cheque_min` ≤ this value |
| `q` | Text search across name, thesis, description |
| `limit` | Default 50, max 200 |
| `offset` | Default 0 |

```
GET /investors/search?stage=seed&sector=fintech&geography=United+Kingdom
GET /investors/search?cheque_max=500000
GET /investors/search?q=deep+tech
```

---

### `POST /investors/search`

Rich filtered search via JSON body. Supports arrays for multi-value filtering.

**Request body**
```json
{
  "name": "accel",
  "q": "enterprise software",
  "stages": ["seed", "series_a"],
  "sectors": ["fintech", "deeptech"],
  "geographies": ["United Kingdom", "Europe"],
  "investor_type": "VC",
  "enrichment_status": "completed",
  "needs_review": false,
  "cheque_min": 100000,
  "cheque_max": 2000000,
  "limit": 20,
  "offset": 0
}
```

All fields are optional.

| Field | Behaviour |
|-------|-----------|
| `name` | Substring match on `canonical_name` |
| `q` | Substring match across name, thesis, description |
| `stages` | Investor must have **any** of these in their stages array |
| `sectors` | Investor must have **any** of these in their sectors array |
| `geographies` | Matches against both `geographies` and `geo_focus` arrays |
| `cheque_min` | Investor's `first_cheque_max` ≥ this (they can write a big enough cheque) |
| `cheque_max` | Investor's `first_cheque_min` ≤ this (they write small enough cheques) |

---

### `GET /investors/{investor_id}`

Full investor row plus original CSV source records.

```json
{
  "investor": {
    "id": "b264da2c-...",
    "external_vc_id": 89,
    "canonical_name": ".406 Ventures",
    "slug": "406-ventures",
    "website": "https://406ventures.com",
    "website_url": "https://406ventures.com",
    "domain": "406ventures.com",
    "investor_type": null,
    "status": "Active",
    "hq_city": null,
    "hq_country": "United States",
    "location": "Boston, United States",
    "stages": ["seed", "series_a", "series_b"],
    "rounds": ["Seed", "Series A", "Series B"],
    "sectors": ["enterprise", "deeptech"],
    "geographies": ["United States"],
    "geo_focus": ["United States"],
    "short_description": "Early-stage B2B and deep tech investor.",
    "long_description": "Founded by former operators...",
    "investment_thesis": "We back founders building the future of enterprise.",
    "stated_thesis": "We back founders building the future of enterprise.",
    "revealed_thesis": "Strong pattern in security and analytics.",
    "investment_tendency": "lead",
    "year_founded": 2008,
    "ticket_size_min": 500000,
    "ticket_size_max": 5000000,
    "first_cheque_min": 500000,
    "first_cheque_max": 5000000,
    "first_cheque_currency": "USD",
    "enrichment_status": "completed",
    "source_count": 2,
    "source_names": ["source_1", "source_4"],
    "needs_review": false,
    "dedupe_confidence": 0.98,
    "created_at": "2026-04-25T16:36:00",
    "updated_at": "2026-04-25T21:23:00"
  },
  "sources": [
    {
      "source_name": "source_1",
      "source_row_id": "42",
      "original_name": ".406 Ventures",
      "original_website": "https://406ventures.com",
      "raw_data": { "name": ".406 Ventures", "round": "Seed, Series A" }
    }
  ]
}
```

**Field notes**

| Field | Description |
|-------|-------------|
| `stages` | Internal normalised values from CSV import (`seed`, `series_a` etc.) |
| `rounds` | Human-readable values from enrichment (`Seed`, `Series A` etc.) |
| `geographies` | Countries from CSV import |
| `geo_focus` | Countries from enrichment — prefer this when populated |
| `investment_thesis` | Raw text from CSV source |
| `stated_thesis` | Cleaned thesis from enrichment |
| `revealed_thesis` | Thesis inferred by agent from portfolio pattern analysis |
| `investment_tendency` | `lead` / `follow_on` / `unsure` |
| `dedupe_confidence` | `0.98` = matched by domain. `0.8` = matched by name only |

---

### `PATCH /investors/{investor_id}`

Update any subset of fields. Only provided fields are changed.

**Request body** — all fields optional:
```json
{
  "canonical_name": "New Name",
  "short_description": "Updated description.",
  "investment_tendency": "lead",
  "stages": ["seed", "series_a"],
  "sectors": ["fintech"],
  "enrichment_status": "pending"
}
```

Updatable fields: `canonical_name`, `website`, `investor_type`, `status`, `hq_city`, `hq_country`, `location`, `stages`, `sectors`, `geographies`, `geo_focus`, `rounds`, `description`, `investment_thesis`, `stated_thesis`, `revealed_thesis`, `short_description`, `long_description`, `investment_tendency`, `year_founded`, `first_cheque_min`, `first_cheque_max`, `first_cheque_currency`, `ticket_size_min`, `ticket_size_max`, `enrichment_status`

**Response**
```json
{ "updated": ["short_description", "investment_tendency"] }
```

---

### `GET /investors/{investor_id}/members`

VC investment team (populated after enrichment).

```json
{
  "count": 2,
  "results": [
    {
      "name": "Greg Dracon",
      "position": "General Partner",
      "expertise": ["Enterprise Software", "Healthcare IT"],
      "description": "Leads B2B SaaS investments.",
      "linkedin": "https://linkedin.com/in/gregdracon",
      "email": "greg@406ventures.com",
      "joined_at": "2008-01-01"
    }
  ]
}
```

---

### `GET /investors/{investor_id}/funds`

Named funds the firm has raised (populated after enrichment).

```json
{
  "count": 2,
  "results": [
    {
      "fund_name": ".406 Ventures Fund I",
      "fund_size": 100000000,
      "fund_size_raw": "$100M",
      "vintage_year": 2008
    }
  ]
}
```

---

### `GET /investors/{investor_id}/portfolio`

Portfolio companies from CSV import (legacy, low fidelity). For enriched portfolio use `GET /enrichment/vc/{vc_id}`.

```json
{
  "count": 3,
  "results": [
    {
      "id": "uuid",
      "canonical_name": "Biomason",
      "sector": null,
      "relationship_type": "portfolio",
      "confidence_score": 0.7,
      "source": "import"
    }
  ]
}
```

---

### `GET /investors/{investor_id}/similar`

Investors ranked by overlapping sectors (weight ×3), stages (×2), geographies (×1).

**Query params:** `limit` (default 10, max 50)

```json
{
  "count": 5,
  "results": [
    {
      "id": "uuid",
      "canonical_name": "Accel",
      "stages": ["seed", "series_a"],
      "sectors": ["deeptech", "enterprise"],
      "similarity_score": 8
    }
  ]
}
```

---

### `POST /investors/{investor_id}/mark-for-enrichment`

Sets `enrichment_status = pending`. No request body.

```json
{ "status": "pending", "investor_id": "uuid" }
```

---

## Enrichment endpoints

---

### `GET /enrichment/stats`

```json
{
  "not_started": 8480,
  "pending": 3,
  "completed": 12,
  "total": 8495
}
```

---

### `GET /enrichment/next-vc`

Returns the next investor needing enrichment as a `VC` object. Prioritises `pending` over `not_started`. Uses `FOR UPDATE SKIP LOCKED` — safe for concurrent agents.

Returns `404` when the queue is empty.

**Response — `VC` object**
```json
{
  "id": 89,
  "name": ".406 Ventures",
  "short_description": null,
  "long_description": null,
  "stated_thesis": null,
  "revealed_thesis": null,
  "rounds": ["Seed", "Series A"],
  "sectors": ["deeptech"],
  "ticket_size_min": null,
  "ticket_size_max": null,
  "tendency": null,
  "year_founded": null,
  "funds": [],
  "location": "United States",
  "geo_focus": ["United States"],
  "website_url": "https://406ventures.com",
  "status": "Active",
  "slug": "406-ventures"
}
```

The integer `id` is `external_vc_id` — pass it directly to `/enrichment/vc/{vc_id}/complete`.

---

### `GET /enrichment/vc/{vc_id}`

Full enrichment snapshot for an already-enriched investor.

```json
{
  "investor": {
    "id": "uuid",
    "canonical_name": ".406 Ventures",
    "enrichment_status": "completed",
    "last_enriched_at": "2026-04-25T21:23:00"
  },
  "enriched_at": "2026-04-25T21:23:00",
  "members": [
    {
      "name": "Greg Dracon",
      "position": "General Partner",
      "expertise": ["Enterprise Software"],
      "linkedin": "https://linkedin.com/in/gregdracon"
    }
  ],
  "funds": [
    { "fund_name": ".406 Fund I", "fund_size": 100000000, "vintage_year": 2008 }
  ],
  "portfolio": [
    {
      "name": "Veracode",
      "overview": "Application security testing.",
      "sectors": ["deeptech"],
      "stages": ["Series A", "Series B"],
      "status": "exited",
      "hq": "Burlington, MA",
      "founded_year": 2006,
      "valuation_usd": "$614M",
      "team": [
        { "name": "Sam King", "position": "CEO" }
      ]
    }
  ]
}
```

---

### `POST /enrichment/vc/{vc_id}/complete`

Submit enrichment results. Accepts `DeepEnrichedVC` from the agent pipeline.

**Path param:** `vc_id` — the integer `id` from `GET /enrichment/next-vc`.

**Request body — `DeepEnrichedVC`**

```json
{
  "vc": { },
  "profile": { },
  "team": [ ],
  "portfolio": [ ],
  "revealed_thesis": { },
  "enriched_at": "2026-04-25T12:00:00Z",
  "depth": "standard",
  "branch_traces": [ ]
}
```

---

#### `vc` — `VC` object (same shape returned by `next-vc`)

```json
{
  "id": 89,
  "name": ".406 Ventures",
  "rounds": ["Seed", "Series A"],
  "sectors": ["deeptech", "enterprise"],
  "tendency": "lead",
  "year_founded": 2008,
  "funds": [
    { "name": ".406 Fund I", "size_usd": 100000000, "vintage_year": 2008 }
  ],
  "location": "Boston, United States",
  "geo_focus": ["United States"],
  "website_url": "https://406ventures.com",
  "status": "Active",
  "slug": "406-ventures"
}
```

---

#### `profile` — `EnrichedVCProfile`

```json
{
  "identity": {
    "short_description": "Early-stage B2B and deep tech investor.",
    "long_description": "Founded by former operators...",
    "stated_thesis": "We back founders building the future of enterprise.",
    "year_founded": 2008,
    "hq": "Boston, United States",
    "website_url": "https://406ventures.com"
  },
  "preferences": {
    "stages": ["Seed", "Series A"],
    "sectors": ["deeptech", "enterprise"],
    "ticket_size": {
      "minimum_usd": 500000,
      "maximum_usd": 5000000,
      "currency": "USD"
    },
    "tendency": "lead",
    "geo_focus": ["United States"],
    "funds": [
      { "name": ".406 Fund I", "size_usd": 100000000, "vintage_year": 2008 }
    ]
  },
  "source": {
    "url": "https://406ventures.com/about",
    "source_type": "vc_website",
    "extracted_at": "2026-04-25T12:00:00Z"
  }
}
```

**`identity` field mapping → `investors` table**

| Agent field | DB column |
|-------------|-----------|
| `short_description` | `short_description` |
| `long_description` | `long_description` |
| `stated_thesis` | `stated_thesis` |
| `year_founded` | `year_founded` |
| `hq` | `location` |
| `website_url` | `website_url` |

**`preferences` field mapping → `investors` table**

| Agent field | DB column |
|-------------|-----------|
| `stages` | `rounds` (TEXT[]) |
| `sectors` | `sectors` (TEXT[]) |
| `ticket_size.minimum_usd` | `ticket_size_min` |
| `ticket_size.maximum_usd` | `ticket_size_max` |
| `ticket_size.currency` | `first_cheque_currency` |
| `tendency` | `investment_tendency` |
| `geo_focus` | `geo_focus` (TEXT[]) |
| `funds[].name` | `vc_funds.fund_name` |
| `funds[].size_usd` | `vc_funds.fund_size` |
| `funds[].vintage_year` | `vc_funds.vintage_year` |

---

#### `team` — `list[EnrichedVCMember]`

```json
[
  {
    "name": "Greg Dracon",
    "position": "General Partner",
    "area_of_expertise": "Enterprise Software",
    "description": "Leads B2B SaaS investments.",
    "linkedin": "https://linkedin.com/in/gregdracon",
    "email": "greg@406ventures.com",
    "joined_at": "2008-01-01",
    "source": { "url": "...", "source_type": "vc_website", "extracted_at": "..." }
  }
]
```

**Field mapping → `vc_members` table**

| Agent field | DB column |
|-------------|-----------|
| `name` | `name` |
| `position` | `position` |
| `area_of_expertise` | `expertise` (stored as single-element array) |
| `description` | `description` |
| `linkedin` | `linkedin` |
| `email` | `email` |
| `joined_at` | `joined_at` |

---

#### `portfolio` — `list[EnrichedPortfolioCompany]`

```json
[
  {
    "name": "Veracode",
    "overview": "Application security testing platform.",
    "investment_stage": "Series B",
    "sectors": ["deeptech", "software"],
    "status": "exited",
    "hq": "Burlington, MA",
    "founded_in": 2006,
    "company_size": "201-500",
    "valuation": "$614M",
    "website_url": "https://veracode.com",
    "executives": [
      {
        "name": "Sam King",
        "position": "CEO",
        "description": "Led Veracode through acquisition.",
        "linkedin": "https://linkedin.com/in/samking",
        "email": null,
        "source": { "url": "...", "source_type": "portco_website", "extracted_at": "..." }
      }
    ],
    "source": { "url": "...", "source_type": "vc_website", "extracted_at": "..." }
  }
]
```

**Field mapping → `portfolio_companies` table**

| Agent field | DB column |
|-------------|-----------|
| `name` | `name` |
| `overview` | `overview` |
| `investment_stage` | `stage` (wrapped as single-element array) |
| `sectors` | `sectors` (TEXT[]) |
| `status` | `status` |
| `hq` | `hq` |
| `founded_in` | `founded_year` |
| `company_size` | `company_size` |
| `valuation` | `valuation_usd` |
| `website_url` | `website_url` |
| `executives` | `portco_team` rows |

---

#### `revealed_thesis` — `RevealedThesis`

```json
{
  "summary": "Strong focus on developer-tooling and security despite generalist stated thesis.",
  "inferred_sectors": ["deeptech", "software"],
  "inferred_stages": ["Seed", "Series A"],
  "inferred_geo_focus": ["United States"],
  "source": { "url": "...", "source_type": "web_search", "extracted_at": "..." }
}
```

Stored in `investors.revealed_thesis` (summary text) and `investors.revealed_thesis_json` (full object — pending migration).

---

#### `depth` and `branch_traces`

```json
"depth": "standard",
"branch_traces": [
  {
    "target_label": "vc_profile:406-ventures",
    "primary_url": "https://406ventures.com/about",
    "fallback_used": false,
    "fallback_query": null,
    "selected_source": { "url": "...", "source_type": "vc_website", "extracted_at": "..." }
  }
]
```

Both stored in `vc_enrichments` (`depth TEXT`, `branch_traces JSONB`) — pending migration.

---

**Response**
```json
{
  "status": "completed",
  "vc_id": 89,
  "members_updated": 2,
  "portfolio_updated": 4,
  "funds_updated": 2
}
```

---

## Enum reference

### `InvestmentStage` — `VC.rounds`, `PortfolioCompany.stages`

`"Pre-Seed"` `"Seed"` `"Series A"` `"Series B"` `"Series C"` `"Growth"` `"Late Stage"`

### `VCStatus` — `VC.status`

`"Active"` `"Inactive"`

### `InvestmentTendency` — `VC.tendency`

`"lead"` `"follow_on"` `"unsure"`

### `PortcoStatus` — `PortfolioCompany.status`

`"active"` `"exited"`

### `SourceType` — `SourceInfo.source_type`

`"vc_data_service"` `"vc_website"` `"portco_website"` `"web_search"`

### `DepthLevel` — `DeepEnrichedVC.depth`

`"quick"` `"standard"` `"deep"`

---

## Stage filter values (for `GET /investors/search`)

These are the **internal normalised values** stored in `investors.stages`. Use these exact strings when filtering.

`idea` `prototype` `pre_seed` `seed` `early_revenue` `series_a` `series_b` `series_c` `growth` `buyout` `secondary` `infrastructure`

---

## Sector filter values (for `GET /investors/search`)

`fintech` `software` `deeptech` `healthcare` `consumer` `b2b` `ecommerce` `climate` `infrastructure` `real_estate` `industrial` `media` `logistics` `generalist`

---

## Pagination

```
GET /investors?limit=20&offset=0   → page 1
GET /investors?limit=20&offset=20  → page 2
```

`count` in the response is results in this page, not total. Last page when `count < limit`.

---

## Error responses

| Status | Meaning |
|--------|---------|
| `200` | Success |
| `201` | Created (POST /investors) |
| `400` | Bad request — no valid fields to update |
| `404` | Resource not found |
| `409` | Conflict — duplicate domain on investor create |
| `422` | Validation error — body failed Pydantic validation |
| `500` | Internal server error |

---

## Data quality guidance

- Prefer `rounds` over `stages` — `rounds` is enrichment-sourced and human-readable; `stages` is raw CSV
- Prefer `geo_focus` over `geographies` — same reason
- Prefer `stated_thesis` over `investment_thesis` — cleaned vs raw
- Prefer `ticket_size_min/max` over `first_cheque_min/max` — enrichment vs CSV
- `needs_review: true` → deduplicated by name only, surface a warning in UI
- `enrichment_status: not_started` → only CSV data available, narrative fields will be null
- `source_count > 1` → appeared in multiple datasets, higher confidence record

---

## Pending schema changes

Two small migrations needed to fully support `DeepEnrichedVC`:

1. `investors.revealed_thesis_json JSONB` — stores full `RevealedThesis` object
2. `vc_enrichments.depth TEXT` and `vc_enrichments.branch_traces JSONB` — stores pipeline audit trail

The `POST /enrichment/vc/{vc_id}/complete` endpoint will be updated to write these fields once the migration is applied.
