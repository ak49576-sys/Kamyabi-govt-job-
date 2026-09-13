# Airo handoff: enable Kamyabi recruitment collection and publication

Repository: https://github.com/ak49576-sys/Kamyabi-govt-job-

## Current verified status

The GitHub-hosted check ran, but collected zero links. IBPS failed certificate verification, UPSC returned 403, and the Rajasthan sources timed out. Tests passed. No live publication exists. An alternate server may have different access; it must be tested before claiming a fix.

## Request for Airo / hosting support

Please check whether the current hosting plan supports a background Python 3.10+ process, curl, flock, SSH/file access and cron. If it does, place this repository outside the public web directory and run:

```sh
bash run-server.sh
```

Inspect the generated reports/YYYYMMDDTHHMMSSZ/report.json, notices.csv and run.log. Return actual per-source counts, errors and the tested server region. Keep certificate validation enabled. Do not fabricate jobs or treat zero results as proof of no vacancies.

If a source fails, investigate its server reachability, official site's TLS chain or JavaScript rendering as appropriate. Fix certificate-chain problems using verified issuer certificates/system trust updates; do not use insecure TLS flags.

If the hosting plan does not support these tools, report that limitation and the available background-task features before proposing another host.

After a successful manual test, configure a daily cron task. For a host whose cron timezone is UTC, 02:30 UTC is 08:00 IST:

```cron
30 2 * * * /bin/bash /ABSOLUTE/PATH/TO/REPO/run-server.sh >> /ABSOLUTE/PATH/TO/REPO/cron.log 2>&1
```

Replace both paths and confirm the actual cron timezone. Set a report-retention policy appropriate for the server. The wrapper prevents overlapping runs and preserves dated reports. It does not automatically update code from GitHub; deploy reviewed changes.

## Publication API contract required

Provide documentation or existing implementation evidence for:
1. The exact live add-jobs URL and HTTP method.
2. The authentication header name and scheme; do not include the secret value.
3. Required fields, types, allowed values and a complete sample request using placeholders.
4. Success response and how to distinguish accepted, staged and publicly published jobs.
5. Duplicate/update behavior for job_id and how corrections are handled.
6. Rate limits, retry rules and whether a failed request can safely be repeated.
7. A read-only endpoint or final public URL that proves publication.
8. A staging/dry-run method for testing before live writes.

Store the actual API key in GitHub Actions secrets or the server's secret store. Never put it in a commit, report, public file or chat reply.

Do not publish any jobs during this diagnostic. Collected links remain candidates requiring verification of official notification, vacancies, eligibility and dates.
