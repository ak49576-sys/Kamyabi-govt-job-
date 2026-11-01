# Relaxed Kamyabi smart-publishing verification — offline implementation

Date: 2026-11-01. **Status: implemented and tested on safety branch; NOT deployed. Live automatic publishing remains OFF.**

This replaces the document-heavy *eligibility preview* with four core checks. It does **not** weaken the requirement that actual official recruitment evidence be obtained independently of Apify or a submitted job payload.

## Four required checks

1. **Official recruiting-body source:** An HTTPS page or PDF on a separately approved issuer domain contains and confirms the recruiting body, advertisement number and specific post. A PDF is **optional** when a verified official HTML page supplies the information. A link alone, a scraper claim, a cached description, or a copied boolean does not establish verification. Known withdrawn notices are held.
2. **Open recruitment window:** Application start/end dates agree with the official page and the last date has not passed in India. The preview rejects implausible, malformed or expired deadlines. The source must have been checked on the current monitoring day.
3. **Duplicate protection:** Compare against a complete, consistent snapshot covering pending, approved, published, rejected and legacy records. Hold when inventory is partial or duplicates are unknown. Before any future production decision, use a database transaction with unique canonical recruitment-identity **and** official-notice URL reservations; hold conflicts and revisions. The SQLite rehearsal is not the Kamyabi MySQL implementation.
4. **Correct government/PSU scope:** Independently verify the employer class; support central/state government, railways, public-sector banking, armed forces and PSUs. Private banks, unverified co-operatives and ambiguous entities go to manual review.

The application/API still requires populated basic job fields such as vacancy count and qualifications for a valid record, but the official *fast track* no longer insists on exact extracted count/qualification matches or a full PDF. Missing basic fields cannot be invented.

## Implemented in GitHub

- `smart_publish_gate.py`: existing read-only preview uses the four-check policy and accepts `source_type: official_page`. It cross-matches issuer/advt/post/deadline, freshness and verified scope, but does not publish.
- `safety_prototypes/fast_track_review.py`: separate official HTML/PDF preflight and four-check dry-run rehearsal, with a verified-page evidence contract and no Kamyabi HTTP write.
- `safety_prototypes/fast_track_reservation.py`: **SQLite-only** atomic rehearsal of canonical identity and notice-URL uniqueness. No production schema change.
- `test_smart_publish_relaxed.py` and `safety_prototypes/test_fast_track_*.py`: 36 new focused tests passed locally (11 preview and 25 low-level). Existing preview fixtures updated. The updated GitHub Actions preview and offline suites subsequently passed 51 and 97 tests respectively; these are isolated code tests, not GoDaddy staging certification.
- `.github/workflows/smart-publish-dry-run.yml` and the existing offline-notice safety workflow run the relevant tests on the safety branch.

Example of a **dry-run-only** eligible official-page evidence object:

```json
{
  "source_type": "official_page",
  "url": "https://www.ibps.in/recruitment/assistant",
  "retrieval_succeeded": true,
  "official_content_verified": true,
  "checked_on": "2026-11-01",
  "official_title": "Assistant",
  "official_recruiting_body": "IBPS",
  "official_advt_no": "IBPS/2026-27/06",
  "official_last_date": "2026-11-12",
  "verified_scope_category": "public_sector_banking",
  "classification_verified": true
}
```

**Crucial:** Those booleans and fields are placeholders for server-trusted evidence, not secure attestations. Do not accept evidence keys directly from a scraper, job submitter, editable JSON or public API to approve jobs.

## Result and release boundary

- `eligible_for_dry_run` or `fast_track_eligible_dry_run`: eligible for further integration testing, **not** permission to auto-publish.
- `manual_review`: missing, uncertain, expired, mismatched, wrong-sector or stale job; can appear in an offline review report.
- `duplicate_or_update_review`: already-existing record; update only through an explicit, reviewed path.

The current Airo admin endpoints may autoapprove importer submissions, and the admin inventory endpoint cannot prove complete enumeration. Therefore, **do not submit all 20 Apify candidates to the live importer or enable publishing**. Their existing offline pending-review report remains the handoff until verified pending-only staging is deployed.

To deploy later: obtain a staging Airo environment and a real consistent MySQL inventory, implement an issuer-bound verified HTML/PDF fetcher, reconcile historical duplicates, add transactional production uniqueness, test API pending-only behavior, manual approval, public-feed regression and rollback, then seek separate go-live approval. Do not use Airo credits or live production APIs for these rehearsals.
