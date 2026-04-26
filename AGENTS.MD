# Data Service — AI Agent Instructions

This file is a **router**. It defines the non-negotiable contract, code style, and a table
that maps each task to the skill files the agent must load before acting.

Every feature — models, services, API routes — is built through the
**SKELETON → RED → GREEN → REFACTOR** loop. No exceptions.

---

## NON-NEGOTIABLE: Run the linter after every file edit

After **every** file edit — no matter how small — run:

```
scripts/lint.sh <edited-file>
```

This runs `ruff` + `pyright` on the file and emits compact, one-line-per-issue output.
**Do not proceed to the next step until the output is `LINT OK`.**
Fix all reported issues before continuing.

---

## OC Rules — mandatory, no exceptions

All 9 Object Calisthenics rules apply to every line of code — source and tests alike.
If a rule conflicts with a design, the design changes. The rule never bends.

1. **One level of indentation per method** — extract helper methods when you need to go deeper.
2. **No `else` keyword** — use early returns and guard clauses instead.
3. **Wrap all primitives and strings** — use `pydantic.BaseModel` for value objects that carry domain meaning. Schema fields that carry no meaning beyond their type may stay primitive.
4. **First-class collections** — wrap any collection that has behaviour in its own class.
5. **One dot per line** — `a.b.c` is two dots too many; assign intermediates.
6. **No abbreviations** — `investor_id`, not `inv_id`; `portfolio_company`, not `pc`.
7. **Keep entities small** — class ≤ 50 lines, method ≤ 5 lines.
8. **No more than two instance variables per class** — if you need more, extract a value object.
9. **No getters, setters, or properties that expose internals** — tell, don't ask.

---

## Skill Router

**Before writing anything**, identify the task and load the matching skills. Skills live in
`.devin/skills/<skill-name>/SKILL.md`.

| Task | Skills to load (in order) |
|------|---------------------------|
| Add a new feature end-to-end | `feature-workflow` → `tdd-workflow` → layer skill (`api-routes`) → test skill (`testing-unit` / `testing-integration`) |
| Add or modify a FastAPI endpoint | `api-routes` → `tdd-workflow` → `testing-integration` |
| Add or modify a service method | `tdd-workflow` → `testing-unit` |
| Write unit tests for services | `testing-unit` → `tdd-workflow` |
| Write integration tests (API, repo) | `testing-integration` → `tdd-workflow` |
| Refactor a service | `tdd-workflow` → `testing-unit` |
| Any code change of any kind | `tdd-workflow` (always) |

The router is additive — if multiple rows match, load all referenced skills.

This repo uses **Simplified 3-Layer** architecture for every feature. There is no
Full DDD path here — no separate `domain/` entities or repository interfaces. Models
centralise field-level validation and own their state transitions; services orchestrate
DB sessions and cross-record rules; routes are thin HTTP wrappers.

---

## Code Writing Style (applies everywhere, no skill needed)

### Type hints — mandatory on every method

All methods, including private helpers, must carry complete type annotations:

- Return type on every method, including `__init__` (`-> None`) and void helpers.
- All parameters typed — no exceptions for private methods.
- Use native syntax: `list[str]`, `dict[str, int]`, `str | None`.
- Do **not** use `typing.List`, `typing.Dict`, `typing.Optional`.

```python
# ✅ correct
def _reject_non_positive(self, value: int) -> None:
    if value <= 0:
        raise ValueError("must be positive")

# ❌ wrong — missing return type and parameter types
def _normalise_sector(self, raw):
    return raw.strip().lower()
```

### Imports — MANDATORY MODULE LEVEL ONLY

- **ALL imports MUST be at module level** — NEVER inside functions, methods, fixtures, or any code block.
- Zero exceptions for convenience. Circular imports? Refactor the modules.
- This rule applies everywhere: source code, tests, fixtures, async functions.
- Absolute imports from `app.*`.

```python
# ❌ WRONG — NEVER DO THIS
async def my_fixture():
    from app.enrichment.service import get_enrichment_snapshot
    return get_enrichment_snapshot(...)

# ✅ CORRECT — ALWAYS DO THIS
from app.enrichment.service import get_enrichment_snapshot

async def my_fixture():
    return get_enrichment_snapshot(...)
```

### Docstrings — NumPy format on public methods

```python
def get_enrichment_snapshot(db: Session, external_vc_id: int) -> EnrichmentSnapshot:
    """
    Return the full enrichment snapshot for a VC.

    Parameters
    ----------
    db : Session
        SQLAlchemy session bound to the active engine.
    external_vc_id : int
        Legacy integer VC id the frontend knows about.

    Returns
    -------
    EnrichmentSnapshot
        Top-level investor + members + funds + portfolio payload.

    Raises
    ------
    InvestorNotFoundError
        When no investor has the supplied external_vc_id.
    """
```

### Value objects

- **Value objects with domain meaning use `pydantic.BaseModel`** — place them in the
  owning context's `schemas.py`.
- Enforce domain constraints via `@field_validator` or `@model_validator`.
- Plain transport schemas (request/response DTOs) also live in `schemas.py`.

### Naming conventions

