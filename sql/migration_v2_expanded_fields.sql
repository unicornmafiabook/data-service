-- Migration v2: expanded fields for full enrichment contract

-- 1. investors: new enrichment columns
ALTER TABLE investors
    ADD COLUMN IF NOT EXISTS short_description    TEXT,
    ADD COLUMN IF NOT EXISTS long_description     TEXT,
    ADD COLUMN IF NOT EXISTS stated_thesis        TEXT,
    ADD COLUMN IF NOT EXISTS revealed_thesis      TEXT,
    ADD COLUMN IF NOT EXISTS investment_tendency  TEXT,
    ADD COLUMN IF NOT EXISTS year_founded         INT,
    ADD COLUMN IF NOT EXISTS geo_focus            TEXT[]  DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS ticket_size_min      NUMERIC,
    ADD COLUMN IF NOT EXISTS ticket_size_max      NUMERIC;

-- Backfill from existing columns
UPDATE investors SET
    stated_thesis    = investment_thesis    WHERE stated_thesis    IS NULL AND investment_thesis IS NOT NULL;
UPDATE investors SET
    geo_focus        = geographies          WHERE geo_focus = '{}'  AND geographies <> '{}';
UPDATE investors SET
    ticket_size_min  = first_cheque_min,
    ticket_size_max  = first_cheque_max
WHERE ticket_size_min IS NULL AND first_cheque_min IS NOT NULL;

-- 2. vc_members: add all new fields (keep existing role column, drop its NOT NULL)
ALTER TABLE vc_members ALTER COLUMN role DROP NOT NULL;
ALTER TABLE vc_members
    ADD COLUMN IF NOT EXISTS position    TEXT,
    ADD COLUMN IF NOT EXISTS expertise   TEXT[]  DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS linkedin    TEXT,
    ADD COLUMN IF NOT EXISTS email       TEXT,
    ADD COLUMN IF NOT EXISTS joined_at   DATE;

-- Backfill position from role for any existing rows
UPDATE vc_members SET position = role WHERE position IS NULL AND role IS NOT NULL;

-- 3. portfolio_companies: add all new fields (sector was NOT NULL, relax since sectors[] replaces it)
ALTER TABLE portfolio_companies ALTER COLUMN sector DROP NOT NULL;
ALTER TABLE portfolio_companies
    ADD COLUMN IF NOT EXISTS overview      TEXT,
    ADD COLUMN IF NOT EXISTS stage         TEXT[]  DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS sectors       TEXT[]  DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS status        TEXT,
    ADD COLUMN IF NOT EXISTS hq            TEXT,
    ADD COLUMN IF NOT EXISTS founded_year  INT,
    ADD COLUMN IF NOT EXISTS company_size  TEXT,
    ADD COLUMN IF NOT EXISTS website_url   TEXT;

-- Backfill sectors from single sector column
UPDATE portfolio_companies
SET sectors = ARRAY[sector]
WHERE sector IS NOT NULL AND (sectors = '{}' OR sectors IS NULL);

-- 4. vc_funds: structured fund list per VC
CREATE TABLE IF NOT EXISTS vc_funds (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vc_id         BIGINT NOT NULL,
    fund_name     TEXT,
    fund_size     NUMERIC,
    fund_size_raw TEXT,
    vintage_year  INT,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vc_funds_vc_id ON vc_funds(vc_id);

-- 5. portco_team: executives / team members at portfolio companies
CREATE TABLE IF NOT EXISTS portco_team (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_company_id UUID NOT NULL REFERENCES portfolio_companies(id) ON DELETE CASCADE,
    name                 TEXT NOT NULL,
    position             TEXT,
    description          TEXT,
    linkedin             TEXT,
    email                TEXT,
    created_at           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portco_team_portfolio_company_id ON portco_team(portfolio_company_id);
