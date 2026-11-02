"""Conservative SBI advertisement-number matching for Apify candidates.

A match is evidence for editorial review, not proof that all vacancy details are correct.
No import or publication occurs here.
"""
import csv
import json
import re
from io import BytesIO
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, unquote
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SBI_URL = "https://sbi.bank.in/web/careers/current-openings"
SBI_URLS = [SBI_URL, "https://sbi.bank.in/web/careers/Current-openings",
            "https://sbi.bank.in/en/web/careers/current-openings"]
OFFICIAL_HOSTS = {"sbi.bank.in", "sbi.co.in", "bank.sbi"}



def find_official_pdf(html, advert, base_url):
    """Return only an official PDF URL with the same year and advert suffix."""
    match = re.fullmatch(r"CRPD/SCO/(20\d{2}-\d{2})/(\d{1,3})", advert)
    if not match:
        return ""
    year, number = match.groups()
    pattern = re.compile(re.escape(year) + r"[^0-9]{1,15}0?" + re.escape(number) + r"(?![0-9])", re.I)
    for raw in re.findall(r'href="([^"]+)"', html, flags=re.I):
        candidate = urljoin(base_url, unescape(raw))
        parsed = urlparse(candidate)
        path = unquote(parsed.path)
        if (parsed.scheme == "https" and (parsed.hostname or "").lower() in OFFICIAL_HOSTS
                and ".pdf" in path.lower() and pattern.search(path)):
            return candidate
    return ""


def pdf_reachable(url):
    if not url:
        return False
    try:
        with urlopen(Request(url, headers={"User-Agent": "KamyabiNoticeReview/1.0"}), timeout=20) as response:
            final = urlparse(response.geturl())
            return (final.scheme == "https" and (final.hostname or "").lower() in OFFICIAL_HOSTS
                    and response.read(5).startswith(b"%PDF-"))
    except Exception:
        return False



def inspect_pdf_text(text, advert, scraped_deadline):
    normalized = re.sub(r"\s+", " ", text).upper()
    advert_match = bool(re.search(re.escape(advert), normalized))
    deadline_match = False
    try:
        deadline = datetime.strptime(scraped_deadline, "%d-%m-%Y")
        pattern = (rf"{deadline.day:02d}[./-]{deadline.month:02d}[./-]{deadline.year}"
                   rf"(?=\D|$)")
        deadline_match = bool(re.search(pattern, normalized))
    except ValueError:
        pass
    return {"advertisement_in_pdf": advert_match, "deadline_in_pdf": deadline_match}


def extract_official_pdf_text(url):
    if not url:
        return "", "NO_OFFICIAL_PDF"
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "PDF_TEXT_TOOL_UNAVAILABLE"
    try:
        with urlopen(Request(url, headers={"User-Agent": "KamyabiNoticeReview/1.0"}), timeout=25) as response:
            final = urlparse(response.geturl())
            if final.scheme != "https" or (final.hostname or "").lower() not in OFFICIAL_HOSTS:
                return "", "PDF_REDIRECT_UNTRUSTED"
            pdf = response.read(8_000_001)
        if len(pdf) > 8_000_000 or not pdf.startswith(b"%PDF-"):
            return "", "PDF_INVALID_OR_TOO_LARGE"
        reader = PdfReader(BytesIO(pdf))
        if len(reader.pages) > 50:
            return "", "PDF_TOO_MANY_PAGES"
        text = "\\n".join(page.extract_text() or "" for page in reader.pages)
        return text, "PDF_TEXT_EXTRACTED"
    except Exception:
        return "", "PDF_TEXT_EXTRACTION_FAILED"


def match_sbi(rows, html, official_url=SBI_URL):
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
        official_pdf = find_official_pdf(html, advert, official_url) if found else ""
        document_reachable = pdf_reachable(official_pdf)
        document_text, pdf_text_status = (extract_official_pdf_text(official_pdf)
                                          if document_reachable else ("", "NO_OFFICIAL_PDF"))
        checks = inspect_pdf_text(document_text, advert, (row.get("lastDate") or "").strip())
        output.append({
            "title": (row.get("postName") or "").strip(),
            "advt_no": advert,
            "scraped_deadline": (row.get("lastDate") or "").strip(),
            "aggregator_url": (row.get("detailUrl") or "").strip(),
            "official_listing_url": official_url if found else "",
            "official_document_url": official_pdf,
            "official_document_reachable": document_reachable,
            "pdf_text_status": pdf_text_status,
            "advertisement_in_pdf": checks["advertisement_in_pdf"],
            "deadline_in_pdf": checks["deadline_in_pdf"],
            "verification_status": ("OFFICIAL_PDF_LINK_FOUND_REQUIRES_CONTENT_REVIEW" if document_reachable else
                                    "OFFICIAL_ADVERTISEMENT_NUMBER_MATCH_ONLY" if found else
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
    html = ""
    status = "official_page_unavailable"
    checked_urls = []
    matched_source_url = SBI_URL
    for source_url in SBI_URLS:
        try:
            req = Request(source_url, headers={"User-Agent": "KamyabiNoticeReview/1.0"})
            with urlopen(req, timeout=20) as response:
                host = (urlparse(response.geturl()).hostname or "").lower()
                if host not in OFFICIAL_HOSTS:
                    raise ValueError("Redirect outside allowed SBI domains")
                candidate_html = response.read(3_000_000).decode("utf-8", errors="replace")
            checked_urls.append(source_url)
            if not html:
                html = candidate_html
                status = "official_page_accessible_but_listings_not_in_html"
            if "CRPD" in candidate_html.upper():
                html = candidate_html
                matched_source_url = source_url
                status = "official_listing_text_available"
                break
        except Exception:
            continue
    report = match_sbi(rows, html, matched_source_url)
    fields = ["title", "advt_no", "scraped_deadline", "aggregator_url",
              "official_listing_url", "official_document_url", "official_document_reachable", "pdf_text_status",
              "advertisement_in_pdf", "deadline_in_pdf",
              "verification_status", "publishable", "review_note"]
    with (out / "sbi-official-matches.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report)
    summary = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": SBI_URL,
        "official_urls_checked": checked_urls,
        "source_status": status,
        "official_html_bytes": len(html.encode("utf-8")),
        "raw_advert_prefix_occurrences": html.upper().count("CRPD"),
        "script_sources": sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', html, flags=re.I)))[:25],
        "text_advert_prefix_occurrences": unescape(re.sub(r"<[^>]+>", " ", html)).upper().count("CRPD"),
        "sbi_candidates": len(report),
        "advertisement_number_matches": sum(
            r["verification_status"] != "NOT_CONFIRMED_ON_OFFICIAL_PAGE" for r in report),
        "official_pdf_links_reachable": sum(r["official_document_reachable"] for r in report),
        "pdf_advert_and_deadline_matches": sum(r["advertisement_in_pdf"] and r["deadline_in_pdf"] for r in report),
        "pdf_text_statuses": [r["pdf_text_status"] for r in report],
        "advertisement_in_pdf_count": sum(r["advertisement_in_pdf"] for r in report),
        "deadline_in_pdf_count": sum(r["deadline_in_pdf"] for r in report),
        "fully_verified": 0,
        "automatically_submitted": 0,
        "automatically_published": 0,
    }
    (out / "sbi-official-match-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
