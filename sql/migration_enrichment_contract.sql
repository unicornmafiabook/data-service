-- Migration: enrichment contract
-- Adds columns to investors and creates vc_members, portfolio_companies, vc_enrichments.

-- 1. New columns on investors
ALTER TABLE investors
    ADD COLUMN IF NOT EXISTS external_vc_id BIGINT,
    ADD COLUMN IF NOT EXISTS rounds         TEXT[]  DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS location       TEXT,
    ADD COLUMN IF NOT EXISTS sector         TEXT,
    ADD COLUMN IF NOT EXISTS website_url    TEXT,
    ADD COLUMN IF NOT EXISTS slug           TEXT;

-- Sequence to back external_vc_id
CREATE SEQUENCE IF NOT EXISTS investors_external_vc_id_seq;

-- Assign sequential ids to all existing rows
UPDATE investors
SET external_vc_id = nextval('investors_external_vc_id_seq')
WHERE external_vc_id IS NULL;

-- Set sequence ownership so future inserts auto-increment
ALTER SEQUENCE investors_external_vc_id_seq OWNED BY investors.external_vc_id;

ALTER TABLE investors
    ALTER COLUMN external_vc_id SET DEFAULT nextval('investors_external_vc_id_seq');

CREATE UNIQUE INDEX IF NOT EXISTS unique_investors_external_vc_id ON investors(external_vc_id);

-- 2. Backfill derived columns from existing data
UPDATE investors SET
    website_url = website,
    location = CASE
        WHEN hq_city IS NOT NULL AND hq_country IS NOT NULL THEN hq_city || ', ' || hq_country
        WHEN hq_country IS NOT NULL THEN hq_country
        ELSE hq_city
    END,
    sector = CASE WHEN array_length(sectors, 1) > 0 THEN sectors[1] ELSE NULL END,
    slug = LOWER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(canonical_name, '[^a-zA-Z0-9\s]', '', 'g'),
            '\s+', '-', 'g'
        )
    );

-- Backfill rounds from stages using enum mapping
UPDATE investors SET rounds = (
    SELECT COALESCE(array_agg(mapped ORDER BY mapped), '{}')
    FROM (
        SELECT CASE s
            WHEN 'pre_seed'  THEN 'Pre-Seed'
            WHEN 'seed'      THEN 'Seed'
            WHEN 'series_a'  THEN 'Series A'
            WHEN 'series_b'  THEN 'Series B'
            WHEN 'series_c'  THEN 'Series C'
            WHEN 'growth'    THEN 'Growth'
        END AS mapped
        FROM unnest(stages) AS s
        WHERE s IN ('pre_seed', 'seed', 'series_a', 'series_b', 'series_c', 'growth')
    ) t
);

-- 3. vc_members
CREATE TABLE IF NOT EXISTS vc_members (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vc_id      BIGINT NOT NULL,
    name       TEXT   NOT NULL,
    role       TEXT   NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vc_members_vc_id ON vc_members(vc_id);

-- 4. portfolio_companies
CREATE TABLE IF NOT EXISTS portfolio_companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vc_id           BIGINT NOT NULL,
    name            TEXT   NOT NULL,
    sector          TEXT   NOT NULL,
    stage           TEXT,
    investment_date TEXT,
    valuation_usd   TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolio_companies_vc_id ON portfolio_companies(vc_id);

-- 5. vc_enrichments
CREATE TABLE IF NOT EXISTS vc_enrichments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vc_id       BIGINT    NOT NULL UNIQUE,
    enriched_at TIMESTAMP NOT NULL,
    raw_payload JSONB     NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vc_enrichments_vc_id ON vc_enrichments(vc_id);

-- 6. Index for enrichment queue lookups
CREATE INDEX IF NOT EXISTS idx_investors_enrichment_queue
    ON investors(enrichment_status, created_at)
    WHERE enrichment_status IN ('not_started', 'pending');
