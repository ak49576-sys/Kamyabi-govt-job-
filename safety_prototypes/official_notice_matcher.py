"""Conservative extracted-notice checks; dry-run only, no network or publishing.

Inputs must come from a separate trusted fetch/PDF extraction pipeline. Passing
these checks does NOT authenticate a document or authorize publication.
"""

from dataclasses import dataclass
from datetime import date
import re
import unicodedata


@dataclass(frozen=True)
class Candidate:
    recruiting_body: str
    advertisement_number: str
    post_name: str
    start_date: date
    last_date: date


@dataclass(frozen=True)
class ExtractedNotice:
    text: str | None
    extraction_complete: bool
    official_source_confirmed: bool
    correction_chain_checked: bool
    withdrawn: bool | None


@dataclass(frozen=True)
class Verdict:
    status: str
    reasons: tuple[str, ...]


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w]+", " ", value).strip()


def _contains_phrase(text: str, value: str) -> bool:
    phrase = _normalized(value)
    if not phrase:
        return False
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None


def evaluate_extracted_notice(
    candidate: Candidate,
    notice: ExtractedNotice,
    *,
    today: date,
) -> Verdict:
    reasons: list[str] = []
    if not notice.official_source_confirmed:
        reasons.append("official_source_unconfirmed")
    if not notice.extraction_complete or not notice.text:
        reasons.append("content_missing_or_incomplete")
    if not notice.correction_chain_checked:
        reasons.append("corrections_not_checked")
    if notice.withdrawn is not False:
        reasons.append("withdrawal_unknown_or_confirmed")
    if candidate.start_date > candidate.last_date:
        reasons.append("date_order_invalid")
    if candidate.last_date < today:
        reasons.append("deadline_expired")

    extracted = _normalized(notice.text or "")
    if not _contains_phrase(extracted, candidate.recruiting_body):
        reasons.append("issuer_not_in_notice")
    if not _contains_phrase(extracted, candidate.advertisement_number):
        reasons.append("advertisement_not_in_notice")
    if not _contains_phrase(extracted, candidate.post_name):
        reasons.append("post_not_in_notice")

    # Exact date checks require upstream deterministic date extraction.
    # Neither a text occurrence nor this matcher alone proves the dates.
    reasons.append("dates_require_structured_extraction")
    return Verdict("hold", tuple(reasons))
