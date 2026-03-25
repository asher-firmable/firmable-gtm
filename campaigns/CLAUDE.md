# Campaigns — Data Store

Campaign data organised by region. This folder contains data only — all scripts live in `projects/`.

## Regions

| Folder | Market |
|---|---|
| `anz/` | Australia & New Zealand |
| `us/` | United States |
| `sea/` | South-East Asia |

## Campaign Folder Convention

Each campaign gets its own subfolder inside the relevant region:

```
campaigns/
└── anz/
    └── 2026-q2-fintech-sydney/
        ├── brief.md              ← Campaign goal, ICP, target accounts, sender details
        └── data/
            ├── raw/              ← Original input files from Clay or manual upload
            ├── qualified/        ← After ICP scoring (icp_score, tier added)
            ├── validated/        ← After contact validation (DNC applied)
            └── final/            ← Ready for SmartLead upload
```

## Rules

- **Data only** — no scripts live here; run scripts from `projects/outbound/` or `projects/event-scraper/`
- **brief.md required** — every campaign folder must have a brief describing the goal, ICP, and sender
- **gitignore** — all `data/` subfolders are gitignored; only `brief.md` and `.gitkeep` files are committed
- **Naming** — use `YYYY-[q or month]-[descriptor]-[region]` format (e.g. `2026-q2-fintech-sydney`)

## Creating a New Campaign

Run `/new-campaign` and follow the wizard. It will create the folder structure and populate `brief.md`.
