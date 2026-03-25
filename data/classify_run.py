import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.classifier import classify_contacts

INPUT = os.path.join(os.path.dirname(__file__), "input", "20260325_ex_customer_contacts_new_role.csv")
OUTPUT = os.path.join(os.path.dirname(__file__), "output", "20260325_ex_customer_contacts_new_role_classified.csv")


def main():
    with open(INPUT, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    contacts = []
    for row in rows:
        contacts.append({
            "first_name": row.get("First name", ""),
            "last_name": row.get("Last name", ""),
            "title": row.get("Position", ""),
            "company": row.get("Company name", ""),
            "summary": row.get("Headline", ""),
            "website": row.get("Company website", ""),
        })

    print(f"Classifying {len(contacts)} contacts...")
    results = classify_contacts(contacts)

    out_fieldnames = list(fieldnames) + ["ICP_Match", "ICP_Reason", "ICP_Confidence"]
    for row, result in zip(rows, results):
        row["ICP_Match"] = result.get("icp_match", "")
        row["ICP_Reason"] = result.get("icp_reason", "")
        row["ICP_Confidence"] = result.get("confidence", "")

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Output written to: {OUTPUT}")


if __name__ == "__main__":
    main()
