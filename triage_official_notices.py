"""Prioritize official recruitment links without inventing vacancy details."""
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

OPENING = re.compile(r'\b(recruitment|vacanc(?:y|ies)|apprentice|advertisement|'
                     r'engagement|applications? invited|job openings?|CEN[- /0-9]|'
                     r'engineer trainees?|officer trainees?)\b', re.I)
NON_OPENING = re.compile(r'\b(result|merit list|shortlist(?:ed)?|admit card|'
                         r'answer key|call letters?|interview schedule|exam schedule|'
                         r'cut[- ]?off|document verification|waiting list|'
                         r'final selection|selected candidates)\b', re.I)


def classify(notice, today):
    title = str(notice.get('title', '')).strip()
    url = str(notice.get('notice_url', '')).strip()
    if not title or title.startswith('Untitled official link'):
        return 'needs_review', 'missing_descriptive_title'
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname:
        return 'excluded', 'invalid_official_link'
    if NON_OPENING.search(title):
        return 'excluded', 'non_opening_notice'
    if not OPENING.search(title):
        return 'needs_review', 'not_clearly_recruitment'
    # Prefer the advertisement year in the visible title over an unrelated URL year.
    years = set(re.findall(r'(?<!\d)20\d{2}(?!\d)', title))
    if not years:
        years = set(re.findall(r'(?<!\d)20\d{2}(?!\d)', parsed.path))
    if not years:
        return 'needs_review', 'year_unconfirmed'
    current = {str(today.year), str(today.year + 1)}
    if years.isdisjoint(current):
        return 'excluded', 'old_or_distant_year'
    # Year/title alone do not prove an open deadline or a real vacancy.
    return 'priority_review', 'recent_recruitment_title'


def triage(notices, today):
    groups = {'priority_review': [], 'needs_review': [], 'excluded': []}
    seen = set()
    for notice in notices:
        if not isinstance(notice, dict):
            continue
        url = str(notice.get('notice_url', '')).strip()
        key = url.casefold()
        if key in seen:
            continue
        seen.add(key)
        category, reason = classify(notice, today)
        groups[category].append({**notice, 'triage_reason': reason})
    return groups


def main():
    root = Path('output/official-coverage')
    doc = json.loads((root / 'notices.json').read_text())
    if not isinstance(doc.get('notices'), list):
        raise ValueError('Official coverage notices missing')
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    groups = triage(doc['notices'], today)
    fields = ['source', 'title', 'notice_url', 'triage_reason']
    for name, records in groups.items():
        with (root / (name + '.csv')).open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            # Protect spreadsheet viewers from formula-like remote titles.
            for record in records:
                writer.writerow({field: "'" + str(record.get(field, ''))
                                 if str(record.get(field, '')).lstrip().startswith(('=', '+', '-', '@'))
                                 else record.get(field, '') for field in fields})
    summary = {key: len(value) for key, value in groups.items()}
    summary['published'] = 0
    summary['note'] = 'Priority is editorial review only. Application deadlines and notification text are not verified.'
    (root / 'triage-summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
