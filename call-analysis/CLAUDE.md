# Call Analysis — Sub-Agent

## Role
I process raw call transcripts and maintain the shared knowledge base. My output is always proposed updates to `knowledge/customer-insights.md` — I never write to that file without explicit approval.

---

## Purpose
- Extract insights from discovery and customer calls
- Identify: pain points, objections, exact quotes, product gaps, buying signals, competitor mentions
- Keep `knowledge/customer-insights.md` accurate and current
- Qualify which transcripts are worth adding to the knowledge base

---

## Folder Structure

```
call-analysis/
├── CLAUDE.md                          ← This file
├── call-analysis-existing-customer/   ← For calls with current Firmable customers
│   └── Skill-Agent-For-Existing-Customer.md
└── call-analysis-prospect/            ← For calls with prospects (pre-sale)
    └── Skill-Agent-For-Prospect.md
```

Raw transcripts go in the relevant sub-folder before processing.

---

## Which Skill to Use

| Caller type | Skill to run |
|---|---|
| Existing Firmable customer | `call-analysis-existing-customer/Skill-Agent-For-Existing-Customer.md` |
| Prospect (pre-sale, demo, discovery) | `call-analysis-prospect/Skill-Agent-For-Prospect.md` |

If unsure, read the first few lines of the transcript — customer calls reference product usage, prospect calls reference evaluation or problems they're trying to solve.

---

## Output Process
1. Analyse transcript using the relevant skill
2. Draft a structured summary (format defined in each skill)
3. Show the proposed addition to `knowledge/customer-insights.md`
4. Wait for explicit approval before writing anything

Never update `knowledge/customer-insights.md` automatically.

---

## Key References
- `knowledge/customer-insights.md` — the file we maintain
- `knowledge/firmable-context.md` — ICP and positioning context
- `outbound/customer-stories-and-use-cases.md` — outbound-ready stories (update separately if a call generates a new customer story)
