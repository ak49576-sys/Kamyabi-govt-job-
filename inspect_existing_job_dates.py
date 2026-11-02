"""Read-only inspection of two existing Kamyabi records before correcting deadlines."""
import json
import os
from urllib.request import Request, build_opener

from api_http import NoRedirect
from check_api import USER_AGENT

URL = 'https://kamyabi.in/api/v1/admin/jobs?status='
TARGETS = {'powergrid-engineer-trainee-2027', 'ongc-apprentice-2026'}
FIELDS = ('jobId', 'job_id', 'title', 'verificationStatus', 'lastDate',
          'applicationStartDate', 'applicationLastDate', 'officialNotificationUrl',
          'sourceUrl', 'urlVerified', 'verified', 'vacancyCount')


def inspect(key, opener=None):
    opener = opener or build_opener(NoRedirect)
    if not key or any(char in key for char in '\r\n'):
        raise ValueError('Admin credential unavailable')
    found = []
    for status in ('approved', 'pending', 'rejected'):
        req = Request(URL + status, method='GET', headers={
            'X-Api-Key': key, 'Accept': 'application/json', 'User-Agent': USER_AGENT})
        with opener.open(req, timeout=30) as response:
            if response.status != 200 or 'json' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Unexpected admin response; no write attempted')
            body = json.loads(response.read(3_000_001))
        if not isinstance(body, dict) or not isinstance(body.get('jobs'), list):
            raise ValueError('Admin response missing jobs array')
        for job in body['jobs']:
            if not isinstance(job, dict):
                continue
            job_id = job.get('jobId') or job.get('job_id')
            if job_id in TARGETS:
                found.append({'queried_status': status,
                              'fields': {k: job[k] for k in FIELDS if k in job}})
    return {'targets': sorted(TARGETS), 'records': found, 'writes_attempted': 0}


if __name__ == '__main__':
    result = inspect(os.environ.get('KAMYABI_ADMIN_API_KEY', ''))
    print(json.dumps(result, indent=2, default=str))
