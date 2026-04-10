"""
List Outreach Engagement Status Options
----------------------------------------
Prints a numbered list of all valid options for the outreach_engagement_status
property in HubSpot. Used by the sea-company-viable commands.

Usage:
  PYTHONPATH=. python3 projects/sea-company-upload/scripts/list_status_options.py
"""

from scripts.hubspot_client import HubSpotClient

hs = HubSpotClient()
options = hs.get_property_options("companies", "outreach_engagement_status")

print(f"{'#':<4} {'Label':<35} {'Value (use this in --status)'}")
print("-" * 75)
for i, opt in enumerate(options, 1):
    print(f"{i:<4} {opt['label']:<35} {opt['value']}")
