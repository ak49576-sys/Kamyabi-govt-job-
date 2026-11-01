"""Isolated SQLite duplicate lock rehearsal. No Kamyabi job or publish writes.

The real Airo MySQL backend needs its own migration and transactional checks
against legacy/pending/approved records before this can be used to go live.
"""

from dataclasses import dataclass
import re
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class Reservation:
    state: str
    canonical_job_id: str | None


def canonical_notice_url(value: str) -> str | None:
    """Normalize harmless URL differences; reject unsafe or ambiguous forms."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
        if (parts.scheme.lower() != "https" or not host or parts.username is not None
                or parts.password is not None or parts.fragment or parts.port not in (None, 443)):
            return None
        query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"})
        return urlunsplit(("https", host, parts.path or "/", urlencode(query), ""))
    except (ValueError, UnicodeError, AttributeError):
        return None


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS safety_fast_track_reservations ("
        "identity_key TEXT NOT NULL UNIQUE, "
        "notice_url TEXT NOT NULL UNIQUE, "
        "job_id TEXT NOT NULL UNIQUE, "
        "evidence_sha256 TEXT NOT NULL)"
    )
    connection.commit()


def reserve_notice_identity(connection: sqlite3.Connection, *, job_id: str,
                            identity: str, notice_url: str,
                            evidence_sha256: str) -> Reservation:
    canonical = canonical_notice_url(notice_url)
    if (not isinstance(job_id, str) or not job_id or len(job_id) > 255
            or not isinstance(identity, str) or not identity or len(identity) > 1024
            or canonical is None or not isinstance(evidence_sha256, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", evidence_sha256)):
        return Reservation("hold_invalid_inputs", None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        found = connection.execute(
            "SELECT identity_key, notice_url, job_id, evidence_sha256 "
            "FROM safety_fast_track_reservations "
            "WHERE identity_key=? OR notice_url=? OR job_id=?",
            (identity, canonical, job_id),
        ).fetchone()
        if found:
            connection.commit()
            if found == (identity, canonical, job_id, evidence_sha256.lower()):
                return Reservation("already_reserved", job_id)
            return Reservation("duplicate_hold", found[2])
        connection.execute(
            "INSERT INTO safety_fast_track_reservations "
            "(identity_key, notice_url, job_id, evidence_sha256) VALUES (?, ?, ?, ?)",
            (identity, canonical, job_id, evidence_sha256.lower()),
        )
        connection.commit()
        return Reservation("reserved_dry_run", job_id)
    except sqlite3.IntegrityError:
        connection.rollback()
        return Reservation("race_conflict_hold", None)
    except Exception:
        connection.rollback()
        raise
