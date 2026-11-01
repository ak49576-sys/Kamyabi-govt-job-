# Smart publishing official-evidence and duplicate gate — DESIGN ONLY

Airo export audit (2026-11-01). **Not deployed. Automatic publishing disabled.**

## Confirmed risks

- `govt_jobs.job_id` is the sole primary key; notice URLs and advertisement numbers have no DB uniqueness constraint.
- Apify import uses select-then-insert, allowing concurrent imports to race after duplicate prechecks.
- Manual `admin/jobs/approve` sets `verified=true` and `approved` without validated official-document content or an atomic duplicate check.
- Legacy migration `005_seed_url_verified.sql` set `url_verified=true` from PDF-looking URLs, which is not document verification.
- `auto-verify.ts` verifies hostname/date-shaped inputs; HTTP reachability/content verification is disabled.

## Required server-trusted evidence

Never accept importer's claimed verification booleans. A separate SSRF-safe fetcher (allowlist, redirect check, timeout, download-size limit) must verify the issuer's actual official notice, record its final URL and SHA-256, extract content, match exact recruiting body, advertisement ID, post and dates, and check amendment/withdrawal status. Scans, inaccessible files, mismatches, unknown issuer, expired notice or missing fields => pending manual review.

Check complete inventory (pending, approved, rejected, legacy). If pagination/API/DB access fails, hold. Under one DB transaction, recheck record revision and duplicate identity and acquire an idempotency/unique publication key before state change. Log every decision and preserve rollback trace. Never allow a scraper to write approval evidence.

A unique notice URL alone can over-block legitimate multiple-post advertisements; an advertisement number alone can collide across issuers or years. Prefer a reviewed composite key: verified issuer + ad number + recruitment cycle + specific post. Reconcile historic collisions before creating a database uniqueness constraint. Do not silently delete.

## Isolated prototype

A pure `smart-publish-decision.ts` policy, created in the **temporary Airo test copy only**, checks issuer, downloaded/matched notice, body/ad/date match, current/withdrawal state, PDF SHA-256, evidence timestamp, complete duplicate inventory, collision result, and publication lock. Outputs only `hold` or `eligible_dry_run`; it never publishes.

**17 new tests passed; 75 tests passed across five isolated suites** (34 pipeline, 6 Apify in-payload duplicate, 7 actual auto-verify-handler mocks, 11 manual input, 17 evidence policy). This validates the decision policy—not real PDF verification, schema transactions, parallel import safety, production endpoints or deployment.

## Release checklist

1. Implement an independent server-side official notice fetch and parse with realistic PDF/scanned/revised/withdrawn fixtures.
2. Test complete read-only Kamyabi inventory and transaction-safe duplicate identity under parallel imports/approvals in a sandbox MySQL database.
3. Test admin UI, manual approval and public-feed visibility with no live POST.
4. Review Airo export configuration/build and corrected source patch; arrange staging rollback.
5. Only after all checks pass, request separate explicit owner approval to deploy and to enable live automation.

No live website change, no Airo credits, no publishing, no merge occurred.
