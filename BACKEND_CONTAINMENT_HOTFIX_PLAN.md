# Proposed Airo backend containment patch — NOT DEPLOYED

Source audited: user-provided Kamyabi.in Airo project export, 2026-11-01.

**Purpose:** fail closed so imported/automatically checked vacancies cannot become public merely because their URL host and date strings look plausible. This is a code review/change specification, **not a validated production patch**. Do not run any write endpoint as a test.

## 1. Block Apify import auto-approval

File: `src/server/api/v1/admin/apify-import/POST.ts`

Inside the insert mapping (~line 449), replace the assignment `const approved = avResult.passed;` with `const approved = false;`. Keep `avResult.passed` only as non-authoritative review metadata. Change the `auto_verify_pass` audit field to `avResult.passed`, so the field does not falsely mean the job was fully verified. Use `verified: false` and `verificationStatus: 'pending'` unconditionally for every new Apify record. Fix the comment that currently contradicts the implementation. Unit-test that both passing and failing `autoVerify` results are pending.

## 2. Block add-jobs auto-approval and promotion

File: `src/server/api/v1/add-jobs/POST.ts`

For new records, replace `const approved = isGithubPipeline ? false : result.passed;` with `const approved = false;`. This prevents the admin-key import path from bypassing review. For updates, prevent `canAutoPromote` from becoming true based only on `autoVerify`: restrict promotion to an explicit, separately audited official-notice evidence gate (not present yet). For the interim hotfix, keep `canAutoPromote = false`. Preserve the guards that prevent the GitHub pipeline from editing human-reviewed jobs and from colliding with admin-owned pending records.

## 3. Block bulk auto-verify from publishing

File: `src/server/api/v1/admin/jobs/auto-verify/POST.ts`

The current `if (result.passed)` branch approves **non-GitHub** records automatically. Change that branch to return `approved:false, blocked:true` with a reason that manual official-notification review is required, for **all** import sources. Do not write `verified:true`, `verificationStatus:'approved'`, or `lastVerifiedAt` from this endpoint. The batch indexing notification must receive an empty list and must not run.

## 4. Harden manual approval separately

File: `src/server/api/v1/admin/jobs/approve/POST.ts`

The current handler immediately publishes when a caller supplies a URL and well-shaped date strings. It does not require `urlVerified` or a pending prior state. Until a complete evidence gate and atomic duplicate check exist, preserve manual approval only and require a server-trusted, reviewer-confirmed specific notice plus sane non-expired dates. Existing admin UI flow must be regression-tested before changing it; an uncoordinated change may disrupt manual approvals.

## 5. Add inventory read-only access

The exported `GET /api/v1/admin/jobs` requires the broad `API_KEY`, while GitHub's existing import secret may be `IMPORT_API_KEY`. Design a dedicated read-only secret/scope or a signed server-side inventory export. Ensure pagination consistency, completeness, and no key in logs. See `admin_inventory_readonly.py` for the fail-closed client; it has not authenticated successfully against production.


## Single-job auto-verification must enforce pending state

A further source inspection of the exported `admin/jobs/auto-verify/POST.ts` found that the `job_id` path selects by job ID alone, unlike the bulk path which selects `verificationStatus = 'pending'`. When a specific already-approved/rejected ID is submitted and its autoVerify result fails, the handler can update `rejectionReason` on that nonpending record. This is a state-integrity problem even when the separate containment patch prevents new approvals.

The review-only patch generator now proposes a pending-state condition for both the single-job SELECT and rejection-reason UPDATE; its three-route, 120-line diff matched the exact uploaded Airo export, and five generator unit tests passed. **It has not been applied or runtime-tested.** Before staging deployment, confirm response semantics for nonpending IDs (currently selected as not found), and add HTTP-handler regression tests for approved/rejected/missing/pending IDs. Make the status check and write atomic or conditional at the database level to avoid a concurrent manual-approval race. No production endpoint was called during this finding.

## Required test matrix before deployment

- For each of Apify import, admin-key add-jobs, pipeline-key add-jobs, and bulk auto-verify: both domain-valid and invalid test notices must remain unpublished.
- No mutation of pre-existing approved/rejected records or admin-owned pending records.
- Conflicting dates, expired notices, duplicate URL/advt/title-year, malformed official PDFs, missing inventory page: hold for manual review.
- Manual approval must remain available only for actual reviewed records; public feed should change only following an explicit manual action.
- No live production POST in tests. Mock DB and HTTP calls or run an isolated nonproduction database.

**Status:** This is a branch-only deployment plan. Production code and GoDaddy hosting were not changed, no Airo credits used, and auto-publishing is still OFF.

## Export compatibility validation (2026-11-01)

The review-only generator `prepare_airo_safety_patch.py` was executed in memory against the user-provided project ZIP. All three required source paths and all exact replacement anchors matched once; all three proposed versions differ from the originals, producing a 92-line unified diff. No file was written or deployed. The GitHub test suite also verifies that missing/drifted source patterns abort rather than applying partial changes. This does **not** establish compilation or production behavior; the backend still requires isolated integration testing and a source-compatible deployment workflow.

