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
