# Kamyabi.in smart publishing — release readiness and handoff

Date: 2026-11-01. **Release decision: NO-GO. Automatic publishing must remain disabled.**

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
- Added focused regression tests for these cases. **The new test results have not yet been independently confirmed; prior 70+8 pass counts predate these changes.**
- All changes remain on the unmerged safety branch; the live service and its existing write workflows are unchanged.

## Confirmed production-side blockers

| Gate | Current state | Required for go-live |
|---|---|---|
| Airo import containment patch | Not deployed | Review/apply to staging, then deploy with rollback |
| Airo platform build/type check | Export lacks platform config/modules | Compile/test in real Airo runtime |
| Official PDF retrieval | Offline URL policy only; no pinned-IP TLS fetch | SSRF-safe actual fetch, redirect/IP pinning, size/time limits |
| PDF content and amendment evidence | Synthetic text fixtures only | Official issue/correction/withdrawal fetch and content evidence |
| Admin inventory | Full authenticated pagination not confirmed | Read-only authorized complete inventory, including all statuses |
| Duplicate transaction | Disposable MySQL table tested | Reviewed migration and existing-data reconciliation in Kamyabi staging MySQL |
| Manual approval | Live route still accepts weak URL/date evidence | Regression-test strict human verification, UI and state transition |
| Public feed regression | Not run against staging backend | Prove only explicit reviewed actions affect published feed |
| Feature flag/rollback | No production flag or rollback test | Default OFF, run dry-run, audit log, rollback drill |
| Owner go-live approval | Not requested | Ask only after ALL gates pass |

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