Additional review: `fix-unverified-dates/POST.ts` and `run-fix/POST.ts` preserve already-approved statuses while clearing historic dates and setting a 2099 sentinel. These routes do not independently promote pending records, but must not be used as automated publication remediation; the sentinel violates our current vacancy-validity policy.

## Isolated export testing (2026-11-01)

A temporary local copy of the user's Airo ZIP was extracted and the exact three-route patch applied to **that copy only**. Results:

- TypeScript syntactic transpilation of all three changed routes: **3/3 passed**.
- Existing `pipeline-guard.test.ts`: **34 tests passed**.
- `npm ci`: blocked by an existing package-lock mismatch (missing `yjs`, `lib0`, `isomorphic.js`). For isolated tests only, dependencies were installed without modifying the project's lockfile.
- Whole-project `npm run type-check`: **failed** due to existing missing `@airo/content`, missing `format-overrides-plugin`, and Vite config symbols/type errors. No new diagnostics were reported against the three changed routes, but this is not a clean build.
- `url-verified-reset.test.ts`: **blocked** on absent platform database configuration at `/local/config.json`. The existing test imports the server DB client during module initialization. No production DB connection was attempted.

**Deployment gate remains CLOSED.** Source syntax checks and 34 passing pipeline tests do not constitute complete integration validation. Further work requires a representative local Airo platform configuration or test-specific mocks, plus new tests covering the changed auto-approval branches. The temp install did not use Airo credits and no live API writes were performed.

## Intra-Actor duplicate guard prototype (2026-11-01)

Further isolated review found that Apify import checked job IDs within one Actor dataset, but checked notice URLs and advertisement numbers only against pre-existing database rows. A single dataset could therefore contain multiple different slugs referencing the same notice or advertisement. In the temporary, **undeployed** Airo copy, a pure `apify-payload-dedupe.ts` helper and six unit tests were added; `apify-import/POST.ts` now checks all three keys against records accepted earlier in the same payload. Existing database duplicate checks are retained. Both targeted suites passed: **40 tests in 2 files** (34 original pipeline-guard tests + 6 new in-run duplicate tests).

Limitations: the existing pipeline-guard tests mirror older handler logic (including an admin auto-approval expectation), so 40 green tests do **not** prove all changed routes behave safely. Full DB-integrated tests are still blocked by the absent Airo platform config, and URL normalization, advertisement-number scoping, concurrency safety, database uniqueness, and official PDF verification remain unverified. The new helper/test changes currently live in the temporary test copy only and are **not** included in the original three-route proposed patch. Before any deployment, generate and review an updated patch including the helper/tests, then run real isolated integration tests. **Live publishing remains disabled.**

## Mocked HTTP-handler regression tests (2026-11-01)

Executed the **actual patched** `admin/jobs/auto-verify/POST.ts` handler with Vitest mocks for database, secrets, verifier, and search-engine notifications. Seven tests passed: bad API key returns 401; passing checks for `admin`, `github_pipeline`, `apify`, and null sources all return `auto_approved:0` and `blocked:true`, with no database update or indexing call; a failed check records rejection details but not approval; and mixed batches never approve or notify. Combined with six pure intra-Actor duplicate tests: **13 tests across two files passed**. These are in addition to the previously passing 34 legacy pipeline tests. The Airo export has been updated **only in the temporary test copy** to correct stale endpoint comments.

This narrows the auto-verify regression risk but is not full end-to-end validation. The existing GitHub branch contains the containment proposal and audit, **not the newly tested Airo source/test files**. Before deployment, include the updated route/helper/tests in a reviewed patch, provision a representative isolated database, and test Apify/add-jobs writes, transaction-safe duplicate protection, official PDF evidence, admin manual approval, and the public feed. No production writes, Airo credits, or automatic publishing were used.

## Manual-approval input hardening prototype (2026-11-01)

Isolated review of `src/server/api/v1/admin/jobs/approve/POST.ts` confirmed that the current manual-approval route publishes on receipt of an API key, arbitrary nonempty notification URL, and date strings matching `YYYY-MM-DD`; it does not establish official notice content authenticity or duplicate absence. A **temporary-only, undeployed** input validator was integrated into the exported Airo route to reject malformed/non-HTTPS URLs, URL credentials or fragments, impossible calendar dates, reversed application date ranges, and deadlines before the current date. Eleven focused unit tests passed, bringing the selected isolated suite total to **58 tests across four files** (34 legacy pipeline tests, 6 Apify in-payload duplicate tests, 7 mocked auto-verify route tests, 11 manual input tests).

**Critical limitation:** the validator intentionally accepts a syntactically valid HTTPS URL on an untrusted host; passing it does NOT prove official notice contents, correct issuer, or vacancy authenticity. It is only an input hygiene layer. The current live manual endpoint remains unchanged and is not sufficiently protected for unattended publication. The prototype and tests exist only in the temporary Airo copy, not in the GitHub branch or production. Approval route changes must be reviewed for compatibility with the admin UI, plus tested against an isolated DB, and paired with official PDF/content verification and transaction-safe duplicate checks before deployment. No live changes or Airo credits.
