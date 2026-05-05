"""
End-to-end pipeline for HR Tech Festival Asia 2026:
  1. Scrape exhibitors → output/exhibitors.csv
  2. Copy to campaigns/quick-sales-team-size-check/input/
  3. Enrich with Firmable regional sales team sizes

Usage:
    PYTHONPATH=. python3 campaigns/sea-conferences/hr-tech-festival-asia-2026/run_pipeline.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE      = Path(__file__).parent
REPO_ROOT = HERE.parents[2]  # .../hr-tech-festival-asia-2026 → .../sea-conferences → .../campaigns → repo root

SCRAPER    = HERE / "scrape_exhibitors.py"
OUTPUT_CSV = HERE / "output" / "exhibitors.csv"

QUICK_CHECK_INPUT  = REPO_ROOT / "campaigns" / "quick-sales-team-size-check" / "input"
QUICK_CHECK_ENRICH = REPO_ROOT / "campaigns" / "quick-sales-team-size-check" / "scripts" / "enrich_sales_team_size.py"
INPUT_FILENAME     = "hr-tech-festival-asia-2026-exhibitors.csv"


def _step(label: str) -> None:
    print(f"\n{'=' * 60}")
    print(label)
    print("=" * 60)


def run() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}

    # Step 1: Scrape
    _step("Step 1/3: Scraping HR Tech Festival Asia 2026 exhibitors...")
    subprocess.run([sys.executable, str(SCRAPER)], check=True, env=env)

    if not OUTPUT_CSV.exists():
        print(f"[error] Scraper output not found: {OUTPUT_CSV}")
        sys.exit(1)

    # Step 2: Copy to quick-sales-team-size-check/input/
    _step("Step 2/3: Copying to quick-sales-team-size-check/input/...")
    QUICK_CHECK_INPUT.mkdir(parents=True, exist_ok=True)
    dest = QUICK_CHECK_INPUT / INPUT_FILENAME
    shutil.copy(OUTPUT_CSV, dest)
    print(f"Copied → {dest}")

    # Step 3: Enrich with Firmable sales team sizes
    _step("Step 3/3: Enriching with Firmable sales team sizes...")
    subprocess.run(
        [sys.executable, str(QUICK_CHECK_ENRICH), "--input", str(dest)],
        check=True,
        env=env,
    )

    enriched = QUICK_CHECK_INPUT.parent / "output" / f"{dest.stem}_enriched.csv"
    print(f"\nPipeline complete.")
    print(f"Enriched CSV: {enriched}")


if __name__ == "__main__":
    run()
