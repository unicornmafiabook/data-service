# Reorganisation plan

Incremental migration to bounded-context layout. Hybrid is OK at every
step — old raw-SQL routes and new SQLModel/service routes coexist until
each slice is migrated.

## Target architecture

### Per-context layout

```
app/<context>/
├── __init__.py
├── models.py      # SQLModel table classes (DB schema)
├── schemas.py     # Pydantic DTOs (API request/response)
├── service.py     # CRUD / business logic
└── routes.py      # FastAPI router
```

### Shared (not contexts)

- `app/core/config.py` — env settings
- `app/db/session.py` — engine + `get_db`
- `app/importer/` — pure CSV helpers
- `app/main.py` — wires every context router

Cross-context imports are explicit and allowed (e.g. `enrichment.service`
imports `from app.investors.models import Investor`).

### Folder naming

Flat: `app/investors/`, `app/enrichment/`, `app/matching/`, etc.

### Base vs enriched partitioning

Two distinct shapes for VC-like entities, owned by different contexts:

- **Base shape** — CSV-importable / browsable subset. Lives in
  `app/investors/schemas.py`. The `Investor` SQLModel in
  `app/investors/models.py` only carries the columns that belong to the
  base shape, plus DB metadata (`enrichment_status`,
  `last_enriched_at`, timestamps, `external_vc_id` for joins).
- **Enriched shape** — fields populated by the enrichment agent.
  Lives in `app/enrichment/schemas.py`. The enrichment-managed columns
  on the `investors` table (`short_description`, `long_description`,
  `stated_thesis`, `revealed_thesis`, `revealed_thesis_json`,
  `ticket_size_min/max`, `investment_tendency`, `year_founded`,
  `geo_focus`, `sectors`, `geographies`) are **not** modelled in
  SQLModel for this slice — the legacy `POST /complete` route writes
  them via raw SQL. When we migrate that route (slice 2) we'll either
  add a second SQLModel via `__table_args__ = {"extend_existing": True}`
  pointing at the same `investors` table, or split them off into a
  dedicated `investor_enrichment_profile` table.

Concrete base shapes (extracted from the existing API contract):

```python
class InvestmentStage(str, Enum):
    PRE_SEED = "Pre-Seed"
    SEED = "Seed"
    SERIES_A = "Series A"
    SERIES_B = "Series B"
    SERIES_C = "Series C"
    GROWTH = "Growth"
    LATE_STAGE = "Late Stage"


class VCStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class VCMember(BaseModel):
    name: str
    role: str


class PortfolioCompany(BaseModel):
    name: str
    sector: str
    stage: InvestmentStage | None = None
    investment_date: str | None = None
    valuation_usd: str | None = None
    description: str
    url: str | None = None


class VC(BaseModel):
    id: str
    name: str
    rounds: list[InvestmentStage] = []
    location: str | None = None
    sector: str | None = None
    website_url: str
    status: VCStatus | None = None
    slug: str
```

Enriched DTOs (`EnrichedVC`, `EnrichedVCMember`,
`EnrichedPortfolioCompany`, `DeepEnrichedVC`, `EnrichmentSnapshot`,
`VCIdentity`, `VCPreferences`, `RevealedThesis`, `BranchTrace`, …)
live in `app/enrichment/schemas.py`.

### Contexts and table ownership

| Context | HTTP prefix | Owns tables |
|---|---|---|
| `health` | `/health` | — |
| `investors` | `/investors/*` | `investors`, `investor_sources`, `companies`, `investor_company_relationships`, `dedupe_candidates` |
| `enrichment` | `/enrichment/*` | `vc_members`, `vc_funds`, `portfolio_companies`, `portco_team`, `vc_enrichments`, `enrichment_runs` |
| `matching` | `/matching/*` | — (reader only) |
| `indexing` | `/indexing/*` | `retrieval_documents`, `entity_edges`, `portfolio_company_analyses` |
| `ingest` | `/ingest/*` | `import_batches` |

`Investor` is shared but **owned** by `investors`. Other contexts import
it from `app.investors.models`.

## Migration order

Each phase ships independently. Nothing below blocks anything above.

1. **Scaffold** — create empty context folders + `__init__.py` placeholders.
2. **enrichment slice 1 — `GET /enrichment/vc/{vc_id}`** (this session).
3. **Confirm bug behaviour** — round-trip POST `/complete` → GET snapshot against real DB.
4. **enrichment slice 2** — move `POST /complete`.
5. **enrichment slice 3** — move `GET /next-vc` and `GET /stats`; delete `app/api/routes/enrichment.py`.
6. **investors context** — migrate `/investors/*`.
7. **matching, indexing, ingest, health** — same pattern, separate sessions.
8. **Cleanup** — remove `app/api/`, top-level `app/services/`, `app/repositories/`, `app/schemas/`, `app/models/`.

