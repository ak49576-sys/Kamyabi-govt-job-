"""SQLite-only transactional identity reservation prototype.

Never writes a publication status. Kamyabi production uses MySQL and needs
its own reviewed migration and integration tests before this policy is adopted.
"""

from dataclasses import dataclass
import re
import sqlite3
import unicodedata


def _component(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", normalized)


def canonical_identity(issuer: str, advertisement: str, cycle: str, post: str) -> str | None:
    if not all(isinstance(v, str) for v in (issuer, advertisement, cycle, post)):
        return None
    items = tuple(_component(v) for v in (issuer, advertisement, cycle, post))
    if any(not item or len(item) > 180 for item in items):
        return None
    # Length-prefixed pieces prevent separator collisions.
    return "".join(f"{len(item)}:{item}" for item in items)


@dataclass(frozen=True)
class Claim:
    state: str
    canonical_job_id: str | None


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS publication_identity ("
        "identity_key TEXT PRIMARY KEY, "
        "job_id TEXT NOT NULL UNIQUE, "
        "evidence_sha256 TEXT NOT NULL)"
    )
    connection.commit()


def reserve_identity(connection: sqlite3.Connection, *, job_id: str,
                     identity_key: str | None, evidence_sha256: str | None) -> Claim:
    if (not job_id or not identity_key or not evidence_sha256
            or not re.fullmatch(r"[a-fA-F0-9]{64}", evidence_sha256)):
        return Claim("held_invalid_evidence", None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT job_id, evidence_sha256 FROM publication_identity WHERE identity_key = ?",
            (identity_key,),
        ).fetchone()
        if existing:
            connection.commit()
            if existing[0] == job_id and existing[1] == evidence_sha256:
                return Claim("already_reserved", job_id)
            return Claim("duplicate_hold", existing[0])
        # Same job ID cannot be reused with different identity/evidence.
        previous = connection.execute(
            "SELECT identity_key FROM publication_identity WHERE job_id = ?", (job_id,)
        ).fetchone()
        if previous:
            connection.commit()
            return Claim("revision_conflict_hold", job_id)
        connection.execute(
            "INSERT INTO publication_identity(identity_key, job_id, evidence_sha256) "
            "VALUES (?, ?, ?)", (identity_key, job_id, evidence_sha256.lower()),
        )
        connection.commit()
        return Claim("reserved_dry_run", job_id)
    except sqlite3.IntegrityError:
        connection.rollback()
        return Claim("race_conflict_hold", None)
    except Exception:
        connection.rollback()
        raise
