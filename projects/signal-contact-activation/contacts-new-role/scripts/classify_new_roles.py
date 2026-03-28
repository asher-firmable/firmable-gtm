"""
Signal — Contact Activation: New Role Classifier
-------------------------------------------------
Reads a Firmable-exported contacts CSV (people who started new roles in the past 90 days),
classifies each contact against Firmable's ICP definition, and writes a scored output CSV.

Key mapping: the `Headline` column (LinkedIn headline) is passed as `summary` to the
classifier so the BDM ambiguity rule and seniority checks can use it to validate whether
a contact is genuinely at a managerial level — not just a titled IC.

Usage:
  PYTHONPATH=. python3 projects/signal-contact-activation/scripts/classify_new_roles.py \\
    --input "data/input/20260325_ex_customer_contacts_new_role.csv"
"""

import argparse
import os

from scripts.classifier import classify_contacts
from scripts.utils import load_csv, save_csv, timestamp

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
)


def _build_classifier_input(row) -> dict:
    """Map a normalised CSV row to the fields the classifier expects."""
    contact = {}
    if row.get("first_name"):
        contact["first_name"] = str(row["first_name"]).strip()
    if row.get("last_name"):
        contact["last_name"] = str(row["last_name"]).strip()
    if row.get("position"):
        contact["title"] = str(row["position"]).strip()
    # LinkedIn headline → summary: the classifier's BDM ambiguity rule
    # checks this field for team leadership signals ("leading a team of X", etc.)
    if row.get("headline"):
        contact["summary"] = str(row["headline"]).strip()
    if row.get("company_name"):
        contact["company"] = str(row["company_name"]).strip()
    if row.get("company_website"):
        contact["website"] = str(row["company_website"]).strip()
    return contact


def classify(input_path: str, output_path: str, batch_size: int = 20) -> str:
    df = load_csv(input_path)
    total = len(df)
    print(f"Loaded {total} contacts from: {input_path}")

    rows = df.to_dict(orient="records")

    icp_matches = []
    icp_reasons = []
    confidences = []

    for batch_start in range(0, total, batch_size):
        batch = rows[batch_start : batch_start + batch_size]
        batch_end = min(batch_start + batch_size, total)
        print(f"  Classifying [{batch_start + 1}–{batch_end}/{total}]...")

        contacts = [_build_classifier_input(r) for r in batch]
        results = classify_contacts(contacts)

        for r in results:
            icp_matches.append(r.get("icp_match", "No"))
            icp_reasons.append(r.get("icp_reason", ""))
            confidences.append(r.get("confidence", "high"))

    df["icp_match"] = icp_matches
    df["icp_reason"] = icp_reasons
    df["confidence"] = confidences

    save_csv(df, output_path)

    yes_count = sum(1 for m in icp_matches if m == "Yes")
    no_count = total - yes_count
    low_conf = sum(1 for c in confidences if c == "low")
    print(f"\nDone. {total} contacts classified.")
    print(f"  ICP Yes: {yes_count}  |  ICP No: {no_count}  |  Low confidence: {low_conf}")
    print(f"  Output: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Classify new-role contacts against Firmable's ICP definition."
    )
    parser.add_argument(
        "--input", required=True, help="Path to input contacts CSV (Firmable export)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to output CSV (default: output/classified_<timestamp>.csv)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Contacts per API call (default: 20)",
    )
    args = parser.parse_args()

    output_path = args.output or os.path.join(OUTPUT_DIR, f"classified_{timestamp()}.csv")
    classify(args.input, output_path, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
