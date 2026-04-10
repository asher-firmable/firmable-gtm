# SEA Company Upload Check

Run this before uploading any company list to SmartLead. It checks each domain against HubSpot and reports:
1. How many companies already exist in HubSpot vs. don't
2. For those in HubSpot — how many are ruled out (outreach status = "No product fit" or "Time Out") vs. viable

## Steps

1. Remind the user:
   > Drop your company CSV into `projects/sea-company-upload/input/` before continuing.
   > The file needs at least one domain column: `domain`, `website`, `company_website`, or `company_domain`.
   > Let me know when it's in there.

   Wait for the user to confirm. Do not run anything yet.

2. Once the user confirms, run the check:
   ```
   PYTHONPATH=. python3 scripts/check_company_hubspot_status.py
   ```
   The script auto-detects the latest CSV in `projects/sea-company-upload/input/`. To use a different file:
   ```
   PYTHONPATH=. python3 scripts/check_company_hubspot_status.py --input path/to/companies.csv
   ```

3. After the script prints its summary, ask:
   "Based on these numbers, do you want to proceed to upload, filter the list further, or investigate any specific companies?"

## Notes
- The script auto-detects the domain and company name columns — no need to rename columns first.
- Domains are cleaned automatically (strips `https://`, `www.`, path segments).
- Rate limiting: the script sleeps 0.1s between HubSpot calls. Expect ~1–2 seconds per company.
- Script: `scripts/check_company_hubspot_status.py`
- Project folder: `projects/sea-company-upload/`
