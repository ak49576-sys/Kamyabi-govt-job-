"""Conservative SBI advertisement-number matching for Apify candidates.

A match is evidence for editorial review, not proof that all vacancy details are correct.
No import or publication occurs here.
"""
import csv
import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SBI_URL = "https://sbi.bank.in/web/careers/current-openings"
OFFICIAL_HOSTS = {"sbi.bank.in", "sbi.co.in", "bank.sbi"}


def match_sbi(rows, html):
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    text = re.sub(r"\s+", " ", text).upper()
    output = []
    for row in rows:
        board = (row.get("recruitmentBoard") or "").strip().lower()
        advert = (row.get("advtNo") or "").strip().upper()
        if board not in ("sbi", "state bank of india"):
            continue
        # Never match candidates without a full, specific advertisement number.
        valid = re.fullmatch(r"CRPD/SCO/20\d{2}-\d{2}/\d{1,3}", advert)
        found = bool(valid and re.search(r"(?<![A-Z0-9])" + re.escape(advert) + r"(?![A-Z0-9])", text))
        output.append({
            "title": (row.get("postName") or "").strip(),
            "advt_no": advert,
            "scraped_deadline": (row.get("lastDate") or "").strip(),
            "aggregator_url": (row.get("detailUrl") or "").strip(),
            "official_listing_url": SBI_URL if found else "",
            "verification_status": ("OFFICIAL_ADVERTISEMENT_NUMBER_MATCH_ONLY" if found else
                                    "NOT_CONFIRMED_ON_OFFICIAL_PAGE"),
            "publishable": False,
            "review_note": ("Check the official PDF, vacancies, eligibility, corrigenda and last date before staging."
                            if found else "Do not stage; exact official advertisement match not established."),
        })
    return output


def main():
    src = Path("/tmp/apify-dataset.csv")
    out = Path("output")
    out.mkdir(parents=True, exist_ok=True)
    with src.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    try:
        req = Request(SBI_URL, headers={"User-Agent": "KamyabiNoticeReview/1.0"})
        with urlopen(req, timeout=30) as response:
            host = (urlparse(response.geturl()).hostname or "").lower()
            if host not in OFFICIAL_HOSTS:
                raise ValueError("SBI official page redirected outside allowed domains")
            html = response.read(3_000_000).decode("utf-8", errors="replace")
        status = "official_page_accessible"
    except Exception:
        html = ""
        status = "official_page_unavailable"
    report = match_sbi(rows, html)
    fields = ["title", "advt_no", "scraped_deadline", "aggregator_url",
              "official_listing_url", "verification_status", "publishable", "review_note"]
    with (out / "sbi-official-matches.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report)
    summary = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": SBI_URL,
        "source_status": status,
        "official_html_bytes": len(html.encode("utf-8")),
        "raw_advert_prefix_occurrences": html.upper().count("CRPD"),
        "text_advert_prefix_occurrences": unescape(re.sub(r"<[^>]+>", " ", html)).upper().count("CRPD"),
        "sbi_candidates": len(report),
        "advertisement_number_matches": sum(
            r["verification_status"] == "OFFICIAL_ADVERTISEMENT_NUMBER_MATCH_ONLY" for r in report),
        "fully_verified": 0,
        "automatically_submitted": 0,
        "automatically_published": 0,
    }
    (out / "sbi-official-match-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
