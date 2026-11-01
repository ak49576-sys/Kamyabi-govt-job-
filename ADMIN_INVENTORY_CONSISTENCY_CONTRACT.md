# Kamyabi admin inventory and duplicate reservation — staging contract

Status: **proposal only / no production change** (2026-11-01). Never enable automatic publishing using the current admin GET endpoint as proof of inventory completeness.

## Current exported behavior

- `GET /api/v1/admin/jobs` accepts `status=pending|approved|rejected`, `limit` and `offset`.
- It returns `total: jobs.length`, i.e. the **current page length**, not the global count.
- It orders only by `createdAt DESC`; records with equal timestamps have no stable tie-breaker.
- Each page is queried independently, without a shared database snapshot. Inserts or approval-state transitions between pages can cause omissions or repeats.
- Exported schema uses `pending`, `approved`, `rejected`. Public publication derives from approval; do not invent a separate published status.

## Required read-only inventory contract

An authorized, narrowly scoped inventory exporter should perform a consistent read (for example, a MySQL REPEATABLE READ read-only transaction) and enumerate **all** relevant records in a stable order such as `(created_at, job_id)`, with a deterministic keyset cursor. Include the same-snapshot record count and a snapshot/export identifier. The export should return job ID, source URL, normalized recruiting body, advertisement number, recruitment cycle, post, notice identity, verification status and any historical aliases, including rejected and approved records. It should exclude secrets, credentials and unnecessary applicant data.

A consumer must reject invalid pages, missing/duplicate cursors, inconsistent counts, missing statuses, changes of snapshot ID, failed authorization or timeouts. Without the complete snapshot contract, the diagnostic `admin_inventory_readonly.py` must report `inventory_complete: false`.

**A complete inventory is necessary for reconciliation, but is not sufficient to prevent races.**

## Required atomic duplicate protection

1. Reconcile historical collisions before adding a uniqueness constraint. Do not silently overwrite an existing approved/rejected record.
2. Use a database-backed canonical recruitment identity with a unique constraint (at minimum recruiting body, advertisement/cycle and post, with agency-specific handling of multi-post notices).
3. Reserve that identity in the same transaction as any candidate insert/update. Two concurrent workers must not both succeed; loser goes to duplicate/manual review. Idempotent retries must not create a second public job.
4. Treat notice URL and advertisement number as collision signals, not sole universal keys—one official PDF may cover multiple distinct posts.
5. Preserve reviewed status during source refreshes. A correction or withdrawn notice must trigger a hold or explicit reviewed update, not an unattended overwrite.
6. A publishing transaction must confirm trusted official-document evidence, current notice/amendment status, unexpired dates and duplicate reservation. Any unknown evidence or incomplete inventory means manual review.

## Isolated acceptance tests

- Same candidate twice sequentially and concurrently: exactly one reserved identity.
- Different job slugs for one recruitment identity: second held.
- Same PDF with two independently advertised posts: manual classification, no silent data loss.
- Collision with existing pending, approved or rejected record: no new public row.
- Page change between inventory requests: snapshot mismatch detected and gate closed.
- Invalid/no credential, empty count, missing page, cursor cycle and non-200 response: fail closed.
- Approval races with refresh/rejection: no status flip without explicit reviewed action.
- Public-feed count changes only after a reviewed action; audit log and rollback tested.

No live POST, automatic publication, migration or GoDaddy deploy is authorized by this specification.
