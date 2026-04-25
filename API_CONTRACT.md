# VC Data Service — API Contract

**Base URL (local dev):** `http://127.0.0.1:8000`  
**Interactive docs:** `http://127.0.0.1:8000/docs`  
**Content-Type:** `application/json` for all requests and responses

---

## Quick reference

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness + DB check |
| `GET` | `/investors` | Paginated list of all investors |
| `GET` | `/investors/search` | Filtered investor search |
| `GET` | `/investors/{investor_id}` | Single investor + raw source rows |
| `GET` | `/investors/{investor_id}/portfolio` | Legacy portfolio companies (from CSV import) |
| `POST` | `/investors/{investor_id}/mark-for-enrichment` | Queue an investor for enrichment |
| `GET` | `/enrichment/next-vc` | Pull the next investor to enrich |
| `POST` | `/enrichment/vc/{vc_id}/complete` | Submit enrichment results |
| `POST` | `/ingest/run` | Re-run CSV import (internal/admin only) |

---

## IDs — important

There are two investor ID types. Use the right one per endpoint.

| Field | Type | Used in |
|-------|------|---------|
| `id` | UUID string | `/investors/{investor_id}` endpoints |
| `external_vc_id` | integer | `/enrichment/vc/{vc_id}/complete` |

The `external_vc_id` is the integer `id` inside the `VC` enrichment model. It exists because the enrichment contract requires a sequential integer. For all standard investor browsing/search, use the UUID `id`.

---

## Endpoints

---

### `GET /health`

Returns the service and database status. Call this before any other request to confirm the service is up.

**Response**
```json
{
  "status": "ok",
  "database": "connected"
}
```

---

### `GET /investors`

Returns a paginated list of all investors ordered alphabetically. Use this to build a browse / directory view.

**Query parameters**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | integer | `50` | Max results to return. Hard cap: `200` |
| `offset` | integer | `0` | Number of records to skip for pagination |

**Response**
```json
{
  "count": 50,
  "results": [
    {
      "id": "b264da2c-6957-48b5-8c35-3e97d52e3086",
      "canonical_name": ".406 Ventures",
      "website": "https://406ventures.com",
      "domain": "406ventures.com",
      "stages": ["seed", "series_a", "series_b"],
      "sectors": ["deeptech"],
      "geographies": ["United States"],
      "first_cheque_min": null,
      "first_cheque_max": null,
      "source_count": 1,
      "needs_review": false
    }
  ]
}
```

**Field notes**

| Field | Description |
|-------|-------------|
| `id` | UUID — use this for detail page routing e.g. `/vc/b264da2c-...` |
| `canonical_name` | Best available name, deduplicated across all sources |
| `domain` | Clean domain without `www` or protocol e.g. `406ventures.com` |
| `stages` | Internal normalised values — see stage taxonomy below |
| `sectors` | Internal normalised values — see sector taxonomy below |
| `geographies` | Countries the VC invests in, from CSV sources |
| `source_count` | How many of the 4 CSV sources this investor appeared in |
| `needs_review` | `true` if deduplication was uncertain — treat data with lower confidence |

---

### `GET /investors/search`

Filtered investor search. All parameters are optional and combinable.

**Query parameters**

| Param | Type | Description |
|-------|------|-------------|
| `stage` | string | Filter to investors whose `stages` array contains this value |
| `sector` | string | Filter to investors whose `sectors` array contains this value |
| `geography` | string | Filter to investors whose `geographies` array contains this value |
| `cheque_max` | number | Filter to investors whose `first_cheque_min` is ≤ this value (i.e. they can write a cheque within your budget) |
| `q` | string | Free-text search across `canonical_name`, `investment_thesis`, `description` |
| `limit` | integer | Default `50`, max `200` |
| `offset` | integer | Default `0` |

**Example requests**
```
GET /investors/search?stage=seed
GET /investors/search?sector=fintech&geography=United+Kingdom
GET /investors/search?cheque_max=500000
GET /investors/search?q=deep+tech
GET /investors/search?stage=seed&sector=fintech&limit=20&offset=0
```

**Stage filter values** — use these exact strings:

| Value | Meaning |
|-------|---------|
| `idea` | Idea / concept stage |
| `prototype` | Prototype / MVP |
| `pre_seed` | Pre-seed |
| `seed` | Seed |
| `early_revenue` | Early revenue |
| `series_a` | Series A |
| `series_b` | Series B |
| `series_c` | Series C |
| `growth` | Growth / late stage |
| `buyout` | Buyout |
| `secondary` | Secondary |
| `infrastructure` | Infrastructure funds |

