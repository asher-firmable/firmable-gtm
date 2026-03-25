# Skill: Account-Based Outbound Pipeline

Run this skill when given a list of accounts (Excel/CSV with Firmable IDs) to turn into a live SmartLead outbound campaign.

---

## Prerequisites

1. **Input file** ready in `data/input/` with columns:
   - `account_name` — company name
   - `firmable_company_id` — Firmable ID
   (Any additional columns are preserved but not used by the pipeline)

2. **`config.json` filled in** at `outbound/account-pipeline/config.json`:
   - Set `from_name`, `from_email`, `reply_to` to your sending details

3. **`.env` has all required keys:**
   - `FIRMABLE_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `SMARTLEAD_API_KEY`

---

## Step-by-Step Execution

### 1. Run the full pipeline
```bash
PYTHONPATH=. python3 outbound/account-pipeline/scripts/run_all.py --input data/input/YOUR_FILE.xlsx
```

### 2. (Recommended) Run with --skip-upload to review emails first
```bash
PYTHONPATH=. python3 outbound/account-pipeline/scripts/run_all.py \
  --input data/input/YOUR_FILE.xlsx \
  --skip-upload
```
Review `outbound/account-pipeline/output/emails.csv` — check that subject lines and bodies look right before uploading.

### 3. Upload when satisfied
```bash
PYTHONPATH=. python3 outbound/account-pipeline/scripts/4_upload.py
```

Or dry-run first:
```bash
PYTHONPATH=. python3 outbound/account-pipeline/scripts/4_upload.py --dry-run
```

---

## What Each Step Does

| Step | Output File | What to Check |
|---|---|---|
| 0 — Filter | `filtered_accounts.csv`, `excluded_accounts.csv` | Review excluded accounts; re-add any wrongly removed |
| 1 — Find Contacts | `contacts.csv` | Check contact count per company; expect 1–5 per account |
| 2 — Research | `contacts_researched.csv` | Spot-check `target_market` and `target_titles` for 3–5 companies |
| 3 — Generate Emails | `emails.csv` | Read 5 emails to verify tone, persona-fit, and personalization quality |
| 4 — Upload | `upload_results.csv` | Check that all rows show `status: uploaded` |

---

## Troubleshooting

**SmartLead 403 on campaign creation:**
Create the campaign manually in SmartLead, then re-run upload with:
```bash
PYTHONPATH=. python3 outbound/account-pipeline/scripts/4_upload.py --campaign-id <id>
```
Note: the 2-step sequence still needs to be set up manually in SmartLead with `{{email_body_1}}` and `{{email_body_2}}` as the body templates for steps 1 and 2.

**No contacts found for a company:**
Firmable may not have contacts at that company. The script logs `[INFO] No qualifying contacts found` and moves on.

**Email quality is off:**
Edit the prompt in `3_generate_emails.py` → `generate_emails()` function. Adjust tone rules or proof points.

---

## Re-running a Step

Each script reads from the previous step's output CSV. To re-run from step 2 onwards without re-running the full pipeline:
```bash
PYTHONPATH=. python3 outbound/account-pipeline/scripts/2_research.py
PYTHONPATH=. python3 outbound/account-pipeline/scripts/3_generate_emails.py
PYTHONPATH=. python3 outbound/account-pipeline/scripts/4_upload.py
```
