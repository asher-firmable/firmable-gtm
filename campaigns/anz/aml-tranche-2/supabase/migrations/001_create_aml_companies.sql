CREATE TABLE IF NOT EXISTS aml_companies (
  id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,

  -- Firmable input columns
  domain                text UNIQUE NOT NULL,
  company_name          text,
  firmable_id           text,
  country               text,
  addresses             text,
  employee_count_au     text,
  employee_count_global text,
  target_customer_type  text,
  anzsic                text,
  description           text,
  linkedin_url          text,
  services              text,
  tech_software_dev     text,
  tech_finance          text,
  tech_hosting          text,
  tech_content          text,
  tech_sales_marketing  text,
  tech_customer_mgmt    text,
  tech_analytics        text,
  tech_hr               text,
  tech_other            text,

  -- Phase 1 outputs
  aml_result      boolean,
  aml_reason      text,
  needs_web_check boolean,

  -- Phase 2 outputs
  web_result  boolean,
  web_reason  text,

  status    text DEFAULT 'pending'
            CHECK (status IN (
              'pending', 'processing', 'phase1_done',
              'pending_web', 'done', 'error'
            )),
  error_msg  text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
  BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at ON aml_companies;
CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON aml_companies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
