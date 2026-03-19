# Skill: Event Scraping Bot (Staging)

## What This Is
Staging version of the Event-Scraping-Skill. Same logical steps as production, but may diverge for experimentation.

Refer to `event-scraping-bot/Event-Scraping-Skill.md` as the production reference.

---

## How to Run (Staging)

### Scrape
```bash
PYTHONPATH=. python3 staging/event-scraping-bot-staging/scripts/Scrape.py \
  --url "TEST_EVENT_URL" \
  --output "staging/event-scraping-bot-staging/output/test_raw.csv" \
  --skip-linkedin-resolve \
  --skip-firmable
```

### Enrich
```bash
PYTHONPATH=. python3 staging/event-scraping-bot-staging/scripts/Enrich-Company.py \
  --input "staging/event-scraping-bot-staging/output/test_raw.csv" \
  --output "staging/event-scraping-bot-staging/output/test_enriched.csv"
```

---

## Notes on Divergence
Document any intentional differences from production here:
- [e.g. "Testing a new Playwright-based scroll strategy"]
- [e.g. "Trying a higher Vision threshold (8 vs 5)"]

---

## Promoting to Production
When the staging version is validated:
1. Run `staging/Replicate-to-prod-skill.md`
2. Review the diff
3. Approve the copy to production
