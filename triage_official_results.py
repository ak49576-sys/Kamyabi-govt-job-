"""Triage official results links into a conservative, review-only shortlist.

Exam year is not publication date. Never label a notice as newly declared
or publishable until its official upload date and document are checked.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

RESULT = re.compile(r'\b(result(?:s)?|merit\s+list|shortlist(?:ed|ing)?|'
                    r'provisionally\s+selected|final\s+selection)\b', re.I)
NOT_RESULT = re.compile(r'\b(answer\s+keys?|admit\s+cards?|exam\s+schedule|'
                        r'vacanc(?:y|ies)|application\s+status|objection|'
                        r'document\s+verification|response\s+sheets?)\b', re.I)
YEAR = re.compile(r'(?<!\d)20\d{2}(?!\d)')


def classify(notice, current_year):
    title = str(notice.get('title') or '').strip()
    url = str(notice.get('notice_url') or '').strip()
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname:
        return 'held', 'invalid_official_url'
    if not title or title.startswith('Untitled official link'):
        return 'held', 'no_descriptive_title'
    if NOT_RESULT.search(title):
        return 'held', 'not_a_result_announcement'
    if not RESULT.search(title):
        return 'held', 'result_not_explicit_in_title'
    years = {int(value) for value in YEAR.findall(title)}
    if not years:
        return 'held', 'exam_year_unknown'
    if all(year < current_year - 1 or year > current_year for year in years):
        return 'held', 'historical_or_future_exam_cycle'
    return 'potential_current_cycle', 'exam_year_current_or_previous_unverified_upload_date'


def triage(notices, current_year):
    shortlisted, held, seen = [], [], set()
    for notice in notices:
        if not isinstance(notice, dict):
            continue
        url = str(notice.get('notice_url') or '').strip()
        key = url.casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        status, reason = classify(notice, current_year)
        row = {'source': notice.get('source'), 'title': notice.get('title'),
               'official_url': url, 'status': status, 'reason': reason,
               'verified_upload_date': None, 'reviewed': False, 'publishable': False}
        (shortlisted if status == 'potential_current_cycle' else held).append(row)
    return {'potential_current_cycle': shortlisted, 'held': held,
            'total_unique_links': len(seen), 'duplicates_removed': len(notices) - len(seen),
            'published': 0,
            'note': 'Exam year is not result publication date. Confirm official PDF, upload date, exam and stage before publication.'}


def main():
    folder = Path('output/official-results')
    source = json.loads((folder / 'notices.json').read_text())
    report = triage(source.get('notices', []), datetime.now(ZoneInfo('Asia/Kolkata')).year)
    (folder / 'triage.json').write_text(json.dumps(report, indent=2))
    (folder / 'priority-review.json').write_text(json.dumps({
        'reviewed': False, 'submission_ready': False,
        'candidates': report['potential_current_cycle'][:50],
        'note': report['note']}, indent=2))
    print(json.dumps({'unique_links': report['total_unique_links'],
                      'potential_current_cycle': len(report['potential_current_cycle']),
                      'held': len(report['held']), 'published': 0}))


if __name__ == '__main__':
    main()
