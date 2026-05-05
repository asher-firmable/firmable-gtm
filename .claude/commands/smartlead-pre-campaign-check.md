# SmartLead Pre-Campaign Check

Run this before uploading any company list to SmartLead. It checks each domain against HubSpot and filters out:
1. Companies on an active trial or paying customers
2. Companies with an outreach engagement status other than "Pool" or "Time Out"
3. Companies contacted in the last 30 days
4. Companies with active scheduled tasks
5. Companies with any open (non-closed) deal

Output is a clean CSV of eligible companies only: company name, domain, Firmable link, and Firmable ID.

## Steps

1. Ask the user:
   > What would you like to name the output file? (e.g. `eligible_acme_campaign.csv`)

   Wait for their answer. Save it as `<output_filename>`.

2. Remind the user:
   > Drop your company CSV into `campaigns/company-checks/input/` before continuing.
   > The file needs at least one domain column: `domain`, `website`, `company_website`, or `company_domain`.
   > Let me know when it's in there.

   Wait for the user to confirm. Do not run anything yet.

3. Once the user confirms, run the check:
   ```
   PYTHONPATH=. python3 scripts/smartlead_pre_campaign_check.py --output <output_filename>
   ```
   To use an explicit input file instead of auto-detection:
   ```
   PYTHONPATH=. python3 scripts/smartlead_pre_campaign_check.py --input path/to/companies.csv --output <output_filename>
   ```

4. After the script prints its summary, report the eligible count and ask:
   > Based on these numbers, do you want to proceed to SmartLead upload, review any filtered companies, or investigate specific entries?

## Notes
- Domain columns auto-detected (case-insensitive).
- Domains are cleaned automatically (strips `https://`, `www.`, path segments) and reduced to root domain before HubSpot lookup (e.g. `shopify.com.au` → searches as `shopify.com`).
- Companies not found in HubSpot are treated as eligible.
- Firmable company link is preserved in output; the ID is extracted as a separate column.
- Output is written to `campaigns/company-checks/output/<output_filename>`.
- Rate limiting: ~0.2s per company. Expect 1–2 seconds per company for those in HubSpot.
- Script: `scripts/smartlead_pre_campaign_check.py`
- Input/output folder: `campaigns/company-checks/`
