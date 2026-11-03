"""Verify that newly approved job IDs appear in Kamyabi's public jobs API."""
import json
import time
from pathlib import Path
from auto_import import fetch_public


def verify(approved_ids, fetch=fetch_public, wait=time.sleep, attempts=3):
    approved = list(dict.fromkeys(approved_ids))
    if not approved:
        return {'status': 'ok', 'approved': [], 'visible': [], 'missing': [],
                'note': 'No new approvals to verify'}
    missing = approved
    for attempt in range(attempts):
        public = fetch()
        missing = [job_id for job_id in approved if job_id not in public]
        if not missing:
            break
        if attempt + 1 < attempts:
            wait(2)
    return {'status': 'ok' if not missing else 'missing_public_jobs',
            'approved': approved, 'visible': [job_id for job_id in approved if job_id not in missing],
            'missing': missing}


def main():
    approval = json.loads(Path('output/automatic-publishing.json').read_text())
    if approval.get('status') != 'ok':
        raise ValueError('Approval did not complete successfully')
    report = verify(approval.get('approved', []))
    path = Path('output/verified-publications.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if report['missing']:
        print('::error::Approved job IDs missing from the public jobs API')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
