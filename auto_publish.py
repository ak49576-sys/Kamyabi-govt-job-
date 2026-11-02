"""Conservative, opt-in approval of already staged Kamyabi jobs.

Only jobs present in the authenticated admin pending queue are considered.
Raw Apify candidates are never published by this module.
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo

from api_http import NoRedirect
from auto_import import SOURCES, load_queue
from check_api import USER_AGENT

ADMIN_LIST = 'https://kamyabi.in/api/v1/admin/jobs?status=pending'
ADMIN_UPDATE = 'https://kamyabi.in/api/v1/admin/jobs/update'


def admin_pending(key, opener=None):
    opener = opener or build_opener(NoRedirect)
    request = Request(ADMIN_LIST, headers={
        'X-Api-Key': key, 'Accept': 'application/json', 'User-Agent': USER_AGENT})
    with opener.open(request, timeout=30) as response:
        if response.status != 200 or 'json' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Authenticated pending-job API did not return JSON 200')
        payload = json.loads(response.read(2_000_001))
    if not isinstance(payload, dict) or not isinstance(payload.get('jobs'), list):
        raise ValueError('Unknown admin pending-job response; no approval attempted')
    return payload['jobs']


def field(record, *keys):
    for key in keys:
        if key in record:
            return record[key]
    return None


def eligible(job, pending, today):
    # Never publish sentinel or implausibly distant closing dates (e.g. 2099-12-31).
    # Two years is a generous limit for advance recruitment notices.
    try:
        deadline = datetime.strptime(job['last_date'], '%Y-%m-%d').date()
        if deadline.year > today.year + 2:
            return False, 'placeholder_or_distant_deadline'
    except (ValueError, TypeError, KeyError):
        return False, 'invalid_deadline'
    if job['last_date'] < today.isoformat():
        return False, 'expired'
    employer = job.get('recruiting_body')
    hosts = SOURCES.get(employer, set())
    if not hosts:
        return False, 'unrecognized_employer'
    for key in ('source_url', 'official_notification_url'):
        parsed = urlparse(job.get(key, ''))
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https' or not any(host == h or host.endswith('.' + h) for h in hosts):
            return False, 'unofficial_url'
    if not job.get('title') or not job.get('application_start_date') or not job.get('application_last_date'):
        return False, 'missing_basic_fields'
    if job['application_last_date'] != job['last_date']:
        return False, 'date_mismatch'
    item = next((x for x in pending if field(x, 'jobId', 'job_id') == job['job_id']), None)
    if item is None:
        return False, 'not_in_pending_queue'
    if field(item, 'verificationStatus', 'verification_status') != 'pending':
        return False, 'not_pending'
    if field(item, 'title') != job['title']:
        return False, 'pending_title_differs'
    pending_url = field(item, 'officialNotificationUrl', 'official_notification_url')
    if pending_url != job['official_notification_url']:
        return False, 'pending_official_url_differs'
    # A different job ID pointing to the same notice requires a human decision.
    if any(field(other, 'jobId', 'job_id') != job['job_id'] and
           field(other, 'officialNotificationUrl', 'official_notification_url') == pending_url
           for other in pending):
        return False, 'possible_duplicate'
    return True, 'basic_checks_passed'


def approve(job_id, key, opener=None):
    opener = opener or build_opener(NoRedirect)
    body = json.dumps({'job_id': job_id, 'fields': {
        'urlVerified': True, 'verificationStatus': 'approved'}}).encode()
    request = Request(ADMIN_UPDATE, data=body, method='PATCH', headers={
        'X-Api-Key': key, 'Content-Type': 'application/json',
        'Accept': 'application/json', 'User-Agent': USER_AGENT})
    with opener.open(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError('Approval endpoint returned unexpected status')
        result = json.loads(response.read(100_001))
    if not isinstance(result, dict) or result.get('ok') is not True or result.get('job_id') != job_id:
        raise ValueError('Approval response did not confirm job ID')
    if result.get('verification_status') != 'approved':
        raise ValueError('Approval response did not confirm approved status')


def run(root, key='', publish=False, today=None, get_pending=admin_pending, approve_job=approve):
    today = today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    jobs, expired = load_queue(root, today)
    report = {'mode': 'approval' if publish else 'preview', 'reviewed_jobs': len(jobs),
              'expired': expired, 'approved': [], 'held': [], 'status': 'ok'}
    if not jobs:
        return report
    if not key:
        report['status'] = 'configuration_required'
        report['note'] = 'KAMYABI_ADMIN_API_KEY is not configured; no approvals attempted'
        return report
    pending = get_pending(key)
    if not all(isinstance(item, dict) for item in pending):
        raise ValueError('Unexpected pending job rows')
    for job in jobs:
        ok, reason = eligible(job, pending, today)
        if not ok:
            report['held'].append({'job_id': job['job_id'], 'reason': reason})
            continue
        if publish:
            approve_job(job['job_id'], key)
            report['approved'].append(job['job_id'])
        else:
            report.setdefault('eligible_preview', []).append(job['job_id'])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    try:
        report = run(Path('.'), os.environ.get('KAMYABI_ADMIN_API_KEY', ''), args.publish)
    except Exception as error:
        report = {'status': 'error', 'error': str(error) if isinstance(error, ValueError) else type(error).__name__,
                  'approved': []}
    out = Path('output/automatic-publishing.json')
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 1 if report['status'] == 'error' else 0


if __name__ == '__main__':
    raise SystemExit(main())
