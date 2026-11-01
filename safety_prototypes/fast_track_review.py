"""Four-check official-page fast track: offline decision only, never publishes.

The caller MUST obtain independent structured fields from an authenticated,
SSRF-safe retrieval of the actual issuer page. Apify metadata, a plausible URL,
or an unverified HTML snippet must never set ``verified_retrieval=True``.
The reservation callback MUST atomically enforce uniqueness of both the
recruitment identity and canonical official-notice URL against all jobs.
"""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import re
import unicodedata
from typing import Callable

from atomic_job_identity import canonical_identity
from official_notice_matcher import Candidate
from official_source_url_policy import UnsafeTarget, preflight_redirect_chain

# Mirror the six supported Government/PSU scopes in vacancy_scope.py. This
# standalone gate runs in isolation and deliberately does not infer categories.
ALLOWED_CATEGORIES = frozenset((
    "central_government", "state_government", "railways",
    "public_sector_banking", "armed_forces", "psu",
))


@dataclass(frozen=True)
class OfficialPageEvidence:
    recruiting_body: str
    advertisement_number: str
    post_name: str
    start_date: date
    last_date: date
    page_text: str
    checked_on: date
    verified_retrieval: bool
    employer_type: str
    employer_type_verified: bool
    withdrawn: bool | None = None


@dataclass(frozen=True)
class FastTrackOutcome:
    status: str
    reasons: tuple[str, ...]
    evidence_sha256: str | None


def _normal(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def _quoted_field_present(page_text: str, value: str) -> bool:
    phrase = _normal(value)
    return bool(phrase) and re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)",
                                      _normal(page_text)) is not None


def review_official_page_fast_track(
    *,
    job_id: str,
    candidate: Candidate,
    category: str,
    recruitment_cycle: str,
    evidence: OfficialPageEvidence,
    url_chain: list[str],
    allowed_domains: tuple[str, ...],
    resolve_dns,
    inventory_complete: bool,
    existing_duplicate: bool | None,
    reserve_notice_identity: Callable[..., object],
    today: date,
) -> FastTrackOutcome:
    """Dry-run readiness for *official HTML or PDF*, with no publication write.

    Four gates: official matching content, open application dates, authoritative
    duplicate snapshot plus atomic two-key reservation, and validated job class.
    An unknown result at any gate becomes manual review. This code neither
    stages jobs nor calls the live Kamyabi administration API.
    """
    reasons: list[str] = []
    verified_url: str | None = None
    try:
        preflight_redirect_chain(url_chain, allowed_domains, resolve_dns)
        verified_url = url_chain[-1]
    except (UnsafeTarget, TypeError, IndexError) as exc:
        reasons.append(f"unsafe_official_url:{exc}")

    if not evidence.verified_retrieval or not isinstance(evidence.page_text, str) or not evidence.page_text.strip():
        reasons.append("official_page_not_independently_verified")
    if evidence.checked_on != today:
        reasons.append("official_page_not_checked_today")
    if evidence.withdrawn is True:
        reasons.append("notice_withdrawn")

    for label in ("recruiting_body", "advertisement_number", "post_name"):
        from_listing = getattr(candidate, label)
        from_official_page = getattr(evidence, label)
        if not _normal(from_listing) or _normal(from_listing) != _normal(from_official_page):
            reasons.append(f"{label}_mismatch")
        if not _quoted_field_present(evidence.page_text, from_official_page):
            reasons.append(f"{label}_missing_from_official_page")

    if (candidate.start_date != evidence.start_date
            or candidate.last_date != evidence.last_date):
        reasons.append("application_dates_mismatch")
    if (candidate.start_date > candidate.last_date
            or evidence.start_date > evidence.last_date):
        reasons.append("application_dates_invalid")
    if candidate.last_date < today:
        reasons.append("deadline_expired")

    if (category not in ALLOWED_CATEGORIES
            or evidence.employer_type != category
            or evidence.employer_type not in ALLOWED_CATEGORIES
            or not evidence.employer_type_verified):
        reasons.append("government_psu_classification_unverified")

    if inventory_complete is not True:
        reasons.append("incomplete_duplicate_inventory")
    if existing_duplicate is not False:
        reasons.append("existing_or_unchecked_duplicate")

    identity = canonical_identity(candidate.recruiting_body, candidate.advertisement_number,
                                  recruitment_cycle, candidate.post_name) if all(
                                      isinstance(v, str) for v in (
                                          candidate.recruiting_body, candidate.advertisement_number,
                                          recruitment_cycle, candidate.post_name)) else None
    if not identity:
        reasons.append("identity_incomplete")
    if not job_id or not isinstance(job_id, str):
        reasons.append("job_id_missing")
    digest = sha256(evidence.page_text.encode("utf-8")).hexdigest() if isinstance(evidence.page_text, str) and evidence.page_text else None
    if reasons:
        return FastTrackOutcome("manual_review", tuple(dict.fromkeys(reasons)), digest)

    # The only write is via the supplied *dry-run reservation* implementation.
    claim = reserve_notice_identity(
        job_id=job_id, identity=identity, notice_url=verified_url,
        evidence_sha256=digest,
    )
    if getattr(claim, "state", None) in ("reserved_dry_run", "already_reserved"):
        return FastTrackOutcome("fast_track_eligible_dry_run", (), digest)
    return FastTrackOutcome(
        "manual_review", (f"duplicate_reservation:{getattr(claim, 'state', 'unknown')}",), digest,
    )
