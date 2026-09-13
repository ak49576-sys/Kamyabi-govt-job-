"""Compare public official-site reachability without bypassing TLS or access controls."""
import json
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TARGETS = {
    'UPSC advertisements': 'https://www.upsc.gov.in/recruitment/recruitment-advertisement',
    'UPSC updates': 'https://www.upsc.gov.in/whats-new',
    'RPSC advertisements': 'https://rpsc.rajasthan.gov.in/advertisements',
    'RSSB advertisements': 'https://rssb.rajasthan.gov.in/advertisements',
    'Rajasthan recruitment portal': 'https://www.recruitment.rajasthan.gov.in/',
    'RSSB legacy site (archival; not current coverage)': 'https://rsmssb.rajasthan.gov.in/',
}


def probe(item):
    name, url = item
    try:
        result = subprocess.run([
            'curl', '--ipv4', '--silent', '--show-error', '--location',
            '--proto', '=https', '--proto-redir', '=https',
            '--connect-timeout', '8', '--max-time', '20',
            '--user-agent', 'Mozilla/5.0 (compatible; KamyabiRecruitmentMonitor/1.1; +https://kamyabi.in)',
            '--output', 'NUL' if platform.system() == 'Windows' else '/dev/null',
            '--write-out', '%{http_code}|%{url_effective}|%{remote_ip}|%{time_total}', url,
        ], capture_output=True, text=True, timeout=25)
        return {'name': name, 'url': url, 'curl_exit': result.returncode,
                'http_final_url_ip_seconds': result.stdout.strip(), 'error': result.stderr.strip(),
                'note': 'Reachability only; HTTP 200 does not prove current notice extraction.'}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'name': name, 'url': url, 'error': type(error).__name__ + ': ' + str(error)}


def main():
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(probe, TARGETS.items()))
    report = {'platform': platform.system(), 'targets': results,
              'note': 'Diagnostic completed. Site failures remain visible in this report; no jobs collected or submitted.'}
    Path('diagnostics').mkdir(exist_ok=True)
    Path('diagnostics/access.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
