CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS investors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    normalized_name TEXT,
    website TEXT,
    domain TEXT,
    investor_type TEXT,
    status TEXT,
    hq_city TEXT,
    hq_country TEXT,
    hq_address TEXT,
    stages TEXT[] DEFAULT '{}',
    sectors TEXT[] DEFAULT '{}',
    geographies TEXT[] DEFAULT '{}',
    first_cheque_min NUMERIC,
    first_cheque_max NUMERIC,
    first_cheque_currency TEXT,
    capital_under_management NUMERIC,
    fund_size_raw TEXT,
    deal_count_raw TEXT,
    funds_raw_json JSONB,
    description TEXT,
    investment_thesis TEXT,
    source_names TEXT[] DEFAULT '{}',
    source_count INT DEFAULT 1,
    dedupe_key TEXT,
    dedupe_confidence NUMERIC DEFAULT 0.8,
    confidence_score NUMERIC DEFAULT 0.8,
    enrichment_status TEXT DEFAULT 'not_started',
    last_enriched_at TIMESTAMP,
    needs_review BOOLEAN DEFAULT FALSE,
    raw_combined JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_investors_updated_at') THEN
        CREATE TRIGGER trg_investors_updated_at
        BEFORE UPDATE ON investors
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS investor_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_id UUID REFERENCES investors(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    source_row_id TEXT,
    original_name TEXT,
    original_website TEXT,
    raw_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    normalized_name TEXT,
    website TEXT,
    domain TEXT,
    description TEXT,
    sector TEXT,
    sub_sector TEXT,
    hq_city TEXT,
    hq_country TEXT,
    founded_year INT,
    company_stage TEXT,
    enrichment_status TEXT DEFAULT 'not_started',
    last_enriched_at TIMESTAMP,
    needs_review BOOLEAN DEFAULT FALSE,
    raw_enrichment JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_companies_updated_at') THEN
        CREATE TRIGGER trg_companies_updated_at
        BEFORE UPDATE ON companies
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS investor_company_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_id UUID NOT NULL REFERENCES investors(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    relationship_type TEXT DEFAULT 'portfolio',
    investment_stage TEXT,
    investment_round TEXT,
    investment_date DATE,
    is_lead_investor BOOLEAN,
    source TEXT,
    confidence_score NUMERIC DEFAULT 0.8,
    raw_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (investor_id, company_id)
);

CREATE TABLE IF NOT EXISTS enrichment_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type TEXT NOT NULL,
    target_id UUID NOT NULL,
    status TEXT DEFAULT 'pending',
    agent_name TEXT,
    model_name TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    input_json JSONB DEFAULT '{}'::jsonb,
    output_json JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    confidence_score NUMERIC
);

CREATE TABLE IF NOT EXISTS dedupe_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_a_id UUID REFERENCES investors(id) ON DELETE CASCADE,
    investor_b_id UUID REFERENCES investors(id) ON DELETE CASCADE,
    investor_a_name TEXT,
    investor_b_name TEXT,
    investor_a_domain TEXT,
    investor_b_domain TEXT,
    match_score NUMERIC,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_name TEXT NOT NULL,
    source_file_name TEXT,
    source_name TEXT,
    rows_seen INT DEFAULT 0,
    rows_imported INT DEFAULT 0,
    rows_failed INT DEFAULT 0,
    status TEXT DEFAULT 'started',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_investors_domain ON investors(domain);
CREATE INDEX IF NOT EXISTS idx_investors_normalized_name ON investors(normalized_name);
CREATE INDEX IF NOT EXISTS idx_investors_dedupe_key ON investors(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_investors_stages ON investors USING GIN(stages);
CREATE INDEX IF NOT EXISTS idx_investors_sectors ON investors USING GIN(sectors);
CREATE INDEX IF NOT EXISTS idx_investors_geographies ON investors USING GIN(geographies);
CREATE INDEX IF NOT EXISTS idx_investors_raw_combined ON investors USING GIN(raw_combined);
CREATE INDEX IF NOT EXISTS idx_sources_raw_data ON investor_sources USING GIN(raw_data);
CREATE INDEX IF NOT EXISTS idx_sources_investor_id ON investor_sources(investor_id);
CREATE INDEX IF NOT EXISTS idx_sources_source_name ON investor_sources(source_name);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_normalized_name ON companies(normalized_name);
CREATE INDEX IF NOT EXISTS idx_relationships_investor_id ON investor_company_relationships(investor_id);
CREATE INDEX IF NOT EXISTS idx_relationships_company_id ON investor_company_relationships(company_id);
CREATE INDEX IF NOT EXISTS idx_investors_enrichment_status ON investors(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_companies_enrichment_status ON companies(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_enrichment_runs_target ON enrichment_runs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_enrichment_runs_status ON enrichment_runs(status);

CREATE UNIQUE INDEX IF NOT EXISTS unique_investor_domain_not_null
ON investors(domain)
WHERE domain IS NOT NULL AND domain <> '';

CREATE UNIQUE INDEX IF NOT EXISTS unique_company_domain_not_null
ON companies(domain)
WHERE domain IS NOT NULL AND domain <> '';
