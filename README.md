# Kamyabi.in official recruitment monitor

A dependency-free Python starter for daily checks of IBPS, UPSC, RPSC and RSSB official pages. It collects candidate notification links into CSV/JSON and reports source errors explicitly. It does not publish jobs to Kamyabi.in.

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

Edit `sources.json` with the official page URL, explicitly allowed official domains and a case-insensitive link matching pattern. Test the page against its actual HTML before relying on it. Current coverage is four bodies, not all government/PSU employers.

## Connect publication later

The exact Kamyabi add-jobs endpoint, authentication header, request schema and success response must be confirmed with the site developer before implementing submission. Store credentials only in GitHub Actions secrets. No live publication integration is configured in this starter.

## Official source pages

- IBPS: https://www.ibps.in/index.php/crp-updates/
- UPSC: https://www.upsc.gov.in/recruitment/recruitment-advertisement
- RPSC: https://rpsc.rajasthan.gov.in/advertisements
- RSSB: https://rssb.rajasthan.gov.in/advertisements

## Run from your hosting server

See [AIRO-HANDOFF.md](AIRO-HANDOFF.md) for the access test, cron setup and exact publication API details required. On a compatible Linux server, use `bash run-server.sh`; it checks prerequisites, prevents overlapping runs and preserves dated reports. This option is prepared but has not been tested on your hosting server. Collection from GitHub-hosted runners is currently failing for all four sources.
