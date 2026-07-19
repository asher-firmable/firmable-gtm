"""
AML Tranche 2 — Trigger & Monitor
-----------------------------------
Invokes the Supabase edge functions (non-blocking) and polls status.

Usage:
  # Trigger Phase 1 (description check) — returns immediately, runs in background
  PYTHONPATH=. python3 campaigns/anz/aml-tranche-2/scripts/trigger.py --phase 1

  # Trigger Phase 2 (website check, for pending_web rows)
  PYTHONPATH=. python3 campaigns/anz/aml-tranche-2/scripts/trigger.py --phase 2

  # Monitor progress
  PYTHONPATH=. python3 campaigns/anz/aml-tranche-2/scripts/trigger.py --monitor

  # Export results to CSV
  PYTHONPATH=. python3 campaigns/anz/aml-tranche-2/scripts/trigger.py --export
"""

import argparse
import os
import time
import sys
from datetime import datetime

import requests
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL     = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OUTPUT_DIR       = "campaigns/anz/aml-tranche-2/output"


def get_supabase():
    return create_client(SUPABASE_URL, SERVICE_ROLE_KEY)


def trigger_function(name: str) -> None:
    url = f"{SUPABASE_URL}/functions/v1/{name}"
    r = requests.post(url, headers={"Authorization": f"Bearer {SERVICE_ROLE_KEY}"})
    if r.status_code == 202:
        print(f"[{name}] started — running in background (202)")
    else:
        print(f"[{name}] unexpected response {r.status_code}: {r.text}")
        sys.exit(1)


def print_status() -> dict:
    sb = get_supabase()
    result = sb.table("aml_companies").select("status").execute()
    rows = result.data or []

    counts = {}
    for row in rows:
        s = row["status"]
        counts[s] = counts.get(s, 0) + 1

    total = len(rows)
    done  = counts.get("done", 0)
    pct   = round(done / total * 100, 1) if total else 0

    print(f"\n{'─'*40}")
    print(f"  Total:         {total}")
    for status in ["pending", "processing", "pending_web", "done", "error"]:
        n = counts.get(status, 0)
        if n:
            print(f"  {status:<14} {n}")
    print(f"  Progress:      {done}/{total}  ({pct}%)")
    print(f"{'─'*40}\n")
    return counts


def monitor(interval: int = 15) -> None:
    print("Monitoring… (Ctrl+C to stop)")
    try:
        while True:
            counts = print_status()
            pending   = counts.get("pending", 0)
            processing = counts.get("processing", 0)
            pending_web = counts.get("pending_web", 0)
            if pending == 0 and processing == 0 and pending_web == 0:
                print("All rows processed.")
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")


def export_results() -> None:
    import csv

    sb = get_supabase()
    result = sb.table("aml_companies").select(
        "domain,company_name,firmable_id,description,"
        "aml_result,aml_reason,needs_web_check,"
        "web_result,web_reason,status"
    ).execute()

    rows = result.data or []
    if not rows:
        print("No rows to export.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{OUTPUT_DIR}/aml_results_{ts}.csv"

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    true_count = sum(
        1 for r in rows
        if r.get("aml_result") is True or r.get("web_result") is True
    )
    print(f"Exported {total} rows → {path}")
    print(f"  Qualified (result=true):  {true_count}")
    print(f"  Not qualified:            {total - true_count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase",   type=int, choices=[1, 2])
    parser.add_argument("--monitor", action="store_true")
    parser.add_argument("--export",  action="store_true")
    parser.add_argument("--interval", type=int, default=15,
                        help="Monitor poll interval in seconds (default: 15)")
    args = parser.parse_args()

    if args.phase == 1:
        trigger_function("check-description")
    elif args.phase == 2:
        trigger_function("check-website")
    elif args.monitor:
        monitor(interval=args.interval)
    elif args.export:
        export_results()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
