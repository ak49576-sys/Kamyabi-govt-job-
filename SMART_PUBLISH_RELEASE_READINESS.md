# Kamyabi.in smart publishing — release readiness and handoff

Date: 2026-11-01. **Release decision: NO-GO. Automatic publishing must remain disabled.**

## Relaxed four-check eligibility preview — 2026-11-01

**Implemented on the branch only:** the preview now accepts separately verified official HTML pages as well as PDFs, matches issuer/advertisement/post/deadline rather than demanding exact vacancy-count/qualification extracts, requires an open application window, independently verified government/PSU scope, and retains duplicate inventory checks. The independent `safety_prototypes/fast_track_review.py` adds issuer-domain/DNS preflight and a SQLite-only two-key reservation rehearsal. The existing dry-run workflow now tests the relaxed gate and the offline prototype workflow tests the low-level cases.

**36 focused local tests passed; no full GitHub CI or GoDaddy staging result has yet been established for this revision.** The source/retrieval flags in the read-only preview must be issued by a future trusted backend, never supplied by an Apify payload. The live Airo importer still has unsafe auto-approval paths, so **production publication and pending-only submission remain DISABLED**. See [RELAXED_SMART_PUBLISH_POLICY.md](RELAXED_SMART_PUBLISH_POLICY.md).

## Completed on isolated/unmerged safety branch

- Audited user-provided GoDaddy Airo project ZIP and identified unsafe auto-approval paths in `admin/apify-import/POST.ts`, `add-jobs/POST.ts`, and `admin/jobs/auto-verify/POST.ts`.
- Generated review-only source patch for those three routes, tested it in a disposable Airo export; did not deploy.
- Added Python fail-closed read-only official evidence gate and public/admin inventory diagnostics.
- Created offline official-source URL/DNS/redirect preflight, synthetic PDF extraction, notice-field/date matcher, review-only integrated rehearsal, SQLite atomic reservation and isolated MySQL 8 reservation tests.
- Verified GitHub Actions: [offline 70 tests passed, with the separate MySQL suite intentionally skipped](https://github.com/ak49576-sys/Kamyabi-govt-job-/actions/runs/41268375444) and [disposable MySQL 8 integration 8 tests passed](https://github.com/ak49576-sys/Kamyabi-govt-job-/actions/runs/41268169073). These are prototypes, not production approval tests.
- Preserved original live website, original ZIP and protected main deployment; used no Airo credits.

## Additional GitHub-only safety improvements (not production-validated)

- Batch review now holds malformed candidates and invalid batch containers instead of raising an exception.
- Every identifiable incoming candidate reserves its batch identity even when held for manual review, so a later duplicate cannot become dry-run eligible merely because the earlier record failed official evidence checks.
- Added focused regression tests for these cases and malformed official URLs. **22 smart publishing gate unit tests passed locally on the latest branch sources on 2026-11-01.** This does not substitute for the complete GitHub Actions suite or staging backend verification; the prior 70+8 CI pass counts predate these changes.
- A separate current-source in-memory rehearsal of the entire offline suite attempted 70 tests: 68 passed, 1 isolated MySQL test skipped (no disposable MySQL), and 1 SQLite concurrency test could not run because this executor forbids creation of its temporary database file. This does **not** establish a code failure or a full-suite pass; rerun in GitHub Actions with a writable temporary directory.
- All changes remain on the unmerged safety branch; the live service and its existing write workflows are unchanged.

## Confirmed production-side blockers

| Gate | Current state | Required for go-live |
|---|---|---|
| Airo import containment patch | Not deployed | Review/apply to staging, then deploy with rollback |
| Airo platform build/type check | Export lacks platform config/modules | Compile/test in real Airo runtime |
| Official PDF retrieval | Offline URL policy only; no pinned-IP TLS fetch | SSRF-safe actual fetch, redirect/IP pinning, size/time limits |
| PDF content and amendment evidence | Synthetic text fixtures only | Official issue/correction/withdrawal fetch and content evidence |
| Admin inventory | Exported API `total` is only page length; offset pagination has no stable snapshot and cannot prove a consistent inventory | Read-only, consistent snapshot or cursor-based inventory covering all relevant statuses and mutations |
| Duplicate transaction | Disposable MySQL table tested | Reviewed migration and existing-data reconciliation in Kamyabi staging MySQL |
| Manual approval | Live route still accepts weak URL/date evidence | Regression-test strict human verification, UI and state transition |
| Public feed regression | Not run against staging backend | Prove only explicit reviewed actions affect published feed |
| Feature flag/rollback | No production flag or rollback test | Default OFF, run dry-run, audit log, rollback drill |
| Owner go-live approval | Not requested | Ask only after ALL gates pass |

## Inventory-completeness finding (2026-11-01)

The exported `GET /api/v1/admin/jobs` returns `total: jobs.length` for each page and uses descending createdAt with limit/offset, without a unique tie-breaker, global count, stable snapshot or cursor. Concurrent imports and approvals can shift pages, so even enumerating all current-looking pages cannot prove there are no missing duplicates. The read-only inventory diagnostic was changed to return `inventory_complete: false` even after apparently successful page enumeration, and its tests were updated; those newest tests still require execution confirmation. The six updated inventory diagnostic unit tests passed on 2026-11-01. The proposed replacement contract is in [ADMIN_INVENTORY_CONSISTENCY_CONTRACT.md](ADMIN_INVENTORY_CONSISTENCY_CONTRACT.md). **No unattended publication may rely on this endpoint's apparent completeness.**

## Reservation input hardening (2026-11-01)

The isolated MySQL reservation prototype and canonical-identity builder now hold malformed input types instead of raising exceptions or touching the database. Two focused tests passed without a database, including a forbidden-connection assertion proving malformed reservations do not open a DB cursor. The disposable MySQL integration suite remains a separate requirement; no production schema or data was changed.

## Existing workflows requiring deployment review

- `.github/workflows/automatic-import.yml` can submit on main push of reviewed JSON or manual dispatch. Despite workflow title, the live Airo backend's admin-key path may auto-approve valid-looking records. Do not assume POST is pending-only until backend containment is deployed and verified.
- `.github/workflows/ibps-live-import.yml` has a manual live import step with `DRY_RUN=false` and must not be treated as safe pending-only without backend checks.
- `.github/workflows/stage-reviewed.yml` can submit when manually called with `submit=true`. This remains a write path.
- `.github/workflows/apify-kamyabi-review.yml` prepares reports only and does not submit to Kamyabi.

**Recommended immediate operations:** keep write workflows untriggered; use the existing 08:00 IST Apify monitoring only to generate manual-review reports. Do not use broad admin-key POST endpoints for unattended intake until containment is verified.

## One-time staging access required

A staging GoDaddy/Airo project with the current backend and a disposable MySQL database (not production), or platform-supported source/config export that enables the real Airo build. Provide access through the platform's normal account sharing; **never paste API keys, OAuth secrets or database passwords in chat**. The staging project must expose an authenticated read-only inventory endpoint and allow isolated write tests without affecting kamyabi.in.

After access exists: apply reviewed containment patch, validate staging build and HTTP handler tests, implement issuer-bound official PDF fetcher, migrate/test unique canonical identity with historic collision reconciliation, replay test matrix, verify public feed and rollback. Only then request owner approval to deploy, and separately to enable automatic publication.

**No live publishing is authorized by this document.**
