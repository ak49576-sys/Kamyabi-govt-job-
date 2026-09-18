"""Read-only validation of current RITES (Railway PSU) vacancies."""
import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urldefrag

from state_psc_validation import LinkParser, fetch_html, official_https
from vacancy_scope import classify_vacancy

RITES_CAREERS = "https://rites.com/"
RITES_DOMAINS = ("rites.com",)
IDENTITY_MARKER = re.compile(r"RITES|Rail India Technical and Economic Service", re.I)
VACANCY_MARKER = re.compile(r"recruitment|vacanc|career|advertisement|\.pdf(?:$|[?#])", re.I)


def extract_candidates(page, base_url):
    parser = LinkParser()
    parser.feed(page)
    found, seen = [], set()
    for href, label in parser.links:
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = urldefrag(urljoin(base_url, html.unescape(href.strip())))[0]
        title = re.sub(r"\s+", " ", label).strip()
        if not official_https(url, RITES_DOMAINS):
            continue
        if not VACANCY_MARKER.search(title + " " + url):
            continue
        if url in seen:
            continue
        seen.add(url)
        found.append({"title": title[:300], "url": url})
    return found


def validate():
    attempts, candidates = [], []
    verified = False
    try:
        page, final_url, _ = fetch_html(RITES_CAREERS, RITES_DOMAINS)
        verified = bool(IDENTITY_MARKER.search(page))
        candidates = extract_candidates(page, final_url)
    except Exception as error:
        attempts.append({"url": RITES_CAREERS, "error": type(error).__name__ + ": " + str(error)})

    scope = classify_vacancy({
        "isGovernmentJob": True,
        "employer": "RITES Ltd, Ministry of Railways, Government of India",
    })
    status = "ok" if verified and scope == "railways" else "needs_attention"
    return {
        "source": "rites",
        "name": "RITES Ltd (Railway PSU)",
        "status": status,
        "endpoint": RITES_CAREERS,
        "official_identity_verified": verified,
        "scope_category": scope,
        "candidate_links": len(candidates),
        "candidates": candidates[:100],
        "attempts": attempts,
        "publish_attempted": False,
        "note": "Discovery only. No record may be published without an official RITES notice, explicit closing date, and vacancy data.",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", default="output/rites")
    args = cli.parse_args()
    report = validate()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2))
    (output / "summary.md").write_text(
        "## RITES Railway PSU validation\n\n"
        f"- Status: **{report['status']}**\n"
        f"- Official identity verified: **{report['official_identity_verified']}**\n"
        f"- Scope category: **{report['scope_category']}**\n"
        f"- Candidate links: **{report['candidate_links']}**\n"
        "- Publishing attempted: **No**\n"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "candidates"}, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
