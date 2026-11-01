"""Read-only smart publication eligibility preview. No network calls or writes.

The official evidence object must be populated by the independent, server-side
official-page verifier, never by Apify, an importer, or a job submitter. This
pure preview does not authenticate evidence and cannot authorize publication.
"""

from datetime import date
from urllib.parse import urlparse
import re

REQUIRED = ("job_id", "title", "recruiting_body", "advt_no", "last_date",
            "official_notification_url", "vacancy_count", "qualification", "scope_category")
OFFICIAL_MATCH_FIELDS = ("official_title", "official_recruiting_body", "official_advt_no",
                         "official_last_date")
TRUSTED_STATES = {"pending", "approved", "published", "rejected"}
ALLOWED_SCOPES = {"central_government", "state_government", "railways",
                  "public_sector_banking", "armed_forces", "psu"}


def _norm(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _host(value):
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            return ""
        return (parsed.hostname or "").lower()
    except ValueError:
        return ""


def _fingerprints(row):
    body = _norm(row.get("recruiting_body"))
    advt = _norm(row.get("advt_no"))
    title = _norm(row.get("title"))
    year = str(row.get("last_date") or "")[:4]
    keys = set()
    notice_url = row.get("official_notification_url")
    notice_host = _host(notice_url)
    if notice_host:
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(notice_url)
        keys.add(("notice-url", urlunsplit(("https", notice_host, parts.path, parts.query, ""))))
    if body and advt:
        keys.add(("advt", body, advt))
    if body and title and re.fullmatch(r"20\d{2}", year):
        keys.add(("title-year", body, title, year))
    return keys


def assess(candidate, existing_records, official_evidence, today=None, inventory_complete=False):
    """Four checks; `eligible_for_dry_run` never grants actual publication."""
    today = today or date.today()
    reasons = []
    if not inventory_complete:
        reasons.append("pending_and_published_inventory_unverified")
    if not isinstance(candidate, dict) or not isinstance(existing_records, list):
        return {"decision": "manual_review", "reasons": ["invalid_input"]}
    if not isinstance(official_evidence, dict):
        official_evidence = {}
    missing = [field for field in REQUIRED if candidate.get(field) in (None, "")]
    if missing:
        reasons.append("missing_fields:" + ",".join(missing))
    try:
        deadline = date.fromisoformat(candidate.get("last_date", ""))
        if deadline < today or deadline.year > today.year + 2:
            reasons.append("expired_or_implausible_deadline")
    except (ValueError, TypeError):
        reasons.append("invalid_deadline")
    if type(candidate.get("vacancy_count")) is not int or candidate.get("vacancy_count", -1) <= 0:
        reasons.append("invalid_vacancy_count")
    host = _host(candidate.get("official_notification_url"))
    if not host or host in {"freejobalert.com", "www.freejobalert.com"}:
        reasons.append("nonofficial_notice_url")

    # Basic payload shape stays required, but the official-page fast track
    # only cross-matches issuer, advertisement, post title and deadline.
    # A PDF, extracted vacancy count and extracted qualification are optional.
    if official_evidence.get("source_type") not in {"official_notice", "official_page"}:
        reasons.append("official_evidence_missing")
    else:
        if official_evidence.get("url") != candidate.get("official_notification_url"):
            reasons.append("evidence_url_mismatch")
        mapping = {
            "official_title": "title", "official_recruiting_body": "recruiting_body",
            "official_advt_no": "advt_no", "official_last_date": "last_date",
        }
        for evidence_field, job_field in mapping.items():
            observed = official_evidence.get(evidence_field)
            claimed = candidate.get(job_field)
            if observed in (None, "") or claimed in (None, ""):
                reasons.append("missing_official_field:" + evidence_field)
            elif _norm(observed) != _norm(claimed):
                reasons.append("official_mismatch:" + job_field)
        if (official_evidence.get("retrieval_succeeded") is not True
                or official_evidence.get("official_content_verified") is not True):
            reasons.append("official_retrieval_unconfirmed")
        if official_evidence.get("checked_on") != today.isoformat():
            reasons.append("official_evidence_stale")
        if official_evidence.get("withdrawn") is True:
            reasons.append("withdrawn_notice")

    # Classification must come from independent official-source verification,
    # not the broad scraped category or mere URL domain.
    scope = candidate.get("scope_category")
    if (scope not in ALLOWED_SCOPES
            or official_evidence.get("verified_scope_category") != scope
            or official_evidence.get("classification_verified") is not True):
        reasons.append("government_psu_scope_not_verified")

    fingerprints = _fingerprints(candidate)
    if not fingerprints:
        reasons.append("insufficient_duplicate_identity")
    for row in existing_records:
        if not isinstance(row, dict) or row.get("status") not in TRUSTED_STATES:
            reasons.append("incomplete_existing_inventory")
            continue
        same_id = bool(candidate.get("job_id")) and row.get("job_id") == candidate.get("job_id")
        if same_id or fingerprints & _fingerprints(row):
            return {"decision": "duplicate_or_update_review", "reasons": ["existing_record:" + str(row.get("status"))]}
    if reasons:
        return {"decision": "manual_review", "reasons": sorted(set(reasons))}
    # Additional database-atomic identity+URL reservation is required later;
    # this read-only preview cannot make it or release the live publish gate.
    return {"decision": "eligible_for_dry_run", "reasons": []}


def assess_batch(candidates, existing_records, evidence_by_job_id, today=None, inventory_complete=False):
    """Fail closed on duplicates within the incoming batch too."""
    if not isinstance(candidates, list) or not isinstance(existing_records, list) or not isinstance(evidence_by_job_id, dict):
        return [{"job_id": None, "decision": "manual_review", "reasons": ["invalid_batch_input"]}]
    results = []
    prior = list(existing_records)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            results.append({"job_id": None, "decision": "manual_review", "reasons": ["invalid_candidate"]})
            continue
        evidence = evidence_by_job_id.get(candidate.get("job_id"))
        result = assess(candidate, prior, evidence, today, inventory_complete)
        results.append({"job_id": candidate.get("job_id"), **result})
        if candidate.get("job_id") or _fingerprints(candidate):
            prior.append({**candidate, "status": "pending"})
    return results
