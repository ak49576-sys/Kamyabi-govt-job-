"""Offline smart-publishing decision report. Never calls Kamyabi or publishes.

Input JSON:
{
  "candidates": [...],
  "existing_records": [...],
  "evidence_by_job_id": {"job-id": {...}},
  "inventory_complete": false
}

The inventory_complete flag is an assertion made by an upstream authenticated
admin export, not a fact this script can independently verify. Until such an
export and a trusted official-notice parser exist, keep this flag false.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from smart_publish_gate import assess_batch


def build_report(document, today=None):
    if not isinstance(document, dict):
        raise ValueError("Expected an object")
    candidates = document.get("candidates")
    inventory = document.get("existing_records")
    evidence = document.get("evidence_by_job_id")
    if not isinstance(candidates, list) or not isinstance(inventory, list) or not isinstance(evidence, dict):
        raise ValueError("candidates, existing_records, and evidence_by_job_id are required")
    if not all(isinstance(row, dict) and isinstance(row.get("job_id"), str) for row in candidates):
        raise ValueError("Every candidate needs job_id")
    if len(candidates) > 500:
        raise ValueError("Maximum 500 candidates per preview")
    complete = document.get("inventory_complete") is True
    results = assess_batch(candidates, inventory, evidence, today, inventory_complete=complete)
    counts = {name: sum(item["decision"] == name for item in results)
              for name in ("eligible_for_dry_run", "duplicate_or_update_review", "manual_review")}
    return {
        "mode": "dry_run_only",
        "publication_enabled": False,
        "submitted": 0,
        "published": 0,
        "inventory_asserted_complete": complete,
        "counts": counts,
        "decisions": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Review input JSON file")
    parser.add_argument("--output", default="output/smart-publish-preview.json")
    args = parser.parse_args()
    document = json.loads(Path(args.input).read_text(encoding="utf-8"))
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    report = build_report(document, today)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
