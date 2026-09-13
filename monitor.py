"""Collect official recruitment notice links; never publish or invent job details."""
import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen


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
        if not re.search(source['pattern'], title + ' ' + parsed.path + '?' + parsed.query, re.I):
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
    for attempt in range(3):
        try:
            request = Request(url, headers={'User-Agent': 'KamyabiRecruitmentMonitor/1.0 (+https://kamyabi.in)'})
            with urlopen(request, timeout=30) as response:
                content_type = response.headers.get('Content-Type', '')
                if 'html' not in content_type.lower():
                    raise ValueError('Source did not return HTML')
                data = response.read(5_000_001)
                if len(data) > 5_000_000:
                    raise ValueError('Source page exceeds 5 MB limit')
                return data.decode(response.headers.get_content_charset() or 'utf-8', errors='replace'), response.url
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


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
    for source in sources:
        try:
            html, final_url = fetch_page(source['url'])
            notices = extract(html, final_url, source)
            rows.extend(notices)
            results.append({'source': source['name'], 'status': 'ok' if notices else 'needs_attention',
                            'notice_links': len(notices),
                            'detail': '' if notices else 'No matching links. Check JavaScript rendering, selectors, or blocking.'})
        except Exception as error:
            results.append({'source': source['name'], 'status': 'error', 'notice_links': 0,
                            'detail': type(error).__name__ + ': ' + str(error)})
        time.sleep(1)
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
