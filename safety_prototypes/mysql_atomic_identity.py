"""Isolated MySQL transactional duplicate-reservation prototype.

NEVER point this module at a production database. It writes only to an
ephemeral CI test schema and never touches the govt_jobs or publication fields.
"""
from dataclasses import dataclass
from hashlib import sha256
import re


@dataclass(frozen=True)
class Reservation:
    state: str
    canonical_job_id: str | None


CREATE_TEST_TABLE = """
CREATE TABLE IF NOT EXISTS safety_identity_reservations (
    identity_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    identity_description VARCHAR(1024) NOT NULL,
    job_id VARCHAR(255) NOT NULL UNIQUE,
    document_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB
"""


def reserve_mysql_identity(connection, *, job_id: str, identity: str,
                           document_sha256: str) -> Reservation:
    if (not job_id or len(job_id) > 255 or not identity or len(identity) > 1024
            or not re.fullmatch(r"[0-9a-fA-F]{64}", document_sha256)):
        return Reservation("hold_invalid_inputs", None)
    identity_hash = sha256(identity.encode("utf-8")).hexdigest()
    cursor = connection.cursor()
    try:
        connection.start_transaction()
        try:
            cursor.execute(
                "INSERT INTO safety_identity_reservations "
                "(identity_hash, identity_description, job_id, document_sha256) "
                "VALUES (%s, %s, %s, %s)",
                (identity_hash, identity, job_id, document_sha256.lower()),
            )
            connection.commit()
            return Reservation("reserved_dry_run", job_id)
        except Exception as exc:
            connection.rollback()
            # MySQL duplicate-key error 1062, whether unique identity or job ID.
            if getattr(exc, "errno", None) != 1062:
                raise
        cursor.execute(
            "SELECT job_id, document_sha256 FROM safety_identity_reservations "
            "WHERE identity_hash = %s", (identity_hash,)
        )
        existing = cursor.fetchone()
        if existing:
            if existing[0] == job_id and existing[1] == document_sha256.lower():
                return Reservation("already_reserved", job_id)
            return Reservation("duplicate_hold", existing[0])
        cursor.execute(
            "SELECT job_id FROM safety_identity_reservations WHERE job_id = %s", (job_id,)
        )
        if cursor.fetchone():
            return Reservation("revision_conflict_hold", job_id)
        return Reservation("race_conflict_hold", None)
    finally:
        cursor.close()
