"""
List HubSpot Owners
-------------------
Prints a numbered list of all HubSpot users with their IDs.
Used by the sea-company-viable commands to let the user pick a Company Owner.

Usage:
  PYTHONPATH=. python3 projects/sea-company-upload/scripts/list_owners.py
"""

from scripts.hubspot_client import HubSpotClient

hs = HubSpotClient()
owners = hs.get_owners()

print(f"{'#':<4} {'Name':<30} {'Email':<40} {'ID'}")
print("-" * 85)
for i, o in enumerate(owners, 1):
    name = f"{o.get('firstName', '')} {o.get('lastName', '')}".strip() or "(no name)"
    email = o.get("email", "")
    oid = o["id"]
    print(f"{i:<4} {name:<30} {email:<40} {oid}")
