"""One-time, exact-precondition correction of the existing ONGC apprentice record.

Do not run against other jobs. This route deliberately uses two PATCH requests
because critical detail changes force a fresh pending review.
"""
import json
import os
from urllib.request import Request, build_opener

from api_http import NoRedirect
from check_api import USER_AGENT

JOB_ID = 'ongc-apprentice-2026'
LIST_URL = 'https://kamyabi.in/api/v1/admin/jobs?status='
UPDATE_URL = 'https://kamyabi.in/api/v1/admin/jobs/update'
PDF = ('https://www.ongcindia.com/documents/77751/2660534/'
       'Advertisement021126.pdf/3680ed1d-fcd1-cdde-c5af-1c25fcc3b8c8')
EXPECTED = {'last_date': '2026-11-05', 'application_start_date': '2026-10-06',
            'application_last_date': '2026-11-05',
            'official_notification_url': 'https://www.ongcindia.com/web/eng/career/recruitment-notice',
            'verification_status': 'approved'}
NEW = {'applicationStartDate': '2026-10-29',
       'applicationLastDate': '2026-11-20',
       'lastDate': '2026-11-20',
       'officialNotificationUrl': PDF,
       'vacancyCount': 3047}


def request_json(url, key, method='GET', body=None, opener=None):
    opener = opener or build_opener(NoRedirect)
    raw = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=raw, method=method, headers={
        'X-Api-Key': key, 'Accept': 'application/json',
        'Content-Type': 'application/json', 'User-Agent': USER_AGENT})
    with opener.open(req, timeout=30) as response:
        if response.status != 200 or 'json' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Admin API returned an unexpected status or content type')
        payload = json.loads(response.read(100_001))
    if not isinstance(payload, dict):
        raise ValueError('Admin API response is not a JSON object')
    return payload


def find_job(key, status, request=request_json):
    offset = 0
    while offset < 2000:
        payload = request(LIST_URL + status + '&limit=100&offset=' + str(offset), key)
        rows, total = payload.get('jobs'), payload.get('total')
        if not isinstance(rows, list) or type(total) is not int or total > 2000:
            raise ValueError('Unrecognized admin listing response')
        match = next((r for r in rows if isinstance(r, dict) and r.get('job_id') == JOB_ID), None)
        if match:
            return match
        offset += len(rows)
        if offset >= total:
            return None
        if not rows:
            raise ValueError('Admin pagination incomplete')
    raise ValueError('Admin pagination too large')


def correct(key, request=request_json, find=find_job):
    if not key or any(x in key for x in '\r\n'):
        raise ValueError('Admin API secret missing')
    record = find(key, 'approved')
    if record is None:
        return {'status': 'held', 'reason': 'job_not_currently_approved', 'writes': 0}
    differences = [field for field, expected in EXPECTED.items() if record.get(field) != expected]
    if differences:
        return {'status': 'held', 'reason': 'existing_record_changed',
                'different_fields': differences, 'writes': 0}
    body = {'job_id': JOB_ID, 'fields': NEW}
    first = request(UPDATE_URL, key, method='PATCH', body=body)
    if first.get('ok') is not True or first.get('job_id') != JOB_ID:
        raise ValueError('Phase-one correction response unconfirmed; inspect pending record')
    pending = find(key, 'pending')
    if not pending or pending.get('last_date') != '2026-11-20' or pending.get('official_notification_url') != PDF:
        raise ValueError('Updated pending record does not match; no approval attempted')
    second = request(UPDATE_URL, key, method='PATCH', body={
        'job_id': JOB_ID, 'fields': {'urlVerified': True, 'verificationStatus': 'approved'}})
    if second.get('ok') is not True or second.get('job_id') != JOB_ID or second.get('verification_status') != 'approved':
        raise ValueError('Approval response unconfirmed; inspect admin record')
    final = find(key, 'approved')
    if not final or final.get('last_date') != '2026-11-20':
        raise ValueError('Final approved date not confirmed; inspect admin record')
    return {'status': 'corrected_and_approved', 'job_id': JOB_ID,
            'closing_date': final.get('last_date'), 'writes': 2}


if __name__ == '__main__':
    try:
        print(json.dumps(correct(os.environ.get('KAMYABI_ADMIN_API_KEY', '')), indent=2))
    except Exception as error:
        print(json.dumps({'status': 'error', 'error_type': type(error).__name__,
                          'note': 'Check the existing record before retrying; operation may be partially complete'}, indent=2))
        raise SystemExit(1)
