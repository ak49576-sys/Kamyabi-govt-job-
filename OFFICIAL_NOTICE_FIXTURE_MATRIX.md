# Official recruitment notice verification — adversarial fixture matrix

Date: 2026-11-01. **Design/test fixtures only. Nothing deployed.**

## Test fixture contract

Each fixture must contain: candidate job ID, recruiting body, advertisement ID, post and recruitment cycle, expected start/end dates, fetched URL/final redirect URL, a synthetic PDF or HTML response, extracted text, source list/current-status response, SHA-256, retrieval timestamp, and full known-inventory snapshot. **Never use arbitrary scraped booleans as verification evidence.** Store only synthetic data in tests.

| Case | Simulated source/evidence | Expected result | Required assertion |
|---|---|---|---|
| F01 | Official issued PDF matching issuer, advertisement, post and all dates, valid current listing, complete inventory, no duplicate | Eligible in **dry run only** | No DB publication write |
| F02 | HTTPS page on attacker-controlled host copying government logo | HOLD | Host allowlist and final host check |
| F03 | Government landing page, no individual advertisement PDF | HOLD | Specific notice required |
| F04 | HTTP 302 from official domain to unrelated external host | HOLD | Redirect target validation |
| F05 | Same PDF filename but changed bytes/ad number | HOLD | Revision/hash and content mismatch |
| F06 | Image-only/scanned PDF without reliable extracted text | HOLD | Incomplete extraction requires review |
| F07 | Forged PDF metadata says issuer but body text shows different organisation | HOLD | Parsed content and issuer mismatch |
| F08 | Correct issuer, wrong advertisement number | HOLD | Exact ad number mismatch |
| F09 | Correct ad number but different post within same multi-post notice | HOLD until post mapping verified | Do not collapse legitimate posts |
| F10 | Dates in scraped job differ from dates in notice | HOLD | Never silently choose scraped dates |
| F11 | Extension/corrigendum changes closing date | HOLD until latest amendment reconciled | Link current status and revision chain |
| F12 | Recruitment withdrawn/cancelled at official source | HOLD | Withdrawal check |
| F13 | Deadline expired as of India date | HOLD | Timezone-aware cutoff |
| F14 | Notice URL returns 404, 403 or timeout | HOLD | Missing evidence cannot pass |
| F15 | Truncated or oversized PDF, invalid magic/content type | HOLD | Bounded fetch and parser failure |
| F16 | Source URL resolves to localhost, private IP or cloud metadata by DNS/redirect | HOLD | SSRF guards, including DNS rebinding |
| F17 | Valid notice but pending record with same canonical issuer/ad/cycle/post exists | HOLD | Pending included in inventory |
| F18 | Same canonical identity already approved with a different slug | HOLD | Idempotency and duplicate preservation |
| F19 | Rejected record with same canonical identity | HOLD | Human adjudication retained |
| F20 | Same PDF legitimately lists distinct posts | Hold for review unless post identities uniquely verified | URL alone not dedupe key |
| F21 | Same ad number from different agencies or cycles | Distinct candidates, each needs verification | Composite identity |
| F22 | Inventory pagination fails after first page | HOLD | Incomplete inventory is not clean |
| F23 | Two concurrent imports of identical canonical identity | At most one staging identity | DB uniqueness / transactional test |
| F24 | Two concurrent approval attempts | At most one approval event | Atomic conditional transition and lock |
| F25 | A job is edited after its evidence hash was created | HOLD | Evidence tied to exact job revision |
| F26 | Legacy url_verified=true only because link looked like .pdf | HOLD | Legacy flag never sufficient |
| F27 | Importer claims fullyVerified=true without trusted verifier record | HOLD | Ignore inbound trust flags |
| F28 | Official site displays CAPTCHA/JS-only content, proof unavailable | HOLD | No bypass by hostname alone |
| F29 | Missing date, vacancy count ambiguous, or disagreement on number of posts | HOLD | Human review required |
| F30 | Complete trusted evidence but transaction lock not acquired | HOLD | No check-then-insert race |

## Trust and execution rules

- Fixtures use fake domains/content or controlled local mocks; do **not** run live production approval/import POST.
- Fetcher must constrain redirects, resolve and check all IPs, reject private/reserved addresses, cap download size and duration, verify MIME/signature, and never forward internal credentials across redirects.
- PDF extractor should record extraction confidence and selected text spans, not rely on filename or extension.
- A provenance record should include verified official source, document hash, checked-at time, ruleset version and exact candidate revision.
- Before any approval, compare fresh official correction/withdrawal state and recheck canonical duplicate identity in one transaction.
- Any exception, missing field, stale evidence, failed DB read, ambiguous mapping, or conflict => pending manual review.
- Promotion must be a separate reviewed feature flag defaulting OFF; dry-run output cannot make a public write.
- Live enablement requires owner approval after staging tests and rollback plan.

