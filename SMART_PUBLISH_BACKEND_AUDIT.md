# Kamyabi smart-publishing backend contract audit (2026-11-01)

Source: user-supplied Airo Builder project ZIP, inspected locally. This report deliberately contains no secrets, private source dump, or credentials. **No live publication enabled.**

## Confirmed routes from exported source

- `GET /api/v1/admin/jobs?status=pending|approved|rejected&limit=200&offset=N`: requires `X-Api-Key` matching hosting `API_KEY` (not `IMPORT_API_KEY`). Returns `jobs`, `total` (page length), `status`, `limit`, `offset`. Pages must be fetched until a short/empty page. Each row includes status, URL/date verification flags, official notice URL, import source, job ID, dates, title and recruiting body.
- `POST /api/v1/admin/jobs/approve`: requires `API_KEY`; immediately exposes the job on the public dataset and sends search-indexing notifications. Never call from a dry run. Current code checks the presence/format of official notice URL and start/end date, and rejects an already-approved job ID. It does **not** fetch/check the notification PDF, enforce a trusted URL domain or `url_verified`, ensure the deadline is current, check advertisement/title duplicate collisions, or strictly require the prior status to be `pending`. This is a **live-publication risk**.
- `POST /api/v1/admin/apify-import`: runs the Actor and inserts new rows. Despite a comment promising pending-only imports, implementation sets `approved = avResult.passed`, which can publish jobs merely on domain/field checks. Do **not** invoke this route in production until repaired.
- `POST /api/v1/add-jobs`: accepts `API_KEY` or `IMPORT_API_KEY`; with the pipeline key it forces pending and guards against rewriting non-pending or non-pipeline records. With the admin key, some records may be automatically approved by `autoVerify`. The request body is a JSON **array**, whereas the current Python staging client sends an array (correct) but describes response handling separately.
- `src/server/lib/auto-verify.ts`: checks HTTPS, a configured official domain, nonempty title/recruiting body and string date ordering. URL reachability is explicitly disabled. Passing does **not** establish the actual PDF's contents, advertisement ID, or closing date. Domain allowlist has a duplicate NPCIL mapping and a placeholder domain; not reliable as publication proof.

## Safety gate for future implementation

1. Keep all automated imports pending by default. Never interpret domain-only autoVerify as authoritative notice verification.
2. Separate read-only admin inventory credentials from write/publish credentials where the hosting app supports it; do not copy `API_KEY` into public repository secrets merely to make the inventory endpoint work.
3. Obtain complete pending, approved and rejected pages; fail closed on 401, partial pages, schema drift, or inconsistent inventory. Distinct `job_id`, official notice URL, advertisement number and title/year identity need collision checks.
4. Verify specific official notice contents and all meaningful fields before setting an immutable evidence record. Unknown/conflicting values go to manual review.
5. Use a staged review-to-publish transition with server-side revalidation, atomic duplicate protection and idempotency; do not call the existing approval POST automatically.
6. Test code in isolated branch with mocks/fixtures and no network write. Do not deploy or enable publishing without explicit subsequent approval.

## Open questions

- Does the exported ZIP correspond to the currently **deployed** backend? Verify version/route behavior through authorized non-mutating checks only.
- Can hosting expose a dedicated read-only inventory API with scoped permissions and pagination metadata?
- Is there a separate server-side URL review workflow that sets `url_verified` only after checking the specific notice? Audit before using it.

**Decision:** existing 20 Python safety tests passing does not make the live approval endpoints safe. Smart auto-publish remains OFF; no Airo credits used.
