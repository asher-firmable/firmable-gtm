"""
Run all event outbound steps in sequence.

Usage:
    python workflows/event_outbound/run_all.py --project projects/event_outbound/gitex_asia_2026
    python workflows/event_outbound/run_all.py --project projects/event_outbound/gitex_asia_2026 --start-from 2
    python workflows/event_outbound/run_all.py --project projects/event_outbound/gitex_asia_2026 --dry-run
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run full event outbound pipeline")
    parser.add_argument("--project", required=True, help="Path to project folder")
    parser.add_argument("--start-from", type=int, default=0, choices=[0, 1, 2, 3, 4],
                        help="Start from a specific step (0=scrape, 1=enrich, 2=score, 3=personalise, 4=upload)")
    parser.add_argument("--dry-run", action="store_true", help="Pass --dry-run to upload step")
    args = parser.parse_args()

    project = args.project
    start = args.start_from

    steps = [
        ("Step 0: Scrape exhibitors",      f"PYTHONPATH=. python3 workflows/event_outbound/0_scrape_exhibitors.py --project {project}"),
        ("Step 1: Find contacts",          f"PYTHONPATH=. python3 workflows/event_outbound/1_find_contacts.py --project {project}"),
        # Steps 2–5 use the legacy --project convention and will be migrated as each is rebuilt
        ("Step 2: Score leads",            f"PYTHONPATH=. python3 workflows/event_outbound/2_score.py --project {project}"),
        ("Step 3: Personalise copy",       f"PYTHONPATH=. python3 workflows/event_outbound/3_personalise.py --project {project}"),
        ("Step 4: Upload to SmartLead",    f"PYTHONPATH=. python3 workflows/event_outbound/4_upload_to_smartlead.py --project {project}" + (" --dry-run" if args.dry_run else "")),
    ]

    for i, (label, cmd) in enumerate(steps):
        if i < start:
            print(f"[skipped] {label}")
            continue
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
        result = subprocess.run(cmd, shell=True)
        if result.returncode != 0:
            print(f"\n[ERROR] {label} failed. Stopping pipeline.")
            sys.exit(result.returncode)

    print("\n✓ All steps complete.")


if __name__ == "__main__":
    main()