## Execution status

This matrix defines future acceptance tests. **It has not been executed.** Previous selected isolated suites passed 75 tests, but do not verify this full matrix. Missing Airo runtime/database config blocks true end-to-end validation. No live publication or Airo credits used.

## Initial executable subset (2026-11-01)

Added branch-only Python files `safety_prototypes/official_notice_matcher.py` and `safety_prototypes/test_official_notice_matcher.py`. Ran `python3 -m unittest -v test_official_notice_matcher.py` against the identical local source: **13 tests passed**. Cases cover fake/unconfirmed official source, unreadable notice, wrong issuer/ad/post, boundary match, withdrawal/correction unknown, expired/reversed dates and blank advertisement. The evaluator **always returns HOLD**, including on matching text, because structured notice-date extraction and trustworthy issuer/document fetch have not been implemented. These are intentionally negative/fail-closed unit checks, **not** official-PDF parsing or completed acceptance of the 30-case matrix. The earlier 75 tests were run separately in a previous temporary Airo environment and are not a single combined 88-test run. No production code, live jobs or Airo credits were changed.

## Offline PDF extraction prototype (2026-11-01)

Added `safety_prototypes/official_notice_pdf.py` and `safety_prototypes/test_official_notice_pdf.py` to the safety branch. The module uses `pypdf` on provided bytes (no network), checks PDF magic, input size, page count, encryption/parser errors, insufficient extracted text and records a SHA-256 fingerprint. It extracts only uniquely labelled start/end dates in ISO or DD/MM/YYYY format and holds conflicting/missing/impossible/reversed dates; other date expressions require manual review. Test fixtures are synthetic PDFs generated in memory by `reportlab`. **14 new tests passed**, and the combined standalone Python prototype suite passed **27/27 tests**. This is separate from the earlier isolated Airo Vitest suite of 75; they are not one continuous CI run.

Limitations: this is proof-of-concept parsing of supplied bytes, not trusted official-site retrieval. No SSRF-safe fetcher, PDF OCR for scanned documents, issuer authenticity verification, correction/withdrawal source checks, concurrency-safe database identity or production route integration exists. PDF parser resource/decompression limits need security hardening and staging tests. The checker remains fail-closed and does not approve or publish anything.

## Official-host URL/DNS preflight prototype (2026-11-01)

Added `safety_prototypes/official_source_url_policy.py` and `safety_prototypes/test_official_source_url_policy.py` to the unmerged safety branch. Twenty new **offline** tests cover registered-host suffix boundaries, exact/subdomains, HTTPS-only, URL credentials/fragments/ports, IP literal rejection, public-vs-private/mixed DNS results, DNS failure, redirect limits, off-domain redirects and private-IP redirect answers. All three standalone Python suites passed **47/47 tests** in one local run (13 notice matcher + 14 synthetic PDF extraction + 20 URL preflight). DNS answers were injected; no live DNS or HTTP request occurred.

**Not production ready:** preflight alone is vulnerable to DNS rebinding if the HTTP client subsequently resolves the hostname again; a real fetcher must pin the validated IP to the outbound connection while preserving TLS hostname validation, recheck every redirect, limit streaming bytes/time/decompression and defend metadata/loopback/internal networks. The current code has no networking and never publishes. No Airo credits, live changes or merges.

## Transactional duplicate-identity prototype (2026-11-01)

Added `safety_prototypes/atomic_job_identity.py` and `safety_prototypes/test_atomic_job_identity.py` to the unmerged branch. The SQLite-only dry-run ledger uses a length-prefixed composite identity (issuer + advertisement + cycle + post), one uniqueness constraint on identity and one on canonical job ID, and `BEGIN IMMEDIATE` to serialize simultaneous reservations. It returns only `reserved_dry_run`, `already_reserved`, or a hold reason; there is no publication status or publish operation. **12 new tests passed**, including a two-thread simultaneous reservation test in a disposable local SQLite database: exactly one reservation and one duplicate hold. All four standalone Python suites passed **59/59 tests** in one run.

Limitations: this is **SQLite, not Kamyabi's MySQL**. It does not verify official evidence, retrieve actual production inventory, handle production migrations, reconcile existing duplicates, or update the admin route. A MySQL staging integration test with concurrent import/approval transactions and reviewed unique-key migration remains mandatory. All live publishing remains off. No Airo credits or live writes.