## This session — scope

Only **enrichment slice 1**: `GET /enrichment/vc/{vc_id}` and the
supporting scaffolding.

### Files to create

- `app/db/types.py` — dialect-aware `TypeDecorator`s so the same
  SQLModel classes bind to Postgres in prod and SQLite in tests:
  - `TextArray` → `ARRAY(TEXT)` on Postgres, `JSON` on SQLite (still
    `list[str]` on the Python side).
  - `JsonB` → `JSONB` on Postgres, `JSON` on SQLite.
  - UUIDs use SQLAlchemy 2.0's dialect-aware `sqlalchemy.Uuid` directly.
- `app/db/timestamps.py` — `CreatedAtMixin`, `UpdatedAtMixin`, and the
  combined `TimestampedModel` mixin. Tables inherit the variant that
  matches their on-disk schema.
- `app/investors/__init__.py`
- `app/investors/models.py` — slim `Investor` SQLModel mirroring the
  public `VC` API contract plus queue metadata: `id`, `external_vc_id`,
  `canonical_name`, `slug`, `website_url`, `location`, `sector`,
  `rounds`, `status`, `enrichment_status`, `last_enriched_at`,
  `needs_review`, plus `created_at` / `updated_at` from
  `TimestampedModel`. CSV-import provenance and dedup metadata
  (`description`, `investment_thesis`, `first_cheque_*`,
  `source_names`, `dedupe_*`, `raw_combined`, `funds_raw_json`,
  `normalized_name`, `domain`, `hq_*`, `investor_type`,
  `capital_under_management`, `fund_size_raw`, `deal_count_raw`,
  `confidence_score`, `source_count`, `geographies`, `stages`) and
  enrichment-managed columns (`short_description`, `long_description`,
  `stated_thesis`, `revealed_thesis`, `revealed_thesis_json`,
  `ticket_size_*`, `investment_tendency`, `year_founded`, `geo_focus`,
  agent-overwritten `sectors`) all stay in the prod DB but are not
  mapped here. The legacy raw-SQL routes continue to access them
  directly. Slice 2 (`POST /complete`) will introduce a second
  SQLModel mapped to the same `investors` table via
  `__table_args__ = {"extend_existing": True}` exposing the
  enrichment-managed subset.
- `app/investors/schemas.py` — base API DTOs: `InvestmentStage`,
  `VCStatus`, `VCMember` (`name`, `role`), `PortfolioCompany` (base
  shape per snippet above), `VC` (base shape per snippet above).
- `app/enrichment/__init__.py`
- `app/enrichment/models.py` — SQLModel tables owned by enrichment:
  `VCMember`, `VCFund`, `PortfolioCompany`, `PortcoTeamMember`,
  `VCEnrichment`. Each inherits `CreatedAtMixin` (or
  `TimestampedModel` for `VCEnrichment`).
- `app/enrichment/schemas.py` — enriched DTOs absorbed from the
  legacy `app/models/enrichment.py` (`EnrichedVC`, `DeepEnrichedVC`,
  `EnrichedVCProfile`, `EnrichedVCMember`,
  `EnrichedPortfolioCompany`, `RevealedThesis`, `BranchTrace`,
  `SourceInfo`, `TicketSize`, `FundRecord`, `VCIdentity`,
  `VCPreferences`), plus new response DTOs for the snapshot
  endpoint (`EnrichmentSnapshot`, `EnrichmentInvestorSummary`,
  `EnrichmentMember`, `EnrichmentFund`, `EnrichmentPortcoTeamMember`,
  `EnrichmentPortfolioCompany`).
- `app/enrichment/service.py` — `get_enrichment_snapshot(db, external_vc_id)`
  + `seed_enrichment_for_investor(db, external_vc_id, …)` test/setup helper.
- `app/enrichment/routes.py` — new router with just `GET /vc/{vc_id}`.
- `tests/__init__.py`
- `tests/conftest.py` — SQLite engine + SQLModel session + FastAPI
  `TestClient` fixtures (see **Tests** section below).
- `tests/enrichment/__init__.py`
- `tests/enrichment/test_snapshot_service.py` — service-level tests.
- `tests/enrichment/test_snapshot_routes.py` — route-level tests.

### Files to update

