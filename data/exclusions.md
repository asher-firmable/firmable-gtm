# Outreach Exclusion Rules

Applied before any scoring or campaign routing. If a contact matches any rule below, they are excluded from all outreach.

---

## Rule 1: DNC Register

**Field:** HubSpot contact property — `On DNC Register`
**Values:** `Yes` / `No`

**Rule:** If `On DNC Register = Yes`, exclude from all outreach — email and phone.

**How to apply in scripts:**
```python
# Before adding any contact to a SmartLead campaign or HubSpot sequence
if contact.get("on_dnc_register", "").strip().lower() == "yes":
    logger.info(f"Skipping {contact['email']} — DNC Register flag set.")
    continue
```

**Notes:**
- This is a legal requirement in Australia. Do not skip this check.
- The Firmable platform scrubs against the DNC Register live at the API level, but the flag should also be stored in HubSpot and checked here at the script level as a safeguard.
- If the field is missing or blank, treat as `No` (eligible to contact) — but log a warning.

---

## Future Rules (add here as needed)

- **Existing customers** — exclude contacts associated with HubSpot companies that have a closed-won deal
- **Unsubscribes** — contacts with `Email Unsubscribed = True` in HubSpot
- **Competitors** — exclude contacts at companies identified as direct competitors (e.g. ZoomInfo, Apollo, Lusha, Cognism — as organisations, not as signals)
- **Specific domain blocklist** — a list of domains to never contact (investors, press, etc.)
