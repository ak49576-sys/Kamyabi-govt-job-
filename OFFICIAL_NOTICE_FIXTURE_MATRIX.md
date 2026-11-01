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
