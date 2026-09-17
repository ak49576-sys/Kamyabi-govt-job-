"""Read-only validation of the unified official Railway Recruitment Board portal."""
import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urldefrag

from state_psc_validation import LinkParser, fetch_html, official_https
from vacancy_scope import classify_vacancy

RRB_PORTAL = "https://rrb.indianrailways.gov.in/"
RRB_PAGES = (RRB_PORTAL, RRB_PORTAL + "chandigarh", RRB_PORTAL + "ajmer")
RRB_DOMAINS = ("indianrailways.gov.in",)
PORTAL_MARKER = re.compile(r"railway recruitment boards?|ministry of railways", re.IGNORECASE)
NOTICE_MARKER = re.compile(
    r"\bCEN\s*[A-Z0-9./-]*|centralised employment notice|"
    r"recruitment|notification|corrigendum|apply|\.pdf(?:$|[?#])",
    re.IGNORECASE,
)


def extract_candidates(page, base_url):
    parser = LinkParser()
    parser.feed(page)
    found, seen = [], set()
    for href, label in parser.links:
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = urldefrag(urljoin(base_url, html.unescape(href.strip())))[0]
        if not official_https(url, RRB_DOMAINS):
            continue
        title = re.sub(r"\s+", " ", label).strip()
        if not NOTICE_MARKER.search(title + " " + url):
            continue
        if url in seen:
            continue
        seen.add(url)
        found.append({"title": title[:300], "url": url})
    return found


def validate():
    attempts, candidates, seen = [], [], set()
    portal_verified = False
    fetched_pages = 0
    for url in RRB_PAGES:
        try:
            page, final_url, _ = fetch_html(url, RRB_DOMAINS)
            fetched_pages += 1
            if PORTAL_MARKER.search(page):
                portal_verified = True
            for candidate in extract_candidates(page, final_url):
                if candidate["url"] not in seen:
                    seen.add(candidate["url"])
                    candidates.append(candidate)
        except Exception as error:
            attempts.append({"url": url, "error": type(error).__name__ + ": " + str(error)})

    scope = classify_vacancy({
        "isGovernmentJob": True,
        "employer": "Railway Recruitment Board, Ministry of Railways",
    })
    if portal_verified and scope == "railways":
        status = "ok"
        detail = ""
    else:
        status = "needs_attention"
        detail = "Official RRB identity or railway scope could not be verified"

    return {
        "source": "railways",
        "name": "Railway Recruitment Boards",
        "status": status,
        "endpoint": RRB_PORTAL,
        "portal_verified": portal_verified,
        "scope_category": scope,
        "pages_fetched": fetched_pages,
        "candidate_links": len(candidates),
        "candidates": candidates[:100],
        "attempts": attempts,
        "publish_attempted": False,
        "detail": detail,
        "note": (
            "Official CEN/notification links only; no vacancy count, deadline, "
            "or job record was inferred."
        ),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", default="output/railways")
    args = cli.parse_args()
    report = validate()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2))
    (output / "summary.md").write_text(
        "## Railway recruitment validation\n\n"
        f"- Status: **{report['status']}**\n"
        f"- Official portal verified: **{report['portal_verified']}**\n"
        f"- Scope category: **{report['scope_category']}**\n"
        f"- Candidate links: **{report['candidate_links']}**\n"
        "- Publishing attempted: **No**\n"
        f"- Endpoint: {report['endpoint']}\n"
    )
    summary = {key: value for key, value in report.items() if key != "candidates"}
    print(json.dumps(summary, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
