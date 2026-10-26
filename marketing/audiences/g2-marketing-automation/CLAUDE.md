# G2 Marketing Automation Audience — Sub-Agent

## Purpose
Build a company audience for the marketing team from every product listed in G2's Marketing Automation category (~734 products), with vendor domains for ad audience matching and Firmable enrichment.

## What goes in
- No input file. Data is scraped from https://www.g2.com/categories/marketing-automation via the Apify actor `omkar-cloud/g2-product-scraper`, run through Deepline (`apify_run_actor`)

## What goes out
- `output/g2_marketing_automation.csv` — one row per G2 product: g2_rank, product_name, vendor_name, domain, company_website, company_linkedin, hq_location, founded_year, rating, reviews_count, starting_price, has_free_trial, solution_type, top_pro, top_con, description, g2_link
- `output/` is gitignored

## Scripts / tools
- `scripts/build_audience.py` — pages through the Apify dataset via the Deepline CLI, merges listing + profile rows on slug, writes the CSV

## How to run

1. Start the scrape (reviews and website contacts off to keep cost down):
```bash
.deepline/runtime/node_modules/.bin/deepline tools execute apify_run_actor --input '{
  "actorId": "omkar-cloud/g2-product-scraper",
  "input": {"categories": ["marketing-automation"], "categorySort": "popularity",
            "maxProductsPerListing": 800, "expandListings": true,
            "scrapeReviews": false, "scrapeProductDetails": true, "websiteContacts": "off"},
  "params": {"maxItems": 1600, "timeout": 7200}}' --json
```
2. Poll with `apify_get_actor_run --input '{"runId":"<runId>"}'` until `SUCCEEDED`
3. Build the CSV:
```bash
PYTHONPATH=. python3 marketing/audiences/g2-marketing-automation/scripts/build_audience.py --dataset-id <datasetId>
```

## Conventions
- `scrapeReviews` defaults to true in the actor; always set it to false unless reviews are wanted (roughly 10x the cost)
- Cost (Oct 2026): ~$0.0005 per dataset row on Apify, ~1.5x Deepline markup, ~10 credits per $1. Two rows per product (listing + profile). Full Marketing Automation run (734 products, 1,468 rows) cost 10.28 credits and took ~1.5 hours, mostly profile scraping
- `domain` is the vendor's company website, so acquired products map to the parent (e.g. Selligent → zetaglobal.com); `hq_location` is "N/A" for ~24% of products
- Rows are per product, not per vendor; one vendor can have several products (e.g. Salesforce). Dedupe on `domain` for a company-level audience
- To reuse for another G2 category, change `categories` in the actor input and the output filename
