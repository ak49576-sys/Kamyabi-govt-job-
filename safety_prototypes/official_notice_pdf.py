"""Offline, fail-closed PDF text and labeled date extraction prototypes.

The caller must independently prove the bytes came from the issuer's official
site and check amendments/withdrawals. No network or publication occurs here.
"""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from io import BytesIO
import re

from pypdf import PdfReader


@dataclass(frozen=True)
class PdfExtract:
    text: str | None
    sha256_hex: str | None
    complete: bool
    reason: str | None


def extract_pdf_text(data: bytes, *, max_bytes: int = 5_000_000,
                     max_pages: int = 30, min_chars: int = 40) -> PdfExtract:
    if not data or len(data) > max_bytes:
        return PdfExtract(None, None, False, "size_invalid")
    digest = sha256(data).hexdigest()
    if not data.startswith(b"%PDF-"):
        return PdfExtract(None, digest, False, "not_pdf")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            return PdfExtract(None, digest, False, "encrypted")
        if not 1 <= len(reader.pages) <= max_pages:
            return PdfExtract(None, digest, False, "page_count_invalid")
        texts = [page.extract_text() or "" for page in reader.pages]
    except Exception:
        return PdfExtract(None, digest, False, "parse_error")
    text = "\n".join(texts).strip()
    if len(text) < min_chars:
        return PdfExtract(text, digest, False, "unreadable_or_scanned")
    return PdfExtract(text, digest, True, None)


_DATE_VALUE = r"(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})"
_START = re.compile(r"(?i)\b(?:application\s+start\s+date|applications?\s+open(?:s|ing)?\s+on)\s*[:\-]?\s*" + _DATE_VALUE)
_LAST = re.compile(r"(?i)\b(?:application\s+last\s+date|applications?\s+clos(?:e|es|ing)\s+on|last\s+date\s+to\s+apply)\s*[:\-]?\s*" + _DATE_VALUE)


def _date_from_value(value: str) -> date | None:
    try:
        if value[4] == "-":
            parsed = date.fromisoformat(value)
        else:
            day, month, year = map(int, re.split(r"[-/]", value))
            parsed = date(year, month, day)
        return parsed
    except (ValueError, IndexError):
        return None


def extract_labeled_application_dates(text: str) -> tuple[date, date] | None:
    """Return unique, plausible labeled dates only; ambiguity means no evidence."""
    starts = {_date_from_value(v) for v in _START.findall(text)}
    ends = {_date_from_value(v) for v in _LAST.findall(text)}
    if len(starts) != 1 or len(ends) != 1 or None in starts or None in ends:
        return None
    start, end = next(iter(starts)), next(iter(ends))
    if start > end:
        return None
    return start, end