**Sector filter values** — use these exact strings:

| Value |
|-------|
| `fintech` |
| `software` |
| `deeptech` |
| `healthcare` |
| `consumer` |
| `b2b` |
| `ecommerce` |
| `climate` |
| `infrastructure` |
| `real_estate` |
| `industrial` |
| `media` |
| `logistics` |
| `generalist` |

**Response** — same shape as `/investors` but with more fields per result:
```json
{
  "count": 3,
  "results": [
    {
      "id": "b264da2c-6957-48b5-8c35-3e97d52e3086",
      "canonical_name": ".406 Ventures",
      "website": "https://406ventures.com",
      "domain": "406ventures.com",
      "investor_type": "VC",
      "status": "Active",
      "hq_city": null,
      "hq_country": "United States",
      "stages": ["seed", "series_a"],
      "sectors": ["deeptech"],
      "geographies": ["United States"],
      "first_cheque_min": 500000,
      "first_cheque_max": 5000000,
      "first_cheque_currency": "USD",
      "description": null,
      "investment_thesis": "We back founders building the future of enterprise.",
      "source_count": 1,
      "dedupe_confidence": 0.98,
      "needs_review": false
    }
  ]
}
```

**Additional field notes**

| Field | Description |
|-------|-------------|
| `investor_type` | Raw string from source e.g. `"VC"`, `"CVC"`, `"Angel Fund"`, `"Family Office"` |
| `status` | Raw status string from source e.g. `"Active"`, `"Member"` |
| `hq_country` | Country of headquarters from CSV import |
| `first_cheque_min/max` | Numeric cheque size in `first_cheque_currency` (usually USD) |
| `investment_thesis` | Raw thesis text from CSV source |
| `dedupe_confidence` | `0.98` = matched by domain (reliable). `0.8` = matched by name only (review) |

---

### `GET /investors/{investor_id}`

Full detail for a single investor, plus all original source rows.

**Path parameter:** `investor_id` — UUID from search/list results.

**Response**
```json
{
  "investor": {
    "id": "b264da2c-...",
    "canonical_name": ".406 Ventures",
    "external_vc_id": 89,
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
    "sectors": ["enterprise", "healthcare", "deeptech"],
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
    "capital_under_management": null,
    "enrichment_status": "completed",
    "source_count": 2,
    "source_names": ["source_1", "source_4"],
    "dedupe_key": "domain:406ventures.com",
    "dedupe_confidence": 0.98,
    "needs_review": false,
    "created_at": "2026-04-25T16:36:00",
    "updated_at": "2026-04-25T21:23:00"
  },
  "sources": [
    {
      "source_name": "source_1",
      "source_row_id": "42",
      "raw_data": { "name": ".406 Ventures", "round": "Seed, Series A", "location": "United States" }
    }
  ]
}
```

**Key field notes**

| Field | Description |
|-------|-------------|
| `external_vc_id` | Integer ID — use this when calling enrichment endpoints |
| `slug` | URL-safe name e.g. `"406-ventures"` — use for human-readable URLs |
| `stages` | Internal normalised values (from CSV import) |
| `rounds` | Human-readable enum values (from enrichment) — `"Seed"`, `"Series A"` etc. |
| `geographies` | Countries from CSV import |
| `geo_focus` | Countries from enrichment (may differ / more precise) |
| `investment_thesis` | Raw text from CSV source |
| `stated_thesis` | Cleaned thesis from enrichment |
| `revealed_thesis` | Thesis inferred by agent after scraping portfolio companies |
| `investment_tendency` | `"lead"` / `"follow_on"` / `"unsure"` |
| `enrichment_status` | `"not_started"` / `"pending"` / `"completed"` |
| `sources` | Array of original CSV rows — useful for debugging data quality |

---

### `GET /investors/{investor_id}/portfolio`

Returns portfolio companies linked to this investor from the **CSV import** (legacy, lower fidelity). For enriched portfolio data use the enrichment complete payload or query Supabase directly.

**Response**
```json
{
  "count": 3,
  "results": [
    {
      "id": "f1ccd59d-...",
      "canonical_name": "Biomason",
      "website": null,
      "domain": null,
      "sector": null,
      "sub_sector": null,
      "description": null,
      "relationship_type": "portfolio",
      "investment_stage": null,
      "investment_round": null,
      "investment_date": null,
      "confidence_score": 0.7,
      "source": "import"
    }
  ]
}
```

