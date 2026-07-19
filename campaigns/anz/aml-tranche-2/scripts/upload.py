"""
AML Tranche 2 — Upload CSV to Supabase
---------------------------------------
Upserts all rows from input/ into the aml_companies table.

Before running, create the table in Supabase SQL Editor:
  campaigns/anz/aml-tranche-2/supabase/migrations/001_create_aml_companies.sql

Usage:
  PYTHONPATH=. python3 campaigns/anz/aml-tranche-2/scripts/upload.py
"""

import os
import re
import glob
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL     = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
INPUT_DIR        = "campaigns/anz/aml-tranche-2/input"


def norm_domain(raw: str) -> str:
    d = re.sub(r"^https?://", "", str(raw).strip().lower())
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0].rstrip(".")


def extract_firmable_id(url: str) -> str:
    parts = str(url).rstrip("/").split("/")
    return parts[-1] if parts else ""


def upload_csv():
    sb = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

    # Auto-detect most recently modified CSV in input/
    files = sorted(glob.glob(f"{INPUT_DIR}/*.csv"), key=os.path.getmtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No CSV found in {INPUT_DIR}/")
    path = files[0]
    print(f"Reading: {path}")

    df = pd.read_csv(path, dtype=str).fillna("")
    print(f"Rows in file: {len(df)}")

    rows = []
    skipped = 0
    for _, r in df.iterrows():
        domain = norm_domain(r.get("Website", r.get("Domain name", "")))
        if not domain:
            skipped += 1
            continue
        rows.append({
            "domain":                domain,
            "company_name":          r.get("Company name", ""),
            "firmable_id":           extract_firmable_id(r.get("Firmable company link", "")),
            "country":               r.get("HQ - country", ""),
            "addresses":             r.get("Addresses", ""),
            "employee_count_au":     r.get("Employee count (AU)", ""),
            "employee_count_global": r.get("Employee count (Global)", ""),
            "target_customer_type":  r.get("Target customer type", ""),
            "anzsic":                r.get("ANZSIC", ""),
            "description":           r.get("Description", ""),
            "linkedin_url":          r.get("LinkedIn", ""),
            "services":              r.get("Services", ""),
            "tech_software_dev":     r.get("Technographics - software developme", ""),
            "tech_finance":          r.get("Technographics - finance & accounti", ""),
            "tech_hosting":          r.get("Technographics - hosting & operatio", ""),
            "tech_content":          r.get("Technographics - content & media", ""),
            "tech_sales_marketing":  r.get("Technographics - sales & marketing", ""),
            "tech_customer_mgmt":    r.get("Technographics - customer managemen", ""),
            "tech_analytics":        r.get("Technographics - analytics", ""),
            "tech_hr":               r.get("Technographics - HR & payroll", ""),
            "tech_other":            r.get("Technographics - other", ""),
            "status":                "pending",
        })

    if skipped:
        print(f"Skipped {skipped} rows with no domain.")

    # Deduplicate by domain (keep last occurrence)
    seen = {}
    for row in rows:
        seen[row["domain"]] = row
    rows = list(seen.values())
    print(f"Unique domains: {len(rows)}")

    # Upsert in batches of 500
    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        sb.table("aml_companies").upsert(batch, on_conflict="domain").execute()
        print(f"  Upserted rows {i + 1}–{i + len(batch)}")

    print(f"\nDone. {len(rows)} rows uploaded to aml_companies.")


if __name__ == "__main__":
    upload_csv()
