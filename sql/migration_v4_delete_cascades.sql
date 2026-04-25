-- Migration v4: add FK cascades so deleting an investor cleans up all child rows

ALTER TABLE vc_members
    ADD CONSTRAINT fk_vc_members_investor
    FOREIGN KEY (vc_id) REFERENCES investors(external_vc_id) ON DELETE CASCADE;

ALTER TABLE vc_funds
    ADD CONSTRAINT fk_vc_funds_investor
    FOREIGN KEY (vc_id) REFERENCES investors(external_vc_id) ON DELETE CASCADE;

ALTER TABLE portfolio_companies
    ADD CONSTRAINT fk_portfolio_companies_investor
    FOREIGN KEY (vc_id) REFERENCES investors(external_vc_id) ON DELETE CASCADE;

ALTER TABLE vc_enrichments
    ADD CONSTRAINT fk_vc_enrichments_investor
    FOREIGN KEY (vc_id) REFERENCES investors(external_vc_id) ON DELETE CASCADE;
