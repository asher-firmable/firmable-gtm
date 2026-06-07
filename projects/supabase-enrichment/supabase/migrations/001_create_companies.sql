CREATE TABLE IF NOT EXISTS master_companies (
  company_name            text,
  country                 text,
  industry                text,
  technographics          text,
  firmable_id             text,
  domain                  text not null,
  linkedin_url            text,
  list_segment            text,

  -- Competitive intelligence (company-level flags from source CSV)
  zoominfo                boolean,
  apollo                  boolean,
  six_sense               boolean,
  cognism                 boolean,
  hubspot                 boolean,
  salesforce              boolean,

  -- Enrichment
  description             text,       -- fetched from Firmable API
  website_summary         text,       -- Firecrawl fallback (only if description unclear)
  company_type            text,       -- 'SaaS/Software providers' | 'MSPs' | 'IT services firms' | 'IT Solutions providers' | 'Other B2B companies'
  company_type_reasoning  text,
  target_persona          text,       -- e.g. 'CFOs or operations managers'
  persona_reasoning       text,

  -- Pipeline metadata
  status                  text not null default 'pending',  -- pending | processing | done | error
  error_msg               text,
  id                      uuid primary key default gen_random_uuid(),
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),

  CONSTRAINT master_companies_domain_unique UNIQUE (domain),
  CONSTRAINT master_companies_status_check CHECK (status IN ('pending', 'processing', 'done', 'error'))
);

CREATE INDEX IF NOT EXISTS master_companies_status_idx ON master_companies (status);

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER master_companies_updated_at
  BEFORE UPDATE ON master_companies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

GRANT SELECT, INSERT, UPDATE ON public.master_companies TO service_role;
