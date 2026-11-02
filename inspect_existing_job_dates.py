"""Read-only inspection of two existing Kamyabi records before correcting deadlines."""
import json
import os
from urllib.request import Request, build_opener

from api_http import NoRedirect
from check_api import USER_AGENT

URL = 'https://kamyabi.in/api/v1/admin/jobs?status='
TARGETS = {'powergrid-engineer-trainee-2027', 'ongc-apprentice-2026'}
FIELDS = ('jobId', 'job_id', 'title', 'verificationStatus', 'verification_status',
          'lastDate', 'last_date', 'applicationStartDate', 'application_start_date',
          'applicationLastDate', 'application_last_date', 'officialNotificationUrl',
          'official_notification_url', 'sourceUrl', 'source_url', 'urlVerified',
          'url_verified', 'verified', 'vacancyCount', 'vacancy_count')


def inspect(key, opener=None):
    opener = opener or build_opener(NoRedirect)
    if not key or any(char in key for char in '\r\n'):
        raise ValueError('Admin credential unavailable')
    found = []
    listing = []
    for status in ('approved', 'pending', 'rejected'):
        offset = 0
        while True:
            req = Request(URL + status + '&limit=100&offset=' + str(offset), method='GET', headers={
                'X-Api-Key': key, 'Accept': 'application/json', 'User-Agent': USER_AGENT})
            with opener.open(req, timeout=30) as response:
                if response.status != 200 or 'json' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Unexpected admin response; no write attempted')
                body = json.loads(response.read(3_000_001))
            if not isinstance(body, dict) or not isinstance(body.get('jobs'), list):
                raise ValueError('Admin response missing jobs array')
            rows = body['jobs']
            total = body.get('total')
            if type(total) is not int or total < 0 or total > 2000:
                raise ValueError('Unexpected admin pagination total')
            listing.append({'status': status, 'offset': offset,
                            'returned_jobs': len(rows), 'total_jobs': total,
                            'response_keys': sorted(body.keys())})
            for job in rows:
                if not isinstance(job, dict):
                    continue
                job_id = job.get('jobId') or job.get('job_id')
                if job_id in TARGETS or ('POWERGRID' in str(job.get('title', '')).upper() and '2027' in str(job.get('title', ''))):
                    found.append({'queried_status': status,
                                  'fields': {k: job[k] for k in FIELDS if k in job}})
            offset += len(rows)
            if offset >= total:
                break
            if not rows:
                raise ValueError('Pagination stopped early; no write attempted')
    return {'targets': sorted(TARGETS), 'records': found, 'listing': listing,
            'writes_attempted': 0}


if __name__ == '__main__':
    result = inspect(os.environ.get('KAMYABI_ADMIN_API_KEY', ''))
    print(json.dumps(result, indent=2, default=str))