- **Variables / functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_single_underscore`
- Descriptive names — no single letters, no abbreviations (see OC rule 6).

### Comments and errors

- Prefer self-documenting code; explain *why*, not *what*.
- Always include error messages explaining what went wrong.
- Document all raised exceptions in docstrings.

### Logging

```python
from loguru import logger
```

`loguru` for dev-time logs. Log **structured** context (ids, counts), not free prose.

### Packages

Use `uv` for all package management — never `pip install` directly.

```bash
uv add <package>             # runtime dependency
uv add --dev <package>       # dev dependency
uv run pytest tests/ -v      # run tests
uv run python -m app.main    # run app in the uv-managed venv
```

---

## Architecture Overview

This is a **FastAPI microservice** over **SQLModel + PostgreSQL** (Supabase in prod,
SQLite in tests). Code is organised into **bounded contexts** under `app/`, each owning
its own models, schemas, service, and routes.

### Target layout (per `plan.md`)

```
app/<context>/
├── __init__.py
├── models.py      # SQLModel table classes (DB schema + field-level validation)
├── schemas.py     # Pydantic DTOs (API request/response, value objects)
├── service.py     # Orchestration — sessions, cross-record rules, transactions
└── routes.py      # FastAPI router — thin HTTP wrappers over service
```

### Shared (not contexts)

- `app/core/config.py` — env settings
- `app/db/session.py` — engine + `get_db`
- `app/db/types.py` — dialect-aware `TypeDecorator`s (Postgres ↔ SQLite parity)
- `app/importer/` — pure CSV helpers
- `app/main.py` — wires every context router

### Contexts and table ownership

| Context | HTTP prefix | Owns tables |
|---|---|---|
| `health` | `/health` | — |
| `investors` | `/investors/*` | `investors`, `investor_sources`, `companies`, `investor_company_relationships`, `dedupe_candidates` |
| `enrichment` | `/enrichment/*` | `vc_members`, `vc_funds`, `portfolio_companies`, `portco_team`, `vc_enrichments`, `enrichment_runs` |
| `matching` | `/matching/*` | — (reader only) |
| `indexing` | `/indexing/*` | `retrieval_documents`, `entity_edges`, `portfolio_company_analyses` |
| `ingest` | `/ingest/*` | `import_batches` |

`Investor` is shared but **owned** by `investors`. Other contexts import it from
`app.investors.models`. Cross-context imports are explicit and allowed.

### Migration note

An older flat layout (`app/api/routes/*.py`, `app/services/*.py`, `app/models/*.py`,
`app/schemas/*.py`, `app/repositories/*.py`) is being incrementally retired in favour
of per-context folders. **New code goes into `app/<context>/`.** Existing flat-layout
code may be edited in place until its slice is migrated.

### Critical principles

- **Import direction**: `routes` → `service` → `models`. Never the reverse.
- **Routes are thin HTTP wrappers** — they deserialise, call the service, translate
  domain errors to `HTTPException`, return a schema. No business logic.
- **Services manage sessions** — they take a `Session` (or accept one from `Depends(get_db)`
  via the route) and never split a unit of work across routes.
- **Models enforce field-level rules** — validation of a single field's shape or range
  lives in the SQLModel via `@field_validator`. Cross-record rules live in the service.

---

## External Dependencies

- **Database**: PostgreSQL (Supabase in prod) via `psycopg2-binary` + SQLAlchemy/SQLModel.
- **ORM**: SQLModel (Pydantic + SQLAlchemy).
- **Testing DB**: In-memory SQLite — dialect differences covered by `app/db/types.py`.
- **HTTP client for tests**: `httpx` (required by FastAPI `TestClient`).
- **Test runner**: `pytest` via `uv run pytest`.
- **Type checker**: `pyright` (configured via `pyrightconfig.json`).
- **Linter / formatter**: `ruff`.
- **AI agents (where used)**: `pydantic-ai` — for LLM-driven helpers, not for transport logic.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `AGENTS.MD` | This file — the router (non-negotiable contract + skill map) |
| `FACTORY.md` | Output contract + structural invariants for the test-writer/implementer agents |
| `.devin/skills/<name>/SKILL.md` | Loadable skill docs |
| `.devin/agents/test-writer.agent.md` | RED-phase agent guide |
| `.devin/agents/implementer.agent.md` | GREEN-phase agent guide |
| `prompts/templates/simplified/create/<task>.md` | Spec templates for new features |
| `prompts/templates/simplified/update/<task>.md` | Spec templates for modifying existing features |
| `scripts/lint.sh` | `ruff` + `pyright`; must return `LINT OK` after every edit |
| `app/main.py` | FastAPI bootstrap, wires every context router |
| `app/db/session.py` | Engine + `get_db` dependency |
| `app/core/config.py` | Environment settings |
| `pyproject.toml` | Python 3.13, uv-managed |
| `tests/conftest.py` | SQLite + `TestClient` fixtures |
| `plan.md` | Target per-context layout + migration order |

---

## Common Pitfalls

1. **Don't skip the lint gate.** `scripts/lint.sh <file>` after every edit, full stop.
2. **Don't write code without first completing the SKELETON → RED → GREEN loop.**
3. **Don't put business logic in routes.** Thin wrappers only — delegate to the service.
4. **Don't mix contexts.** A service in `app/enrichment/service.py` may import
   `from app.investors.models import Investor`, but it must not write to investor tables.
5. **Don't bypass services in tests.** Use the service's public methods to set up data —
   that's what production does and it catches integration bugs.
6. **Don't hardcode config.** All env values go through `app.core.config`.
7. **Don't use Postgres-only SQL in SQLModel definitions** without a dialect-aware
   `TypeDecorator` in `app/db/types.py` — tests run on SQLite.
8. **Don't assume `typing.List` / `typing.Optional`** — this project uses native
   `list[...]` / `X | None` only.
