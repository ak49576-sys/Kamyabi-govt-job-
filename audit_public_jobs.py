"""Read-only daily quality report for jobs exposed by Kamyabi's public API."""
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo

from api_http import NoRedirect
from check_api import USER_AGENT

URL = 'https://kamyabi.in/api/v1/jobs'


def read_public(opener=None):
    opener = opener or build_opener(NoRedirect)
    request = Request(URL, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json',
                                   'Cache-Control': 'no-cache'})
    with opener.open(request, timeout=30) as response:
        if response.status != 200 or 'json' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Public jobs API unavailable')
        document = json.loads(response.read(5_000_001))
    jobs = document.get('jobs') if isinstance(document, dict) else None
    if not isinstance(jobs, list) or not all(isinstance(j, dict) for j in jobs):
        raise ValueError('Unexpected public jobs API format')
    return jobs


def field(row, snake, camel):
    return row[snake] if snake in row else row.get(camel)


def audit(jobs, today):
    issues = []
    names = [field(j, 'job_id', 'jobId') for j in jobs]
    duplicates = {job_id for job_id, count in Counter(names).items() if job_id and count > 1}
    for row in jobs:
        job_id = field(row, 'job_id', 'jobId')
        if not isinstance(job_id, str) or not job_id:
            issues.append({'job_id': None, 'issue': 'missing_job_id'})
            continue
        if job_id in duplicates:
            issues.append({'job_id': job_id, 'issue': 'duplicate_public_id'})
        deadline = field(row, 'last_date', 'lastDate')
        try:
            if not isinstance(deadline, str):
                raise ValueError('Not a date string')
            closing = date.fromisoformat(deadline[:10])
            if closing < today:
                issues.append({'job_id': job_id, 'issue': 'expired_still_in_public_feed',
                               'last_date': deadline[:10]})
            elif closing.year > today.year + 2:
                issues.append({'job_id': job_id, 'issue': 'placeholder_or_distant_deadline',
                               'last_date': deadline[:10]})
        except ValueError:
            issues.append({'job_id': job_id, 'issue': 'invalid_or_missing_deadline'})
        notice = field(row, 'official_notification_url', 'officialNotificationUrl')
        parsed = urlparse(notice or '')
        if parsed.scheme != 'https' or not parsed.hostname:
            issues.append({'job_id': job_id, 'issue': 'missing_https_official_notification'})
    return {'checked_date_ist': today.isoformat(), 'public_job_records': len(jobs),
            'issues': issues, 'issue_counts': dict(Counter(i['issue'] for i in issues)),
            'published_or_changed': 0, 'note': 'Read-only audit; no job records were changed'}


def main():
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
    result = audit(read_public(), today)
    folder = Path('output/job-quality')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'public-job-audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'public_job_records': result['public_job_records'],
                      'issue_counts': result['issue_counts'], 'writes': 0}))


if __name__ == '__main__':
    main()
