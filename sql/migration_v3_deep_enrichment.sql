-- Migration v3: support DeepEnrichedVC fields
-- revealed_thesis_json on investors; depth + branch_traces on vc_enrichments

ALTER TABLE investors
    ADD COLUMN IF NOT EXISTS revealed_thesis_json JSONB;

ALTER TABLE vc_enrichments
    ADD COLUMN IF NOT EXISTS depth TEXT,
    ADD COLUMN IF NOT EXISTS branch_traces JSONB;
