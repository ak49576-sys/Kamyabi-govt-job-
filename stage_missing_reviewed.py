"""Stage previously reviewed vacancies that are genuinely absent from Kamyabi.

Never imports raw Apify/monitor output. Checks all admin states before any write.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo

from api_http import NoRedirect
from auto_import import load_queue
from check_api import USER_AGENT
from submit_jobs import send_jobs

ADMIN_URL = 'https://kamyabi.in/api/v1/admin/jobs'
STATUSES = ('pending', 'approved', 'rejected')


def admin_inventory(key, opener=None):
    if not key or any(char in key for char in '\r\n'):
        raise ValueError('KAMYABI_ADMIN_API_KEY is required for safe duplicate checks')
    opener = opener or build_opener(NoRedirect)
    inventory = []
    for status in STATUSES:
        offset = 0
        while True:
            url = ADMIN_URL + '?' + urlencode({'status': status, 'limit': 100, 'offset': offset})
            request = Request(url, headers={'X-Api-Key': key, 'Accept': 'application/json',
                                            'User-Agent': USER_AGENT})
            with opener.open(request, timeout=30) as response:
                if response.status != 200 or 'json' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Admin inventory unavailable; no staging attempted')
                document = json.loads(response.read(2_000_001))
            jobs = document.get('jobs') if isinstance(document, dict) else None
            total = document.get('total') if isinstance(document, dict) else None
            if not isinstance(jobs, list) or not isinstance(total, int) or total < 0:
                raise ValueError('Invalid admin inventory response; no staging attempted')
            if not all(isinstance(job, dict) for job in jobs):
                raise ValueError('Invalid admin job records; no staging attempted')
            inventory.extend(jobs)
            offset += len(jobs)
            if offset >= total:
                break
            if not jobs or offset > 5000:
                raise ValueError('Incomplete admin inventory; no staging attempted')
    return inventory


def value(row, snake, camel):
    return row[snake] if snake in row else row.get(camel)


def stage_missing(jobs, existing, key, send=send_jobs):
    if any(not isinstance(value(row, 'job_id', 'jobId'), str) or not value(row, 'job_id', 'jobId') for row in existing):
        raise ValueError('Admin inventory contained a job without an ID; no staging attempted')
    ids = {value(row, 'job_id', 'jobId') for row in existing}
    urls = {value(row, 'official_notification_url', 'officialNotificationUrl')
            for row in existing if value(row, 'official_notification_url', 'officialNotificationUrl')}
    missing, held, already = [], [], []
    for job in jobs:
        if job['job_id'] in ids:
            already.append(job['job_id'])
        elif job['official_notification_url'] in urls:
            held.append({'job_id': job['job_id'], 'reason': 'same_official_notice_already_exists'})
        else:
            missing.append(job)
            ids.add(job['job_id'])
            urls.add(job['official_notification_url'])
    report = {'eligible_reviewed': len(jobs), 'already_in_admin': already,
              'held': held, 'to_stage': [job['job_id'] for job in missing],
              'submitted': 0, 'status': 'ok'}
    if missing:
        if not key:
            raise ValueError('KAMYABI_API_KEY required to stage reviewed jobs')
        for start in range(0, len(missing), 100):
            response = send(missing[start:start + 100], key)
            if response.get('inserted', 0) + response.get('updated', 0) + response.get('skipped', 0) != len(missing[start:start + 100]):
                raise ValueError('Unexpected staging response; check admin before retry')
            if response.get('updated', 0) or response.get('skipped', 0):
                raise ValueError('Staging did not insert every new ID; inspect admin before retry')
            report['submitted'] += response.get('inserted', 0)
    return report


def main():
    report = {'status': 'error', 'submitted': 0}
    try:
        today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        jobs, expired = load_queue(Path('.'), today)
        inventory = admin_inventory(os.environ.get('KAMYABI_ADMIN_API_KEY', ''))
        report = stage_missing(jobs, inventory, os.environ.get('KAMYABI_API_KEY', ''))
        report['expired'] = expired
        report['note'] = 'Only reviewed repository records; raw listings are never staged'
    except Exception as error:
        report = {'status': 'error', 'submitted': 0,
                  'error': str(error) if isinstance(error, ValueError) else type(error).__name__}
    output = Path('output/reviewed-staging.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
