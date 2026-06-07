CREATE TABLE IF NOT EXISTS us_founding_100 (
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

  -- Enrichment (written by Trigger.dev tasks via master_companies, or pre-filled from cache)
  description             text,
  website_summary         text,
  company_type            text,
  company_type_reasoning  text,
  target_persona          text,
  persona_reasoning       text,

  -- Pipeline metadata
  status                  text not null default 'pending',
  error_msg               text,
  id                      uuid primary key default gen_random_uuid(),
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),

  CONSTRAINT us_founding_100_domain_unique UNIQUE (domain),
  CONSTRAINT us_founding_100_status_check CHECK (status IN ('pending', 'processing', 'done', 'error'))
);

CREATE INDEX IF NOT EXISTS us_founding_100_status_idx ON us_founding_100 (status);

CREATE OR REPLACE TRIGGER us_founding_100_updated_at
  BEFORE UPDATE ON us_founding_100
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

GRANT SELECT, INSERT, UPDATE ON public.us_founding_100 TO service_role;
