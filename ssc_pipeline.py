"""Build a reviewable SSC dry-run report from the official advertisement API.

This module never submits jobs to Kamyabi. It only emits candidate records and
explicit rejection reasons for human review.
"""
import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from source_validation import SSC_ENDPOINT, dict_record_lists, fetch_json

TITLE_KEYS = ("title", "advertisementName", "advertisementTitle", "examName", "name")
ID_KEYS = ("id", "advertisementId", "advtId", "advertisementNo", "advtNo")
DEADLINE_KEYS = (
    "closingDate", "lastDate", "last_date", "applicationLastDate",
    "applicationEndDate", "endDate",
)
START_KEYS = ("openingDate", "startDate", "applicationStartDate", "applicationBeginDate")
URL_KEYS = (
    "notificationUrl", "notificationURL", "advertisementUrl", "advertisementURL",
    "documentUrl", "pdfUrl", "url",
)
VACANCY_KEYS = ("vacancyCount", "totalVacancy", "totalVacancies", "vacancies")


def first_value(record, keys):
    lowered = {str(key).lower(): value for key, value in record.items()}
    for key in keys:
        value = record.get(key, lowered.get(key.lower()))
        if value not in (None, ""):
            return value
    return None


def text_value(value):
    return str(value).strip() if value is not None else ""


def slug_piece(value):
    value = re.sub(r"[^a-z0-9]+", "-", text_value(value).lower()).strip("-")
    return value[:180]


def parse_date(value):
    """Return YYYY-MM-DD only when the source supplied an unambiguous real date."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        # Milliseconds/seconds are accepted only when they resolve to a plausible date.
        stamp = float(value)
        if stamp > 10_000_000_000:
            stamp /= 1000
        try:
            parsed = datetime.fromtimestamp(stamp, timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
        return parsed.isoformat() if 2000 <= parsed.year <= date.today().year + 2 else None
    raw = text_value(value)
    iso = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T ]|$)", raw)
    if iso:
        try:
            return date.fromisoformat(iso.group(1)).isoformat()
        except ValueError:
            return None
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            pass
    return None


def official_ssc_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    if host != "ssc.gov.in" and not host.endswith(".ssc.gov.in"):
        return None
    return value.strip().split("#", 1)[0]


def normalise_record(record, today=None):
    today = today or date.today()
    raw_id = first_value(record, ID_KEYS)
    title = text_value(first_value(record, TITLE_KEYS))
    deadline = parse_date(first_value(record, DEADLINE_KEYS))
    start = parse_date(first_value(record, START_KEYS))
    evidence = official_ssc_url(first_value(record, URL_KEYS))
    reasons = []
    stable = slug_piece(raw_id)
    if not stable:
        reasons.append("missing stable advertisement id")
    if not title:
        reasons.append("missing title")
    elif re.search(r"\b(?:demo|test)(?:ing)?\b|do not post", title, re.IGNORECASE):
        reasons.append("demo or test advertisement must never be published")
    if not deadline:
        reasons.append("missing or unparseable application deadline")
    elif date.fromisoformat(deadline) < today:
        reasons.append("application deadline has passed")
    if start and deadline and start > deadline:
        reasons.append("application start is after deadline")
    if not evidence:
        reasons.append("missing record-specific official SSC notification URL")

    candidate = {
        "job_id": f"ssc-advt-{stable}" if stable else None,
        "title": title or None,
        "department": "Staff Selection Commission",
        "qualification": None,
        "state_or_central": "Central Government",
        "source_url": SSC_ENDPOINT,
        "official_notification_url": evidence,
        "application_start_date": start,
        "application_last_date": deadline,
        "last_date": deadline,
        "recruiting_body": "SSC",
        "vacancy_count": None,
    }
    vacancy = first_value(record, VACANCY_KEYS)
    if isinstance(vacancy, int) and vacancy >= 0:
        candidate["vacancy_count"] = vacancy
    return {"eligible_for_review": not reasons, "reasons": reasons, "candidate": candidate}


def build_report(payload, today=None):
    lists = dict_record_lists(payload)
    records = max(lists, key=len) if lists else []
    seen, candidates, duplicates = set(), [], 0
    for record in records:
        result = normalise_record(record, today=today)
        job_id = result["candidate"]["job_id"]
        if job_id and job_id in seen:
            duplicates += 1
            continue
        if job_id:
            seen.add(job_id)
        candidates.append(result)
    eligible = sum(item["eligible_for_review"] for item in candidates)
    return {
        "source": "ssc",
        "mode": "dry_run",
        "fetched": len(records),
        "candidates": len(candidates),
        "eligible_for_review": eligible,
        "needs_manual_review": len(candidates) - eligible,
        "duplicates": duplicates,
        "submitted": 0,
        "publish_attempted": False,
        "records": candidates,
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", default="output/ssc")
    args = cli.parse_args()
    payload, endpoint, content_type = fetch_json(SSC_ENDPOINT, "ssc")
    report = build_report(payload)
    report.update({
        "endpoint": endpoint,
        "content_type": content_type,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "dry-run-report.json").write_text(json.dumps(report, indent=2))
    summary = {key: value for key, value in report.items() if key != "records"}
    (output / "counts.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
