# Description Check

Given a company list with descriptions, evaluate each description against a yes/no question. Runs in two modes:
- **Review mode** (early batches): shows Yes/No + reasoning so you can validate the logic
- **Confirm mode** (after approval): shows Yes/No only — no reasoning, fewer tokens

## Steps

1. Ask the user:
   > What yes/no question do you want to check against the company descriptions?
   > (Example: "Is this company a recruitment or staffing agency?")

   Save their answer as `<question>`.

2. Ask the user:
   > Drop your file (CSV or Excel) into `campaigns/company-checks/description-check/input/` and let me know when it's there.
   > The file needs at least one description column: `description`, `company_description`, `about`, `overview`, or `summary`.

   Wait for confirmation. Do not run anything yet.

3. Ask the user:
   > What should I name the output file? (e.g. `staffing_check.csv`)

   Save their answer as `<output_filename>`. Append `.csv` if they didn't include it.

4. Run the first preview batch:
   ```
   PYTHONPATH=. python3 campaigns/company-checks/description-check/scripts/description_check.py --start 0 --count 10
   ```

5. **Review mode** — parse the JSON from stdout. For each row in `rows`:
   - If `description` is `null` → leave Result and Reason blank in the table and CSV
   - Otherwise → read the description and evaluate it against `<question>` using your own reasoning
   - Display as a markdown table: `| # | Company Name | Domain | Description | Result | Reason |` (include the full description text so the user can compare against the reasoning)
   - Track `current_start = 0 + count_of_rows_returned`

6. Ask:
   > Does the reasoning look right? Say **"confirmed"** and I'll switch to Yes/No only for the remaining rows. Or tell me how many more rows to check with full reasoning (e.g. "check next 20").

7. **If user requests more review rows** (e.g. "check next 20 with reasoning"):
   - Run: `PYTHONPATH=. python3 campaigns/company-checks/description-check/scripts/description_check.py --start <current_start> --count <N>`
   - Evaluate and show table with Yes/No + Reason
   - Update `current_start += N`
   - Ask if they want to save these results before continuing (if yes, save via write mode — see step 9)
   - Repeat step 6

8. **Once user says "confirmed"** — switch to confirm mode. Do not ask how many rows. Process all remaining rows automatically in batches of 300:
   - Run: `PYTHONPATH=. python3 campaigns/company-checks/description-check/scripts/description_check.py --start <current_start> --count 300`
   - **Do not reason about individual rows.** Classify each description directly — read it, decide YES or NO, move on. No internal deliberation.
   - **Do not output a table.** Build only the compact JSON array (see step 9 format) — no markdown, no reasoning text, no descriptions repeated back.
   - Save results immediately (step 9)
   - Print one progress line only: `Batch complete — <current_start + rows_returned>/<total> rows saved.`
   - Update `current_start += rows_returned`
   - If `current_start < total`, immediately run the next batch of 300 — no user prompt, no pause
   - If `current_start >= total`, go to step 10

9. **Saving results** — build a JSON array from the current batch results.

   **Review mode** (first batches with reasoning):
   ```json
   [
     {"row_num": 1, "company_name": "...", "domain": "...", "result": "Yes", "reason": "..."},
     {"row_num": 2, "company_name": "...", "domain": "...", "result": "", "reason": ""}
   ]
   ```

   **Confirm mode** (bulk batches — compact, no reasoning):
   ```json
   [
     {"row_num": 1, "company_name": "...", "domain": "...", "result": "Yes"},
     {"row_num": 2, "company_name": "...", "domain": "...", "result": "No"}
   ]
   ```
   - Copy `company_name` and `domain` directly from the extracted batch input — do not re-state from memory
   - Do not include `description` in the output JSON — it is already in the input file
   - Blank descriptions → `"result": ""`
   - In confirm mode: omit `reason` entirely — do not set it to an empty string

   First save (no existing output file):
   ```
   PYTHONPATH=. python3 campaigns/company-checks/description-check/scripts/description_check.py --mode write --output <output_filename> --results-json '<json_array>'
   ```

   Subsequent saves (append):
   ```
   PYTHONPATH=. python3 campaigns/company-checks/description-check/scripts/description_check.py --mode write --output <output_filename> --results-json '<json_array>' --append
   ```

10. When all rows are processed:
    > All rows processed. Results saved to `campaigns/company-checks/description-check/output/<output_filename>`.

## Notes
- The script auto-detects the most recently modified file in `input/` when `--input` is omitted.
- Column detection is case-insensitive — no column renaming needed.
- `--count 9999` safely processes to end-of-file; pandas truncates gracefully.
- Output is gitignored — results are never committed.
- Always use `--append` after the first write to avoid overwriting previous batches.
- The `total` field in the JSON output tells you the full row count of the file.

## Token efficiency rules (always apply — do not override)
- **Confirm mode is no-reasoning mode.** Never explain why a description is YES or NO during bulk processing. The review phase already validated the logic.
- **No description echo.** Never repeat description text back in the output JSON or in any table — it is already in the input file.
- **No tables in confirm mode.** Tables are only for review mode (first 10 rows). After confirmation, the only output per batch is the compact JSON array + one progress line.
- **Batch size is fixed at 300.** Do not ask the user how many rows to process next after confirmation is given.
