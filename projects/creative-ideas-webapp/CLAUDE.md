# Creative Ideas Web App — Sub-Agent

## Purpose

A public-facing Vercel web app that lets anyone (with the password) enter a company domain and region and instantly see 3 personalised ideas for how Firmable can help that company. The ideas are generated using the same slot framework as the ANZ and SEA creative ideas campaign skills.

## What goes in

- Company domain (e.g. `atlassian.com`)
- Region: ANZ or SEA

## What goes out

- Classified vertical and ICP target
- Bridge line + 2-3 ideas rendered as cards in the browser

## Files

| File | Role |
|---|---|
| `index.html` | Single-page frontend: password gate, form, results display |
| `api/generate.js` | Vercel Edge Function: Firmable lookup + OS sales team size + Claude ideas generation |
| `vercel.json` | Edge runtime config for the API function |
| `package.json` | Minimal — no dependencies (native fetch used in Edge Runtime) |
| `.env.example` | Template for required environment variables |

## API Function Logic

1. Validate password against `APP_PASSWORD`
2. Clean domain (strip protocol, www, path)
3. Call Firmable `/company?fqdn={domain}` to get company data
4. Call Firmable OS Search API to get regional sales team size (non-critical — continues without it)
5. Scan tech stack for competitor tools (ZoomInfo, Apollo, Lusha, etc.)
6. Call Claude Haiku with full ANZ or SEA slot framework prompt
7. Return `{ company_name, vertical, icp_target, bridge_line, ideas[] }`

## Environment Variables (set in Vercel dashboard)

```
FIRMABLE_API_KEY       — main Firmable API key
FIRMABLE_OS_API_KEY    — OS Search API key (for sales team size)
ANTHROPIC_API_KEY      — Anthropic API key
APP_PASSWORD           — password shown to users when sharing the URL
```

## Deployment

1. Push this folder to GitHub (or use this repo)
2. On vercel.com: Import Project → set root directory to `projects/creative-ideas-webapp/`
3. Set all 4 env vars in the Vercel dashboard
4. Deploy → get a live URL like `firmable-ideas.vercel.app`
5. Optional: add custom domain `ideas.firmable.com` via Vercel → Settings → Domains

Share the Vercel URL + `APP_PASSWORD` with team members. No login, no accounts needed.

## Local Testing

1. Copy `.env.example` to `.env` and fill in values
2. Install Vercel CLI: `npm i -g vercel`
3. Run `vercel dev` from this directory
4. Open `http://localhost:3000`

## Conventions

- Never modify the system prompts in `api/generate.js` without checking both SKILL.md files first.
- The SEA prompt has no Slot A (AU registers). ANZ has all 6 slots. Keep them separate.
- Formatting rules (no em dashes, no bold) are embedded in both system prompts — they mirror the SKILL.md formatting rules.
