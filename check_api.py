"""Verify credentials through the read-only status endpoint."""
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from api_http import NoRedirect

STATUS_ENDPOINT = 'https://kamyabi.in/api/v1/status'
USER_AGENT = 'KamyabiJobImporter/1.0 (+https://kamyabi.in)'


def response_details(headers, body):
    server = str(headers.get('Server', '')).lower() if headers else ''
    content_type = str(headers.get('Content-Type', '')).lower() if headers else ''
    cf_ray = str(headers.get('CF-Ray', '')) if headers else ''
    text = body.decode('utf-8', errors='replace').lower()
    details = {'server_mentions_cloudflare': 'cloudflare' in server,
               'response_type': 'json' if 'json' in content_type else 'html' if 'html' in content_type else 'other',
               'challenge_indicated': any(marker in text for marker in ('challenge-platform', 'cf-chl-', 'just a moment')),
               'body_mentions_key_error': any(marker in text for marker in ('invalid api key', 'invalid import key', 'missing api key', 'api key required'))}
    if re.fullmatch(r'[A-Za-z0-9-]{1,80}', cf_ray):
        details['cf_ray'] = cf_ray
    return details


def check(key):
    report = {'status_endpoint': STATUS_ENDPOINT, 'secret_present': bool(key),
              'authentication_verified': False, 'records_sent': 0, 'inserted': 0}
    if not key or any(c in key for c in '\r\n'):
        report['result'] = 'Missing or invalid KAMYABI_API_KEY secret'
        return report
    request = Request(STATUS_ENDPOINT, method='GET',
                      headers={'Accept': 'application/json', 'User-Agent': USER_AGENT, 'X-Api-Key': key})
    try:
        with build_opener(NoRedirect).open(request, timeout=30) as response:
            report['http_status'] = response.status
            body = response.read(100_001)
            report.update(response_details(response.headers, body))
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            report['result'] = 'Response was not API JSON; authentication is unverified'
            return report
        if (report['http_status'] == 200 and isinstance(payload, dict)
                and payload.get('ok') is True and payload.get('auth') == 'api_key'):
            report['authentication_verified'] = True
            report['result'] = 'Read-only status endpoint confirmed API-key authentication'
        else:
            report['result'] = 'Response did not match the expected authenticated status contract; investigate before submission'
    except HTTPError as error:
        report['http_status'] = error.code
        body = error.read(100_001) if error.fp is not None else b''
        report.update(response_details(error.headers, body))
        report['result'] = ('API rejected authentication' if error.code == 401 else
                            'API rejected the request; authentication remains unverified')
    except (URLError, OSError, TimeoutError):
        report['result'] = 'Connection failed; authentication remains unverified'
    return report


def main():
    report = check(os.environ.get('KAMYABI_API_KEY', ''))
    output = Path('output/api-check.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    summary = json.dumps(report, indent=2)
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as file:
            file.write('## Kamyabi API check\n\n```json\n' + summary + '\n```\n')
    return 0 if report['authentication_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