> **Note:** Most fields will be `null` for import-sourced companies. Rich portfolio data (overview, sectors, team, valuation etc.) comes from the enrichment flow and lives in the `portfolio_companies` and `portco_team` tables, not returned by this endpoint yet.

---

### `POST /investors/{investor_id}/mark-for-enrichment`

Flags an investor so the enrichment agent will pick it up next. Sets `enrichment_status = "pending"`.

**No request body required.**

**Response**
```json
{
  "status": "pending",
  "investor_id": "b264da2c-..."
}
```

---

## Enrichment endpoints

These are called by the AI enrichment agent, not typically by the frontend directly. Documented here for completeness and for building admin tooling.

---

### `GET /enrichment/next-vc`

Returns the next investor that needs enrichment. Prioritises `pending` over `not_started`. Uses a database-level lock so multiple agents won't pick the same investor simultaneously.

Returns `404` when there are no investors left to enrich.

**Response — `VC` object**
```json
{
  "id": 89,
  "name": ".406 Ventures",
  "short_description": null,
  "long_description": null,
  "stated_thesis": null,
  "revealed_thesis": null,
  "rounds": ["Seed", "Series A", "Series B"],
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

**`VC` field reference**

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | `external_vc_id` — use in `/enrichment/vc/{vc_id}/complete` |
| `name` | string | Canonical name |
| `short_description` | string \| null | 1–2 sentence summary |
| `long_description` | string \| null | Full research notes |
| `stated_thesis` | string \| null | Thesis as stated by the VC |
| `revealed_thesis` | string \| null | Thesis inferred from portfolio pattern |
| `rounds` | string[] | Investment stages as human-readable enum values |
| `sectors` | string[] | Sectors invested in. `["agnostic"]` if sector-agnostic |
| `ticket_size_min` | number \| null | Minimum cheque size in USD |
| `ticket_size_max` | number \| null | Maximum cheque size in USD |
| `tendency` | string \| null | `"lead"` / `"follow_on"` / `"unsure"` |
| `year_founded` | integer \| null | Year the firm was founded |
| `funds` | VCFund[] | List of named funds raised |
| `location` | string \| null | HQ location e.g. `"Boston, United States"` |
| `geo_focus` | string[] | Countries invested in. `["agnostic"]` if global |
| `website_url` | string | Firm website |
| `status` | string \| null | `"Active"` / `"Inactive"` |
| `slug` | string | URL-safe identifier e.g. `"406-ventures"` |

---

### `POST /enrichment/vc/{vc_id}/complete`

Submits enrichment results for a VC. Replaces all enriched data (members, funds, portfolio companies, portco team) and marks the investor as `completed`.

**Path parameter:** `vc_id` — the integer `id` from the `VC` object returned by `/enrichment/next-vc`.

**Request body — `EnrichedVC` object**

```json
{
  "vc": { },
  "members": [ ],
  "portfolio": [ ],
  "enriched_at": "2026-04-25T12:00:00Z"
}
```

---

#### `vc` — full `VC` object (see field table above)

---

#### `members` — array of `VCMember`

```json
[
  {
    "name": "Greg Dracon",
    "position": "General Partner",
    "expertise": ["Enterprise Software", "Healthcare IT"],
    "description": "Leads investments in B2B SaaS and health tech.",
    "linkedin": "https://linkedin.com/in/gregdracon",
    "email": "greg@406ventures.com",
    "joined_at": "2008-01-01"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Full name |
| `position` | string | Title e.g. `"General Partner"`, `"Principal"` |
| `expertise` | string[] | Areas of focus e.g. `["deeptech", "climate"]`. Filterable |
| `description` | string \| null | Notes on investment focus / reasoning |
| `linkedin` | string \| null | Full LinkedIn URL |
| `email` | string \| null | Contact email |
| `joined_at` | string \| null | ISO date string e.g. `"2019-03-01"` |

---

#### `portfolio` — array of `PortfolioCompany`

```json
[
  {
    "name": "Veracode",
    "overview": "Application security testing platform.",
    "sectors": ["deeptech", "software"],
    "stages": ["Series A", "Series B"],
    "status": "exited",
    "hq": "Burlington, MA",
    "founded_year": 2006,
    "company_size": "201-500",
    "valuation_usd": "$614M",
    "website_url": "https://veracode.com",
    "investment_date": "2009-06-01",
    "team": [
      {
        "name": "Sam King",
        "position": "CEO",
        "description": "Led Veracode through acquisition.",
        "linkedin": "https://linkedin.com/in/samking",
        "email": null
      }
    ]
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Company name |
| `overview` | string \| null | Short description of what the company does |
| `sectors` | string[] | Sectors the company operates in. Filterable |
| `stages` | string[] | Investment stages at which the VC invested e.g. `["Seed", "Series A"]` |
| `status` | string \| null | `"active"` / `"exited"` |
| `hq` | string \| null | Headquarters location e.g. `"London, UK"` |
| `founded_year` | integer \| null | Year company was founded |
| `company_size` | string \| null | Headcount band e.g. `"1-10"`, `"11-50"`, `"51-200"`, `"201-500"`, `"500+"` |
| `valuation_usd` | string \| null | Last known valuation as a string e.g. `"$614M"` |
| `website_url` | string \| null | Company website |
| `investment_date` | string \| null | ISO date string of investment e.g. `"2019-06-01"` |
| `team` | PortcoTeamMember[] | Key people at the company |

**`PortcoTeamMember` fields**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Full name |
| `position` | string \| null | Title e.g. `"CEO"`, `"CTO"` |
| `description` | string \| null | Optional notes |
| `linkedin` | string \| null | Full LinkedIn URL |
| `email` | string \| null | Contact email |

---

#### `funds` — array of `VCFund` (nested inside `vc`)

```json
"funds": [
  {
    "fund_name": ".406 Ventures Fund I",
    "fund_size": 100000000,
    "fund_size_raw": "$100M",
    "vintage_year": 2008
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `fund_name` | string \| null | Name of the fund |
| `fund_size` | number \| null | Size in USD as a number e.g. `100000000` |
| `fund_size_raw` | string \| null | Size as found e.g. `"$100M"` |
| `vintage_year` | integer \| null | Year the fund closed |

---

#### `enriched_at` — ISO 8601 datetime string

```json
"enriched_at": "2026-04-25T12:00:00Z"
```

---

**Complete response**
```json
{
  "status": "completed",
  "vc_id": 89,
  "members_updated": 1,
  "portfolio_updated": 2,
  "funds_updated": 1
}
```

---

## Enum reference

### `InvestmentStage` — used in `VC.rounds` and `PortfolioCompany.stages`

| Value | Meaning |
|-------|---------|
| `"Pre-Seed"` | |
| `"Seed"` | |
| `"Series A"` | |
| `"Series B"` | |
| `"Series C"` | |
| `"Growth"` | Growth / expansion stage |
| `"Late Stage"` | Late-stage / pre-IPO |

### `VCStatus` — used in `VC.status`

| Value |
|-------|
| `"Active"` |
| `"Inactive"` |

### `InvestmentTendency` — used in `VC.tendency`

| Value | Meaning |
|-------|---------|
| `"lead"` | Typically leads rounds |
| `"follow_on"` | Typically follows others |
| `"unsure"` | Pattern unclear |

### `PortcoStatus` — used in `PortfolioCompany.status`

| Value |
|-------|
| `"active"` |
| `"exited"` |

---

## Pagination pattern

All list endpoints follow the same pattern:

```
GET /investors?limit=20&offset=0   → page 1
GET /investors?limit=20&offset=20  → page 2
GET /investors?limit=20&offset=40  → page 3
```

The `count` field in the response is the number of results **in this page**, not the total. To detect the last page, check if `count < limit`.

---

## Error responses

| HTTP status | Meaning |
|-------------|---------|
| `200` | Success |
| `404` | Resource not found (investor_id or vc_id doesn't exist) |
| `422` | Validation error — request body failed Pydantic validation. Response includes field-level errors |
| `500` | Internal server error — check server logs |

**422 example**
```json
{
  "detail": [
    {
      "loc": ["body", "vc", "rounds", 0],
      "msg": "value is not a valid enumeration member",
      "type": "type_error.enum"
    }
  ]
}
```

---

## Data quality notes for frontend

- `needs_review: true` means the investor was deduplicated by name match only (not domain). Surface a warning badge in the UI.
- `enrichment_status: "not_started"` means only raw CSV data is available — `rounds`, `short_description`, `stated_thesis` etc. will likely be `null`.
- `enrichment_status: "completed"` means the agent has run — prefer `rounds` over `stages`, `geo_focus` over `geographies`, `stated_thesis` over `investment_thesis`, `location` over `hq_country`.
- `source_count > 1` means the investor appeared in multiple datasets — higher confidence record.
- Cheque sizes: prefer `ticket_size_min/max` (enrichment) over `first_cheque_min/max` (CSV import) when both are present.
