"""Read-only, bounded official PDF evidence for editorial vacancy review."""
import argparse
import json
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from api_http import NoRedirect
from pypdf import PdfReader

DATE = re.compile(r'(?<!\d)(?:[0-3]?\d[./-][01]?\d[./-]20\d{2}|[0-3]?\d\s+[A-Za-z]{3,9}\s+20\d{2})(?!\d)', re.I)
CLOSING = re.compile(r'(?:last date|closing date|apply by|applications? (?:close|ends?))', re.I)
QUALIFICATIONS = re.compile(r'\b(?:B\.?TECH|B\.?E\.?|MBA|MCA|ITI|DIPLOMA|GRADUATE|12TH|10TH)\b', re.I)


def official_pdf(url, source_domains):
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and '.pdf' in parsed.path.lower()
            and any(host == d or host.endswith('.' + d) for d in source_domains))


def extract_evidence(text):
    normalized = re.sub(r'\s+', ' ', text)
    dates = []
    for match in DATE.finditer(normalized):
        context = normalized[max(0, match.start() - 90):match.start()]
        if CLOSING.search(context):
            dates.append({'observed': match.group(), 'context': context[-80:]})
        if len(dates) >= 12:
            break
    qualifications = sorted(set(token.upper() for token in QUALIFICATIONS.findall(normalized)))
    return {'possible_closing_dates': dates, 'qualification_keywords': qualifications,
            'vacancy_count_verified': False, 'publication_approved': False}


def fetch_pdf(url, opener=None):
    opener = opener or build_opener(NoRedirect)
    req = Request(url, headers={'User-Agent': 'KamyabiOfficialNoticeReview/1.0'})
    with opener.open(req, timeout=15) as response:
        if response.status != 200 or not response.headers.get('Content-Type', '').lower().startswith(('application/pdf', 'application/octet-stream')):
            raise ValueError('Unexpected official PDF response')
        payload = response.read(6_000_001)
    if len(payload) > 6_000_000 or not payload.startswith(b'%PDF-'):
        raise ValueError('Invalid or oversized PDF')
    reader = PdfReader(BytesIO(payload))
    if len(reader.pages) > 35:
        raise ValueError('PDF exceeds page limit')
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


def review(notices, sources, max_documents=5, fetch=fetch_pdf):
    allowed = {x['name']: set(x['allowed_domains']) for x in sources}
    output = []
    seen = set()
    for notice in notices:
        source = notice.get('source')
        url = notice.get('notice_url', '')
        if source not in allowed or not official_pdf(url, allowed[source]) or url in seen:
            continue
        seen.add(url)
        result = {'source': source, 'official_pdf_url': url,
                  'title_as_observed': notice.get('title', ''),
                  'publishable': False, 'reviewed': False}
        try:
            text = fetch(url)
            result.update(extract_evidence(text))
            result['status'] = 'text_extracted' if text.strip() else 'no_text_layer'
        except Exception as error:
            result['status'] = 'unavailable'
            result['reason'] = type(error).__name__
        output.append(result)
        if len(output) >= max_documents:
            break
    return {'submission_ready': False, 'published': 0, 'documents': output}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--sources', default='official-sources-expanded.json')
    cli.add_argument('--notices', default='output/official-coverage/notices.json')
    cli.add_argument('--output', default='output/official-coverage/pdf-evidence.json')
    args = cli.parse_args()
    sources = json.loads(Path(args.sources).read_text())
    notices = json.loads(Path(args.notices).read_text())['notices']
    result = review(notices, sources)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'documents_examined': len(result['documents']),
                      'text_extracted': sum(x['status'] == 'text_extracted' for x in result['documents']),
                      'published': 0}))


if __name__ == '__main__':
    main()
