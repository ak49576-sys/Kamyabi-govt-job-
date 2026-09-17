"""Validate reviewed records and optionally send them to Kamyabi's pending-job API."""
import argparse
import json
import os
import re
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener
from api_http import NoRedirect
from check_api import USER_AGENT, check as verify_api

ENDPOINT = 'https://kamyabi.in/api/v1/add-jobs'
LIMITS = {'job_id': 255, 'title': 500, 'department': 500, 'qualification': 1000,
          'state_or_central': 255, 'source_url': 2048}
OPTIONAL = {'official_notification_url', 'application_start_date',
            'application_last_date', 'vacancy_count', 'recruiting_body'}


def valid_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    parsed = urlparse(value)
    return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Dates must be YYYY-MM-DD')
    return date.fromisoformat(value)


def validate_document(document, today=None):
    today = today or date.today()
    if not isinstance(document, dict) or document.get('reviewed') is not True:
        raise ValueError('Input must explicitly declare reviewed=true after official-notification review')
    jobs = document.get('jobs')
    if not isinstance(jobs, list) or not jobs or len(jobs) > 100:
        raise ValueError('Provide 1–100 reviewed jobs')
    clean, seen = [], set()
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError('Each job must be an object')
        unknown = set(job) - set(LIMITS) - OPTIONAL - {'last_date'}
        if unknown:
            raise ValueError('Unexpected job fields: ' + ', '.join(sorted(unknown)))
        for key, limit in LIMITS.items():
            value = job.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f'{key} must be a nonempty string of at most {limit} characters')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', job['job_id']):
            raise ValueError('job_id must be a lowercase slug')
        if job['job_id'] in seen:
            raise ValueError('Duplicate job_id in input')
        seen.add(job['job_id'])
        if not valid_url(job['source_url']):
            raise ValueError('source_url must be HTTPS')
        if not valid_url(job.get('official_notification_url')):
            raise ValueError('Provide the reviewed official_notification_url as HTTPS')
        end = valid_date(job.get('last_date'))
        if end < today or end.year > today.year + 2:
            raise ValueError('last_date must be a genuine current deadline; no expired or sentinel dates')
        if 'application_last_date' in job and valid_date(job['application_last_date']) != end:
            raise ValueError('application_last_date must match last_date')
        if 'application_start_date' in job and valid_date(job['application_start_date']) > end:
            raise ValueError('Application start is after the deadline')
        if 'vacancy_count' in job and (type(job['vacancy_count']) is not int or job['vacancy_count'] < 0):
            raise ValueError('vacancy_count must be a nonnegative integer')
        if 'recruiting_body' in job and (not isinstance(job['recruiting_body'], str) or not job['recruiting_body'].strip()):
            raise ValueError('recruiting_body must be a nonempty string')
        clean.append(dict(job))
    return clean


def send_jobs(jobs, key):
    if not verify_api(key)['authentication_verified']:
        raise ValueError('Read-only API-key verification failed; no jobs sent')
    request = Request(ENDPOINT, data=json.dumps(jobs).encode(), method='POST',
                      headers={'Content-Type': 'application/json', 'User-Agent': USER_AGENT, 'X-Api-Key': key})
    with build_opener(NoRedirect).open(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError('Unexpected API status; check pending rows before retrying')
        result = json.loads(response.read(100_001))
    if not isinstance(result, dict) or any(type(result.get(k)) is not int or result[k] < 0
                                          for k in ('inserted', 'skipped')):
        raise ValueError('Unexpected API response; check pending rows before retrying')
    updated = result.get('updated', 0)
    if type(updated) is not int or updated < 0:
        raise ValueError('Unexpected update count; check pending rows before retrying')
    if result['inserted'] + updated + result['skipped'] != len(jobs):
        raise ValueError('API counts do not match input; check pending rows before retrying')
    return {'inserted': result['inserted'], 'updated': updated, 'skipped': result['skipped'],
            'publication_status': 'not verified; review /admin/jobs',
            'expected_insert_status': 'pending, according to the supplied API contract'}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--file', required=True, help='JSON document with reviewed=true and jobs array')
    cli.add_argument('--submit', action='store_true', help='Send reviewed jobs to the pending-job API')
    cli.add_argument('--output', default='output/submission.json')
    args = cli.parse_args()
    try:
        jobs = validate_document(json.loads(Path(args.file).read_text()))
        if args.submit:
            key = os.environ.get('KAMYABI_API_KEY', '')
            if not key or any(c in key for c in '\r\n'):
                raise ValueError('KAMYABI_API_KEY must be set in the secret store')
            result = send_jobs(jobs, key)
        else:
            result = {'mode': 'local preview', 'validated_jobs': len(jobs), 'submitted': 0,
                      'job_ids': [job['job_id'] for job in jobs]}
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        return 0
    except HTTPError as error:
        print(f'API returned HTTP {error.code}; no response body or credentials logged. Check pending rows before retrying.')
    except URLError:
        print('Connection failed; submission outcome may be unknown. Check pending rows before retrying.')
    except (ValueError, OSError) as error:
        print(f'Error: {error}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
