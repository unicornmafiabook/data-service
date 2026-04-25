# VC Data Service

Focused microservice for the VC database side of the hackathon build.

It handles:

- importing four unstandardised VC CSV files;
- normalising names, websites, stages, sectors, geographies and cheque sizes;
- deduplicating investors into one canonical `investors` table;
- preserving every original row in `investor_sources`;
- extracting obvious portfolio companies into `companies`;
- linking investors to portfolio companies;
- exposing FastAPI endpoints for the agent/front-end to query.

It does **not** handle the main AI agent, frontend, auth, or heavy enrichment scraping.

## Architecture

```text
CSV files
   ↓
Importer
   ↓
Supabase Postgres
   ↓
FastAPI VC Data Service
   ↓
Agent / frontend / other microservices
```

## Setup

```bash
cd vc-data-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your Supabase Postgres connection string to `.env`:

```env
DATABASE_URL=postgresql+psycopg2://postgres:[PASSWORD]@[HOST]:5432/postgres
```

Run `sql/schema.sql` in Supabase SQL Editor first.

## Data files

Place your CSVs here:

```text
data/raw/source_1.csv
data/raw/source_2.csv
data/raw/source_3.csv
data/raw/source_4.csv
```

Expected mappings:

| File | Main columns |
|---|---|
| `source_1.csv` | `id`, `name`, `round`, `location`, `sector`, `website`, `status`, `slug` |
| `source_2.csv` | `accountId`, `name`, `memberType`, `city`, `country`, `address`, `websiteUrl`, `typeOfCompany`, `capitalUnderManagement`, `financingStages`, `industrySector`, `profile`, `geoPreferences`, `funds_json` |
| `source_3.csv` | `name`, `website`, `portfolio`, `fundSize`, `dealCount` |
| `source_4.csv` | `Investor name`, `Website`, `Global HQ`, `Countries of investment`, `Stage of investment`, `Ivestment thesis`, `Investor type`, `First cheque minimum`, `First cheque maximum` |

`source_4` supports both `Ivestment thesis` and `Investment thesis`.

## Import

Dry run:

```bash
python scripts/import_vc_data.py --dry-run
```

Real import:

```bash
python scripts/import_vc_data.py
```

Reset imported investor/company data and import again:

```bash
python scripts/import_vc_data.py --reset
```

## Run API

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Main endpoints

```text
GET  /health
GET  /investors
GET  /investors/search
GET  /investors/{investor_id}
GET  /investors/{investor_id}/portfolio
POST /investors/{investor_id}/mark-for-enrichment
POST /ingest/run?dry_run=true
```

Example search:

```text
/investors/search?stage=seed&sector=fintech&geography=United Kingdom&cheque_max=500000
```

## Microservice boundary

Other services should call this API rather than connecting directly to Supabase.

```text
frontend / agent / enrichment service
        ↓
VC Data Service API
        ↓
Supabase Postgres
```
