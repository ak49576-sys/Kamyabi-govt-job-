# Kamyabi.in official recruitment monitor

A dependency-free Python starter for daily checks of IBPS, UPSC, RPSC and RSSB official pages, plus supplementary vacancy cards from the Rajasthan Recruitment Portal. It collects candidate notification links into CSV/JSON and reports source errors explicitly. It does not publish jobs to Kamyabi.in.

## Daily operation

Open **Actions → Daily official recruitment check → Run workflow** for a manual check. Scheduled runs are configured for **08:00 IST daily** (02:30 UTC); GitHub may delay scheduled runs. The first code push also runs a check.

Open the completed run, read its summary, and download **recruitment-report**. `notices.csv` contains links for the freelancer to review; `report.json` shows coverage and failures. Reports are retained for 30 days. A failed source or zero matching links makes the run fail visibly while preserving available reports.

## Local use

Requires Python 3.10 or later and curl; no pip installation or API key is needed. Fetching uses IPv4 and the system certificate store, with certificate validation enabled. Up to four sources run concurrently, with one request at a time per source. Official fallback pages are tried when configured; all failed attempts remain in the report.

```sh
python -m unittest -v test_monitor.py
python monitor.py
```

## Review each candidate

Links may include old advertisements, results, corrigenda and general recruitment navigation. This is a daily snapshot with stable link IDs, not a list of newly released or currently open vacancies. Duplicates are removed per source within the run; historical change tracking is not yet implemented. Changes to a PDF at the same URL are not detected.

Read the official notification and confirm the post, vacancy count, eligibility, dates, fee and application link before creating a Kamyabi job. Never infer missing values. Check each source's access terms and avoid excessive requests.

Some government sites use JavaScript or block automated requests. This starter reads server HTML only. An empty result means **needs attention**, not “no vacancies”. Site-specific adapters and PDF extraction are future extensions.

## Add sources

Edit `sources.json` with the official page URL, explicitly allowed official domains and a case-insensitive link matching pattern. Test the page against its actual HTML before relying on it. Configured coverage is four body sites plus the supplementary Rajasthan portal, not all government/PSU employers. Reachable sources are listed in the latest live verification.

## Connect publication later

The exact Kamyabi add-jobs endpoint, authentication header, request schema and success response must be confirmed with the site developer before implementing submission. Store credentials only in GitHub Actions secrets. No live publication integration is configured in this starter.

## Official source pages

- IBPS: https://www.ibps.in/index.php/crp-updates/
- UPSC: https://www.upsc.gov.in/recruitment/recruitment-advertisement
- RPSC: https://rpsc.rajasthan.gov.in/advertisements
- RSSB: https://rssb.rajasthan.gov.in/advertisements

## Run from your hosting server

See [AIRO-HANDOFF.md](AIRO-HANDOFF.md) for the access test, cron setup and exact publication API details required. On a compatible Linux server, use `bash run-server.sh`; it checks prerequisites, prevents overlapping runs and preserves dated reports. This option is prepared but has not been tested on your hosting server. IBPS collection now works; the other three sources still fail from GitHub-hosted runners. See the latest live verification below.

## Confirmed API contract (Airo report, 2026-09-13)

The supplied host audit identifies `POST https://kamyabi.in/api/v1/add-jobs`, an array payload, `X-Api-Key` authentication and deduplication by `job_id`. It reports inserted records are pending and must be approved in `/admin/jobs`. This is host-audit evidence, not a live submission test from this repository.

`submit_jobs.py` validates an explicit `{"reviewed":true,"jobs":[...]}` document. The jobs require the API's required fields plus a reviewed HTTPS official notification URL. It rejects expired/sentinel deadlines, duplicate IDs and mismatched application dates. A review declaration does not itself verify official content; the editor must do that review.

Local preview, with no network write:

```sh
python3 submit_jobs.py --file /path/to/reviewed-jobs.json
```

To stage records after review, set `KAMYABI_API_KEY` in the secret store and use `--submit`. The key is never required for preview. The client does not follow redirects or automatically retry writes. On a connection error, check pending rows before repeating the request.