- `app/main.py` — include the new enrichment router.
- `app/api/routes/enrichment.py` — remove only the `get_enrichment`
  handler (keep `get_next_vc`, `complete_enrichment`, `enrichment_stats`
  untouched). Re-point its `from app.schemas.enrichment import …` to the
  new location `from app.enrichment.schemas import …`.
- `pyproject.toml` — add `pytest` and `httpx` to a `[dependency-groups]
  dev` group via `uv add --dev`.

### Files to remove

- `app/schemas/enrichment.py` — content folds into
  `app/enrichment/schemas.py`.
- `app/db/tables/` — SQLModel tables move into each context's
  `models.py`.
- `app/models/enrichment.py` — already deleted in the previous turn;
  verify nothing re-imports from it.

### Router registration in `app/main.py`

Both old and new enrichment routers register under `/enrichment`. The
new router handles only the migrated path; FastAPI dispatches by path,
so there is no collision.

### Dev dependencies to add

Via `uv add --dev pytest httpx`:

- `pytest` — test runner.
- `httpx` — required by FastAPI's `TestClient`.

## Acceptance criteria — enrichment slice 1

Every AC below is realised as at least one test in
`tests/enrichment/test_snapshot.py`.

### AC-1 — Happy path

- **Given** a VC with `external_vc_id=N` and seeded enriched rows
  (1 investor, ≥1 vc_members, ≥1 vc_funds, ≥1 portfolio_companies each
  with ≥1 portco_team rows, 1 vc_enrichments row).
- **When** `GET /enrichment/vc/N`.
- **Then** the response is `200 OK` and the JSON has exactly the
  top-level keys `investor`, `enriched_at`, `members`, `funds`,
  `portfolio`.
- **And** `investor` contains `id` (stringified UUID), `canonical_name`,
  `enrichment_status`, `last_enriched_at`.
- **And** each `members[i]` has `name`, `position`, `expertise` (list),
  `description`, `linkedin`, `email`, `joined_at`.
- **And** each `funds[i]` has `fund_name`, `fund_size`, `fund_size_raw`,
  `vintage_year`.
- **And** each `portfolio[i]` has `name`, `overview`, `sectors`,
  `stages`, `status`, `hq`, `founded_year`, `company_size`,
  `valuation_usd`, `website_url`, `investment_date`, `team`.

### AC-2 — Unknown VC returns 404

- **Given** no investor with `external_vc_id=N`.
- **When** `GET /enrichment/vc/N`.
- **Then** the response is `404` with a meaningful `detail`.

### AC-3 — Investor exists but no enrichment yet

- **Given** an investor with `external_vc_id=N`, but no rows in
  `vc_enrichments`, `vc_members`, `vc_funds`, or `portfolio_companies`.
- **When** `GET /enrichment/vc/N`.
- **Then** the response is `200 OK`.
- **And** `enriched_at` is `null`.
- **And** `members`, `funds`, `portfolio` are each `[]`.

### AC-4 — Portfolio company with no team

- **Given** a portfolio company with no rows in `portco_team`.
- **When** `GET /enrichment/vc/N`.
- **Then** that entry's `team` is `[]` (list, not `null`, not the string
  `'[]'`).

### AC-5 — Round-trip parity (bug verification)

- **Given** rows seeded directly to mimic exactly what
  `POST /enrichment/vc/{id}/complete` writes today:
  - `vc_members.expertise = ['Enterprise Software']` (single-element
    array, because the legacy code wraps `area_of_expertise`).
  - `portfolio_companies.stage = ['Series B']` (single-element array,
    because legacy wraps `investment_stage`).
  - `portco_team` rows attached via `portfolio_company_id`.
  - `vc_enrichments.enriched_at` set to a known timestamp.
- **When** `GET /enrichment/vc/N`.
- **Then** every seeded field is surfaced with correct typing:
  - `members[0].expertise == ['Enterprise Software']`.
  - `portfolio[0].stages == ['Series B']`.
  - `portfolio[0].team` is a list with the expected dict entries.
  - `enriched_at` equals the seeded timestamp (as an ISO string in JSON).

### AC-6 — JSON shape matches the pre-refactor response

- **Given** the same seed as AC-1.
- **When** we serialise the new service's
  `EnrichmentSnapshot.model_dump(mode="json")`.
- **Then** it deeply equals a frozen expected snapshot checked into the
  test file that matches the legacy endpoint's historical shape
  (same top-level keys, same field names per row).

