"""Validate official SSC, UPSC, and RPSC sources without publishing jobs."""
import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from monitor import check_source

SSC_ENDPOINT = "https://ssc.gov.in/api/admin/5.1/getAllCandiateAdvertisements"
OFFICIAL_DOMAINS = {
    "ssc": ("ssc.gov.in",),
    "upsc": ("upsc.gov.in", "upsconline.nic.in"),
    "rpsc": ("rpsc.rajasthan.gov.in",),
}
HTML_SOURCES = {
    "upsc": {
        "name": "UPSC",
        "url": "https://www.upsc.gov.in/recruitment/recruitment-advertisement",
        "allowed_domains": ["upsc.gov.in", "upsconline.nic.in"],
        "pattern": r"advertisement|recruit|corrigendum|\.pdf$",
        "fallback_urls": ["https://upsc.gov.in/recruitment/recruitment-advertisement"],
    },
    "rpsc": {
        "name": "RPSC",
        "url": "https://rpsc.rajasthan.gov.in/advertisements",
        "allowed_domains": ["rpsc.rajasthan.gov.in"],
        "pattern": r"advertisement|recruit|corrigendum|\.pdf$|Pie=",
        "fallback_urls": ["https://rpsc.rajasthan.gov.in/"],
    },
}


def official_https(url, source):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and any(host == domain or host.endswith("." + domain)
                    for domain in OFFICIAL_DOMAINS[source]))


def fetch_json(url, source):
    if not official_https(url, source):
        raise ValueError("Endpoint is outside the allowed official HTTPS domain")
    with tempfile.TemporaryDirectory() as directory:
        body = Path(directory) / "response.json"
        result = subprocess.run([
            "curl", "--ipv4", "--silent", "--show-error", "--location",
            "--proto", "=https", "--proto-redir", "=https",
            "--connect-timeout", "8", "--max-time", "25", "--max-filesize", "5000000",
            "--user-agent", "Mozilla/5.0 (compatible; KamyabiSourceValidator/1.0; +https://kamyabi.in)",
            "--header", "Accept: application/json",
            "--output", str(body),
            "--write-out", "%{http_code}\n%{url_effective}\n%{content_type}",
            url,
        ], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or f"curl exit {result.returncode}")
        status, final_url, content_type = result.stdout.split("\n", 2)
        if not official_https(final_url, source):
            raise ValueError("Official endpoint redirected outside its allowed domain")
        if status != "200":
            raise RuntimeError(f"HTTP {status} from {final_url}")
        try:
            payload = json.loads(body.read_text(encoding="utf-8", errors="strict"))
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError("Official endpoint did not return valid JSON") from error
        return payload, final_url, content_type


def dict_record_lists(value):
    found = []
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            found.append(value)
        for item in value:
            found.extend(dict_record_lists(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(dict_record_lists(item))
    return found


def validate_ssc():
    payload, final_url, content_type = fetch_json(SSC_ENDPOINT, "ssc")
    record_lists = dict_record_lists(payload)
    records = max(record_lists, key=len) if record_lists else []
    if not records:
        raise ValueError("SSC response contained no advertisement records")
    return {
        "source": "SSC",
        "status": "ok",
        "endpoint": final_url,
        "content_type": content_type,
        "records_observed": len(records),
        "publish_attempted": False,
        "note": "Advertisement records observed only; dates and notifications require separate review.",
    }


def validate_html(source):
    notices, report = check_source(HTML_SOURCES[source])
    return {
        "source": source.upper(),
        "status": report["status"],
        "endpoint": report.get("fetched_url") or HTML_SOURCES[source]["url"],
        "records_observed": len(notices),
        "attempts": report.get("attempts", []),
        "detail": report.get("detail", ""),
        "publish_attempted": False,
        "note": "Official candidate links observed only; no dates or job facts were inferred.",
    }


def validate(source):
    try:
        report = validate_ssc() if source == "ssc" else validate_html(source)
    except Exception as error:
        report = {
            "source": source.upper(),
            "status": "needs_attention",
            "endpoint": SSC_ENDPOINT if source == "ssc" else HTML_SOURCES[source]["url"],
            "records_observed": 0,
            "detail": type(error).__name__ + ": " + str(error),
            "publish_attempted": False,
        }
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--source", required=True, choices=("ssc", "upsc", "rpsc"))
    cli.add_argument("--output", default="output/source-validation")
    args = cli.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    report = validate(args.source)
    (output / "report.json").write_text(json.dumps(report, indent=2))
    (output / "summary.md").write_text(
        f"## {report['source']} validation\n\n"
        f"- Status: **{report['status']}**\n"
        f"- Records observed: **{report['records_observed']}**\n"
        f"- Publishing attempted: **No**\n"
        f"- Endpoint: {report['endpoint']}\n"
        f"- Detail: {report.get('detail', '')}\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
