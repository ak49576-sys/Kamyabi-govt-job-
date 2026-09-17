"""Validate the official National Career Service government-job listing without publishing."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from state_psc_validation import fetch_html

NCS_ENDPOINT = "https://ncs.gov.in/job-listing?isGovernmentJob=true"
NCS_DOMAINS = ("ncs.gov.in",)
GOVERNMENT_MARKERS = (
    re.compile(r"jobs?\s+in\s+government\s+sector", re.IGNORECASE),
    re.compile(r"isGovernmentJob\s*=\s*true", re.IGNORECASE),
)


def validate():
    try:
        page, final_url, content_type = fetch_html(NCS_ENDPOINT, NCS_DOMAINS)
        markers = [pattern.pattern for pattern in GOVERNMENT_MARKERS if pattern.search(page)]
        if not markers:
            raise ValueError("NCS page did not contain the government-job filter marker")
        report = {
            "source": "ncs",
            "name": "National Career Service",
            "status": "ok",
            "endpoint": final_url,
            "content_type": content_type,
            "government_filter_verified": True,
            "dynamic_listing": True,
            "records_observed": None,
            "publish_attempted": False,
            "note": (
                "Official government-job listing is reachable. Job cards load dynamically, "
                "so no vacancy count, dates, or job records were inferred from the HTML shell."
            ),
        }
    except Exception as error:
        report = {
            "source": "ncs",
            "name": "National Career Service",
            "status": "needs_attention",
            "endpoint": NCS_ENDPOINT,
            "government_filter_verified": False,
            "dynamic_listing": True,
            "records_observed": None,
            "publish_attempted": False,
            "detail": type(error).__name__ + ": " + str(error),
            "note": "No jobs were created or published.",
        }
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", default="output/ncs")
    args = cli.parse_args()
    report = validate()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2))
    (output / "summary.md").write_text(
        "## National Career Service validation\n\n"
        f"- Status: **{report['status']}**\n"
        f"- Government filter verified: **{report['government_filter_verified']}**\n"
        "- Records inferred from dynamic page: **0**\n"
        "- Publishing attempted: **No**\n"
        f"- Endpoint: {report['endpoint']}\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