GitHub option: add the key as repository Actions secret `KAMYABI_API_KEY`, then open **Actions → Stage reviewed Kamyabi jobs → Run workflow**. Paste the reviewed JSON, leaving **submit=false** for the first preview. Set **submit=true** only when ready to send real reviewed records. No automatic daily submission is configured. Successful API counts confirm insertion/skipping; public publication still needs separate verification after admin approval.

The IBPS intermediate is now bundled from the official GlobalSign source; see [certs/README.md](certs/README.md). Python, curl and openssl are required for IBPS checks. The host audit reproduced all four collection failures; changing runner alone is not a verified fix. A 403 or timeout does not by itself prove the specific cause is geographic blocking.

## Latest live verification — 2026-09-13 22:06 UTC

[Run 34785741342](https://github.com/ak49576-sys/Kamyabi-govt-job-/actions/runs/34785741342), commit 37808b9f42e27693013d2107a1a483c6bc8879e9: 15 tests passed. IBPS returned 23 candidate links after the certificate repair. UPSC returned 403/timeout; RPSC and RSSB timed out. The overall run remains failed to flag incomplete coverage, and the recruitment-report artifact was saved. Zero jobs submitted or published. The new staging client has been tested with mocked API responses only; real credentials and insertion/pending state remain unverified.

## Supplementary Rajasthan collection — 2026-09-13 22:23 UTC

[Run 34786615567](https://github.com/ak49576-sys/Kamyabi-govt-job-/actions/runs/34786615567), commit c562f5f6cbdabdc34b36a764e1e6deee03e06954: 17 tests passed; 25 candidate records collected (23 IBPS notice links and 2 vacancy cards from the canonical https://recruitment.rajasthan.gov.in/ portal). Direct UPSC, RPSC and RSSB sources still fail, so the overall workflow flags incomplete coverage while saving the report. Zero jobs submitted/published.

The portal is a separate supplementary source, not proof of complete RPSC/RSSB coverage. It reads h6 vacancy headings, body labels and displayed deadlines, and removes repeated cards. Its record URLs point to the listing page, not individual official notifications; editors must obtain and review the notification before using the staging API. CSV now includes observed_deadline, recruiting_body and kind. candidate_records counts both link records and cards; candidate_links counts only notice-link records.

[Diagnostic run 34786438750](https://github.com/ak49576-sys/Kamyabi-govt-job-/actions/runs/34786438750) compared Linux/Windows: both received UPSC 403 and RPSC/RSSB timeouts. The www Rajasthan portal address failed hostname validation on both; the canonical address without www works. The old RSSB site is archival and has additional TLS/redirect issues, so it was not substituted into current coverage. Diagnostic job success means probes completed, not that source access succeeded.

## Updated API deployment contract — 2026-09-14

The latest Airo report says IMPORT_API_KEY is now configured on hosting, X-Api-Key and X-Import-Key are accepted, and /api/v1/add-jobs now aliases the import handler. These host changes require publishing the site. The configured GitHub secret remains KAMYABI_API_KEY and must match hosting's IMPORT_API_KEY.

Credential checking now uses GET https://kamyabi.in/api/v1/status with X-Api-Key. Only HTTP 200 plus JSON {"ok":true,"auth":"api_key"} confirms authentication. It sends no record payload. The older empty-batch POST diagnostic is historical and no longer used.

Submissions now use {"jobs":[...]} and must pass the read-only credential check before any POST. The latest report says the import handler upserts jobs into pending review. This supersedes the earlier duplicate-skip description: review existing job IDs before submitting because upserts may update existing records. No automatic retries are configured. The client accepts inserted/skipped counts and an optional updated count; the actual published response schema still needs a live contract check. Unexpected counts are reported as an unknown submission result, not success; check admin rows before repeating.

Next: publish the Airo site, then rerun Verify Kamyabi API secret on the current revision. A preview sign-in gate or absence of import errors does not prove authenticated live API access. After successful status verification, preview real reviewed jobs before staging them; verify pending state at /admin/jobs and public URLs separately after approval.