The legacy implementation can't be executed on SQLite (it uses
Postgres-only `json_agg` / `json_build_object`), so we compare against
a pinned expected dict rather than running both side-by-side. The
pinned shape is captured from a manual `curl` against the real DB on
the current `main` and is documented in the test file header.

### AC-7 — No collateral damage

- **When** `app.main:app` is imported.
- **Then** no `ImportError`.
- **And** all other `/enrichment/*` routes (`GET /next-vc`,
  `POST /vc/{id}/complete`, `GET /stats`) are still registered on the
  app.

## Tests

### Layout

```
tests/
├── __init__.py
├── conftest.py                  # SQLite engine + session + TestClient fixtures
└── enrichment/
    ├── __init__.py
    └── test_snapshot.py         # AC-1 … AC-7
```

### Strategy

- In-memory SQLite (`sqlite:///:memory:`) via SQLAlchemy, one fresh
  engine per test via a pytest fixture.
- `SQLModel.metadata.create_all(engine)` creates the schema from the
  new `app.<context>.models` definitions.
- FastAPI `TestClient` with the `get_db` dependency overridden to yield
  the test session.

### Fixtures (in `conftest.py`)

- `engine` — function-scoped in-memory SQLite engine; imports every
  `app.*.models` module so SQLModel's metadata is populated before
  `create_all`.
- `session` — fresh SQLModel `Session` bound to `engine`, rolled back
  at end.
- `client` — FastAPI `TestClient` with `app.dependency_overrides` set
  so `get_db` yields `session`.
- `seed_enriched_vc(session, external_vc_id=89)` — helper function (not
  a fixture) that inserts a full enriched VC mirroring
  `POST /complete`'s write shape. Returns the seeded IDs.

### Why the new service avoids Postgres-only SQL

The legacy endpoint builds portfolio-with-team in one query using
`json_agg(json_build_object(...)) FILTER (WHERE ...) COALESCE ... '[]'`.
This is a code smell:

- couples SQL to API response shape;
- Postgres-only — SQLite / other DBs / test harnesses can't run it;
- `COALESCE(json, text)` relies on an implicit text → json cast that
  has bitten drivers before;
- no type safety on the nested JSON keys.

The new service does two typed `SELECT`s (portcos, then team members
for those portcos) and assembles the nested response in Python with
Pydantic DTOs. Still 2 round-trips, not N+1. Dialect-agnostic. Every
column typed.

### Caveats

- The `Investor` SQLModel must declare every column the enrichment
  service `SELECT`s, otherwise the test insert fails silently.
- Complex Postgres-only features in **other** endpoints (array `&&`,
  `to_tsvector`, pg_trgm, etc.) still need Postgres to test. Out of
  scope for this slice.

### Running

```
uv run pytest tests/enrichment/test_snapshot.py -v
```

## Verification

After this session's changes:

1. `uv run pytest tests/enrichment/test_snapshot.py -v` — all AC tests
   pass.
2. `app/main.py` imports without error.
3. `ruff check app/ tests/` passes on the new code.
4. `pyright` has no new diagnostics.
5. Manual against real DB (needs user creds): `GET /enrichment/vc/{id}`
   returns the same JSON shape as before for a known-enriched VC.
6. Real-DB round-trip: `POST /enrichment/vc/{id}/complete` with a known
   body, then `GET /enrichment/vc/{id}`, confirm every field posted is
   reflected. Document anything missing.

## Open items (deferred)

- The committed Alembic migration
  `alembic/versions/2026_04_26_0806-92c62c6e5c94_initial_investors.py`
  was autogenerated against the previous wide `Investor` model. It is
  now stale (creates ~30 columns that aren't on the slim model).
  Tests don't run alembic — they use
  `SQLModel.metadata.create_all(engine)` against the slim model — so
  this drift doesn't break the test suite. Regenerate the migration
  via `uv run alembic revision --autogenerate -m "investors_slim"`
  against an empty DB when convenient.
- Whether `portfolio_companies.stage` is actually `TEXT` or `TEXT[]` in
  the live DB — migration v2 uses `ADD COLUMN IF NOT EXISTS` which is a
  no-op if the column already existed as `TEXT` from the original
  migration. Check once we have DB access. The new service uses
  `TextArray` in the SQLModel regardless; if the live column is
  actually `TEXT` the insert path (`POST /complete`) may be writing
  stringified arrays. That's a slice-2 investigation.
- Move `app/models/investors.py` DTOs into `app/investors/schemas.py`
  (deferred to the investors-context migration).
- Move `app/schemas/matching.py` into `app/matching/schemas.py`
  (deferred to the matching-context migration).
