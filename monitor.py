"""Collect official recruitment notice links; never publish or invent job details."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.parts = []

    def handle_data(self, data):
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None:
            self.links.append((self.href, ' '.join(' '.join(self.parts).split())))
            self.href = None


def extract(html, base_url, source):
    parser = Links()
    parser.feed(html)
    found = {}
    for href, title in parser.links:
        url = urldefrag(urljoin(base_url, href))[0]
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https' or not any(
            host == domain or host.endswith('.' + domain)
            for domain in source['allowed_domains']
        ):
            continue
        if not (re.search(source['pattern'], title + ' ' + parsed.path, re.I)
                or re.search(source['pattern'], parsed.query, re.I)):
            continue
        notice_id = hashlib.sha256((source['name'] + '\n' + url).encode()).hexdigest()[:24]
        found[notice_id] = {
            'notice_id': notice_id, 'source': source['name'],
            'title': title or 'Untitled official link — review required',
            'notice_url': url, 'source_url': source['url'],
            'status': 'needs_review',
        }
    return list(found.values())


def fetch_page(url):
    # curl uses the runner's system certificate store; IPv4 avoids unreachable IPv6 routes.
    # Certificate validation stays enabled. No proxy or challenge bypass is used.
    with tempfile.TemporaryDirectory() as directory:
        body = Path(directory) / 'page.html'
        result = subprocess.run([
            'curl', '--ipv4', '--silent', '--show-error', '--location',
            '--proto', '=https', '--proto-redir', '=https',
            '--connect-timeout', '8', '--max-time', '20', '--max-filesize', '5000000',
            '--user-agent', 'Mozilla/5.0 (compatible; KamyabiRecruitmentMonitor/1.1; +https://kamyabi.in)',
            '--output', str(body), '--write-out', '%{http_code}\n%{url_effective}\n%{content_type}', url,
        ], capture_output=True, text=True, timeout=25)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or f'curl exit {result.returncode}')
        status, final_url, content_type = result.stdout.split('\n', 2)
        if status != '200':
            raise RuntimeError(f'HTTP {status} from {final_url}')
        if 'html' not in content_type.lower():
            raise ValueError('Source did not return HTML')
        return body.read_text(encoding='utf-8', errors='replace'), final_url


def check_source(source):
    attempts = []
    for url in [source['url'], *source.get('fallback_urls', [])]:
        try:
            html, final_url = fetch_page(url)
            notices = extract(html, final_url, source)
            if notices:
                return notices, {'source': source['name'], 'status': 'ok', 'notice_links': len(notices),
                                 'detail': '', 'fetched_url': final_url, 'attempts': attempts}
            attempts.append({'url': url, 'error': 'No matching links; check rendering or page structure.'})
        except Exception as error:
            attempts.append({'url': url, 'error': type(error).__name__ + ': ' + str(error)})
        time.sleep(1)
    return [], {'source': source['name'], 'status': 'needs_attention', 'notice_links': 0,
                'detail': ' | '.join(a['error'] for a in attempts), 'attempts': attempts}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--sources', default=str(Path(__file__).with_name('sources.json')))
    cli.add_argument('--output', default='output')
    args = cli.parse_args()
    sources = json.loads(Path(args.sources).read_text())
    if not sources:
        raise ValueError('No sources configured')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    rows, results = [], []
    timestamp = datetime.now(timezone.utc).isoformat()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for notices, result in pool.map(check_source, sources):
            rows.extend(notices)
            results.append(result)
    (output / 'notices.json').write_text(json.dumps({'checked_at': timestamp, 'notices': rows}, indent=2))
    fields = ['notice_id', 'source', 'title', 'notice_url', 'source_url', 'status']
    with (output / 'notices.csv').open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        # Prevent spreadsheet formula execution when reviewing remote link text.
        writer.writerows({k: "'" + str(v) if str(v).lstrip().startswith(('=', '+', '-', '@')) else v
                          for k, v in row.items()} for row in rows)
    report = {'checked_at': timestamp, 'candidate_links': len(rows), 'sources': results,
              'published_jobs': 0, 'note': 'Links are candidates, not verified active vacancies. Each run is a snapshot.'}
    (output / 'report.json').write_text(json.dumps(report, indent=2))
    summary = '\n'.join([f'# Kamyabi recruitment check — {timestamp}',
                         f'{len(rows)} candidate links. 0 jobs published.',
                         '', *[f"- {s['source']}: {s['status']} ({s['notice_links']} links). {s['detail']}" for s in results],
                         '', 'Download the recruitment-report artifact and review notices.csv.'])
    (output / 'summary.md').write_text(summary)
    print(summary)
    return 1 if any(s['status'] != 'ok' for s in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
