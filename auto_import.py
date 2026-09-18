"""Scheduled delivery of explicitly reviewed records; never promotes raw notices."""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

from api_http import NoRedirect
from check_api import USER_AGENT
from submit_jobs import send_jobs, validate_document, valid_date

PUBLIC_URL = 'https://kamyabi.in/api/v1/jobs'
# Explicit source/body binding. Adding an employer requires an adapter/domain review.
SOURCES = {'IBPS': {'ibps.in'}, 'RITES Limited': {'rites.com'}}


def load_queue(root, today):
    jobs, expired, seen = [], [], set()
    for path in sorted(root.glob('reviewed-*-jobs.json')):
        doc = json.loads(path.read_text())
        if doc.get('reviewed') is not True or not isinstance(doc.get('jobs'), list):
            raise ValueError(f'{path.name}: explicit review and jobs array required')
        for job in doc['jobs']:
            deadline = valid_date(job.get('last_date'))
            if deadline < today:
                expired.append(job.get('job_id'))
                continue
            clean = validate_document({'reviewed': True, 'jobs': [job]}, today)[0]
            if clean['job_id'] in seen:
                raise ValueError('Duplicate job_id across reviewed files')
            seen.add(clean['job_id'])
            domains = SOURCES.get(clean.get('recruiting_body'), set())
            for field in ('source_url', 'official_notification_url'):
                host = (urlparse(clean[field]).hostname or '').lower()
                if not any(host == d or host.endswith('.' + d) for d in domains):
                    raise ValueError('Unconfigured employer or nonofficial source domain')
            jobs.append(clean)
    return jobs, expired


def fetch_public():
    request = Request(PUBLIC_URL, headers={'User-Agent': USER_AGENT, 'Cache-Control': 'no-cache'})
    with build_opener(NoRedirect).open(request, timeout=45) as response:
        if response.status != 200:
            raise ValueError('Public jobs API did not return HTTP 200')
        document = json.loads(response.read(5_000_001))
    if not isinstance(document, dict) or not isinstance(document.get('jobs'), list):
        raise ValueError('Unexpected public jobs API schema')
    return {j['job_id']: j for j in document['jobs'] if isinstance(j, dict) and isinstance(j.get('job_id'), str)}


def matches(job, public):
    row = public.get(job['job_id'])
    return bool(row) and all(row.get(k) == v for k, v in job.items())


def deliver(jobs, submit, key, report, fetch=fetch_public, send=send_jobs):
    public = fetch()  # Read failures must prevent writes.
    changed = [j for j in jobs if not matches(j, public)]
    report.update(unchanged=len(jobs)-len(changed), to_submit=[j['job_id'] for j in changed])
    if submit and changed:
        if not key or any(c in key for c in '\r\n'):
            raise ValueError('KAMYABI_API_KEY secret is required')
        # No retries: an interrupted POST may already have been applied.
        report['submission_attempted'] = True
        results = []
        for offset in range(0, len(changed), 100):
            results.append(send(changed[offset:offset+100], key))
        report['responses'] = results
        report['submitted'] = len(changed)
        public = fetch()
    if submit:
        missing = [j['job_id'] for j in jobs if not matches(j, public)]
        report['public_mismatch'] = missing
        if missing:
            raise ValueError('Imported records not visible with expected fields; check /admin/jobs approval and API filters')
        report['publication_status'] = 'verified in public API'


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--submit', action='store_true')
    args = cli.parse_args()
    report = {'mode': 'live' if args.submit else 'preview', 'submitted': 0, 'publication_status': 'not verified'}
    try:
        today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        jobs, expired = load_queue(Path('.'), today)
        report.update(eligible=len(jobs), expired=expired)
        if jobs:
            deliver(jobs, args.submit, os.environ.get('KAMYABI_API_KEY', ''), report)
        else:
            report['note'] = 'No current reviewed jobs; notice collection is separate'
        report['status'] = 'ok'
    except Exception as error:
        report['status'] = 'error'
        # Network errors may contain request information; never log secrets/bodies.
        report['error'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    output = Path('output/automatic-import.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    print(output.read_text())
    return report['status'] != 'ok'


if __name__ == '__main__':
    raise SystemExit(main())
