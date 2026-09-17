"""Read-only validation for official State Public Service Commission sources."""
import argparse
import html
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

SOURCES = {
    "rpsc": {
        "name": "RPSC", "domains": ("rpsc.rajasthan.gov.in",),
        "urls": ("https://rpsc.rajasthan.gov.in/advertisements", "https://rpsc.rajasthan.gov.in/"),
    },
    "uppsc": {
        "name": "UPPSC", "domains": ("uppsc.up.nic.in",),
        "urls": ("https://uppsc.up.nic.in/CandidatePages/Notifications.aspx", "https://uppsc.up.nic.in/"),
    },
    "mppsc": {
        "name": "MPPSC", "domains": ("mppsc.mp.gov.in",),
        "urls": ("https://mppsc.mp.gov.in/Advertisement", "https://mppsc.mp.gov.in/"),
    },
    "bpsc": {
        "name": "BPSC", "domains": ("bpsc.bihar.gov.in",),
        "urls": ("https://bpsc.bihar.gov.in/",),
    },
    "hpsc": {
        "name": "HPSC", "domains": ("hpsc.gov.in",),
        "urls": ("https://hpsc.gov.in/en-us/", "https://hpsc.gov.in/"),
    },
    "ukpsc": {
        "name": "UKPSC", "domains": ("psc.uk.gov.in",),
        "urls": ("https://psc.uk.gov.in/",),
    },
    "jpsc": {
        "name": "JPSC", "domains": ("jpsc.gov.in",),
        "urls": ("https://www.jpsc.gov.in/exam_files.php?id=1", "https://www.jpsc.gov.in/"),
    },
    "wbpsc": {
        "name": "WBPSC", "domains": ("psc.wb.gov.in",),
        "urls": ("https://psc.wb.gov.in/advertisement.jsp", "https://psc.wb.gov.in/"),
    },
    "gpsc": {
        "name": "GPSC", "domains": ("gpsc.gujarat.gov.in",),
        "urls": ("https://gpsc.gujarat.gov.in/",),
    },
    "mpsc": {
        "name": "MPSC", "domains": ("mpsc.gov.in",),
        "urls": ("https://mpsc.gov.in/",),
    },
}
KEYWORDS = re.compile(
    r"advertisement|notification|recruitment|apply online|vacan(?:cy|cies)|corrigendum|\.pdf(?:$|[?#])",
    re.IGNORECASE,
)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.href, self.parts = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.parts = []

    def handle_data(self, data):
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href is not None:
            self.links.append((self.href, " ".join(self.parts).strip()))
            self.href, self.parts = None, []


def official_https(url, domains):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and any(host == domain or host.endswith("." + domain) for domain in domains))


def fetch_html(url, domains):
    if not official_https(url, domains):
        raise ValueError("Configured URL is outside the official HTTPS domain")
    with tempfile.TemporaryDirectory() as directory:
        body = Path(directory) / "page.html"
        result = subprocess.run([
            "curl", "--ipv4", "--silent", "--show-error", "--location",
            "--proto", "=https", "--proto-redir", "=https",
            "--connect-timeout", "8", "--max-time", "25", "--max-filesize", "5000000",
            "--user-agent", "Mozilla/5.0 (compatible; KamyabiStatePSCValidator/1.0; +https://kamyabi.in)",
            "--header", "Accept: text/html,application/xhtml+xml",
            "--output", str(body),
            "--write-out", "%{http_code}\n%{url_effective}\n%{content_type}",
            url,
        ], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or f"curl exit {result.returncode}")
        status, final_url, content_type = result.stdout.split("\n", 2)
        if not official_https(final_url, domains):
            raise ValueError("Official page redirected outside its allowed domain")
        if status != "200":
            raise RuntimeError(f"HTTP {status} from {final_url}")
        page = body.read_text(encoding="utf-8", errors="replace")
        if len(page.strip()) < 200:
            raise ValueError("Official page returned no usable HTML")
        return page, final_url, content_type


def candidate_links(page, base_url, domains):
    parser = LinkParser()
    parser.feed(page)
    result, seen = [], set()
    for href, label in parser.links:
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urldefrag(urljoin(base_url, html.unescape(href.strip())))[0]
        if not official_https(absolute, domains):
            continue
        text = re.sub(r"\s+", " ", label).strip()
        if not KEYWORDS.search(text + " " + absolute):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        result.append({"title": text[:300], "url": absolute})
    return result


def validate(source):
    config = SOURCES[source]
    attempts = []
    for url in config["urls"]:
        try:
            page, final_url, content_type = fetch_html(url, config["domains"])
            links = candidate_links(page, final_url, config["domains"])
            if not links:
                raise ValueError("No official recruitment candidate links found")
            return {
                "source": source, "commission": config["name"], "status": "ok",
                "endpoint": final_url, "content_type": content_type,
                "candidate_links": len(links), "candidates": links[:50],
                "attempts": attempts, "publish_attempted": False,
                "note": "Candidate links only; no vacancy, deadline, or job record was inferred.",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as error:
            attempts.append({"url": url, "error": type(error).__name__ + ": " + str(error)})
    return {
        "source": source, "commission": config["name"], "status": "needs_attention",
        "endpoint": config["urls"][0], "candidate_links": 0, "candidates": [],
        "attempts": attempts, "publish_attempted": False,
        "note": "No jobs were created or published.",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--source", required=True, choices=tuple(SOURCES))
    cli.add_argument("--output", default="output/state-psc")
    args = cli.parse_args()
    report = validate(args.source)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2))
    (output / "summary.md").write_text(
        f"## {report['commission']} official-source validation\n\n"
        f"- Status: **{report['status']}**\n"
        f"- Candidate links: **{report['candidate_links']}**\n"
        f"- Publishing attempted: **No**\n"
        f"- Endpoint: {report['endpoint']}\n"
    )
    summary = {key: value for key, value in report.items() if key != "candidates"}
    print(json.dumps(summary, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
