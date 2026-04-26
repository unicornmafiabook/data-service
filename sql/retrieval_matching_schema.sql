CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE investors
    ADD COLUMN IF NOT EXISTS revealed_thesis_json JSONB DEFAULT '{}'::jsonb;

ALTER TABLE vc_enrichments
    ADD COLUMN IF NOT EXISTS depth TEXT,
    ADD COLUMN IF NOT EXISTS branch_traces JSONB DEFAULT '[]'::jsonb;

DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'pgvector extension unavailable; retrieval_documents will be created without embeddings.';
END;
$$;

CREATE TABLE IF NOT EXISTS retrieval_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    investor_id UUID REFERENCES investors(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    keywords TEXT[] DEFAULT '{}',
    sectors TEXT[] DEFAULT '{}',
    stages TEXT[] DEFAULT '{}',
    geographies TEXT[] DEFAULT '{}',
    buyer_personas TEXT[] DEFAULT '{}',
    customer_segments TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}'::jsonb,
    content_hash TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        ALTER TABLE retrieval_documents
            ADD COLUMN IF NOT EXISTS embedding VECTOR(1536),
            ADD COLUMN IF NOT EXISTS embedding_model TEXT;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_retrieval_docs_entity
ON retrieval_documents(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_retrieval_docs_investor
ON retrieval_documents(investor_id);

CREATE INDEX IF NOT EXISTS idx_retrieval_docs_type
ON retrieval_documents(document_type);

CREATE INDEX IF NOT EXISTS idx_retrieval_docs_keywords
ON retrieval_documents USING GIN(keywords);

CREATE INDEX IF NOT EXISTS idx_retrieval_docs_sectors
ON retrieval_documents USING GIN(sectors);

CREATE INDEX IF NOT EXISTS idx_retrieval_docs_buyer_personas
ON retrieval_documents USING GIN(buyer_personas);

CREATE INDEX IF NOT EXISTS idx_retrieval_docs_customer_segments
ON retrieval_documents USING GIN(customer_segments);

CREATE INDEX IF NOT EXISTS idx_retrieval_docs_content_fts
ON retrieval_documents USING GIN(to_tsvector('english', content));

CREATE UNIQUE INDEX IF NOT EXISTS idx_retrieval_docs_unique_hash
ON retrieval_documents(entity_type, entity_id, document_type, content_hash);

CREATE TABLE IF NOT EXISTS entity_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    source_id UUID NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    weight NUMERIC DEFAULT 1.0,
    evidence TEXT,
    evidence_url TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entity_edges_source
ON entity_edges(source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_entity_edges_target
ON entity_edges(target_type, target_id);

CREATE INDEX IF NOT EXISTS idx_entity_edges_type
ON entity_edges(edge_type);

CREATE TABLE IF NOT EXISTS portfolio_company_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    overview TEXT,
    market_category TEXT,
    business_model TEXT,
    sectors TEXT[] DEFAULT '{}',
    customer_segments TEXT[] DEFAULT '{}',
    buyer_personas TEXT[] DEFAULT '{}',
    supplier_categories TEXT[] DEFAULT '{}',
    products TEXT[] DEFAULT '{}',
    pain_points TEXT[] DEFAULT '{}',
    competitors TEXT[] DEFAULT '{}',
    complements TEXT[] DEFAULT '{}',
    integration_points TEXT[] DEFAULT '{}',
    market_signals JSONB DEFAULT '{}'::jsonb,
    evidence_urls TEXT[] DEFAULT '{}',
    confidence_score NUMERIC DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (company_id)
);

CREATE INDEX IF NOT EXISTS idx_portco_analyses_company_id
ON portfolio_company_analyses(company_id);

CREATE INDEX IF NOT EXISTS idx_portco_analyses_sectors
ON portfolio_company_analyses USING GIN(sectors);

CREATE INDEX IF NOT EXISTS idx_portco_analyses_buyer_personas
ON portfolio_company_analyses USING GIN(buyer_personas);

CREATE INDEX IF NOT EXISTS idx_portco_analyses_customer_segments
ON portfolio_company_analyses USING GIN(customer_segments);
