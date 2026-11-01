"""Offline integration rehearsal only; returns review outcomes and never publishes.

PDF bytes and notice-status flags are synthetic/test-supplied here. Production
must obtain them from a secure, pinned official fetch and independent issuer feed.
"""

from dataclasses import dataclass
from datetime import date
from typing import Callable

from atomic_job_identity import canonical_identity
from official_notice_matcher import Candidate, ExtractedNotice, evaluate_extracted_notice
from official_notice_pdf import extract_pdf_text, extract_labeled_application_dates
from official_source_url_policy import UnsafeTarget, preflight_redirect_chain


@dataclass(frozen=True)
class ReviewOutcome:
    status: str
    reasons: tuple[str, ...]
    document_sha256: str | None


def rehearse_vacancy_review(
    *,
    job_id: str,
    candidate: Candidate,
    recruitment_cycle: str,
    url_chain: list[str],
    allowed_domains: tuple[str, ...],
    resolve_dns,
    pdf_bytes: bytes,
    latest_corrections_checked: bool,
    withdrawn: bool | None,
    inventory_complete: bool,
    reserve_identity: Callable[..., object],
    today: date,
) -> ReviewOutcome:
    reasons: list[str] = []
    try:
        preflight_redirect_chain(url_chain, allowed_domains, resolve_dns)
    except UnsafeTarget as exc:
        reasons.append(f"unsafe_official_url:{exc}")

    pdf = extract_pdf_text(pdf_bytes)
    if not pdf.complete:
        reasons.append(f"pdf_unverified:{pdf.reason}")

    notice = ExtractedNotice(
        text=pdf.text,
        extraction_complete=pdf.complete,
        official_source_confirmed=not any(r.startswith("unsafe_official_url:") for r in reasons),
        correction_chain_checked=latest_corrections_checked,
        withdrawn=withdrawn,
    )
    matched = evaluate_extracted_notice(candidate, notice, today=today)
    reasons.extend(
        r for r in matched.reasons if r != "dates_require_structured_extraction"
    )

    dates = extract_labeled_application_dates(pdf.text or "")
    if dates is None or dates != (candidate.start_date, candidate.last_date):
        reasons.append("application_dates_not_matched")
    if not inventory_complete:
        reasons.append("incomplete_duplicate_inventory")

    identity = canonical_identity(
        candidate.recruiting_body, candidate.advertisement_number,
        recruitment_cycle, candidate.post_name,
    )
    if identity is None:
        reasons.append("identity_incomplete")
    if reasons:
        return ReviewOutcome("manual_review", tuple(dict.fromkeys(reasons)), pdf.sha256_hex)

    claim = reserve_identity(job_id=job_id, identity=identity, document_sha256=pdf.sha256_hex)
    if getattr(claim, "state", None) in ("reserved_dry_run", "already_reserved"):
        return ReviewOutcome("review_ready_dry_run", (), pdf.sha256_hex)
    return ReviewOutcome("manual_review", (f"identity_reservation:{getattr(claim, 'state', 'unknown')}",), pdf.sha256_hex)
