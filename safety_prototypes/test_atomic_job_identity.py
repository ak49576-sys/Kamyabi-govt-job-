import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from atomic_job_identity import canonical_identity, create_schema, reserve_identity


HASH_A = "a" * 64
HASH_B = "b" * 64


class IdentityStoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        create_schema(self.conn)
        self.key = canonical_identity("SSC", "Advt 12/2026", "2026", "Junior Engineer")

    def tearDown(self):
        self.conn.close()

    def claim(self, job="job-a", key=None, digest=HASH_A):
        return reserve_identity(
            self.conn, job_id=job, identity_key=key if key is not None else self.key,
            evidence_sha256=digest,
        )

    def test_malformed_identity_parts_are_held(self):
        for parts in ((None, "A", "2026", "Post"), ("SSC", 10, "2026", "Post"),
                      ("SSC", "A", None, "Post"), ("SSC", "A", "2026", [])):
            with self.subTest(parts=parts):
                self.assertIsNone(canonical_identity(*parts))

    def test_first_claim_only_reserves(self):
        self.assertEqual(self.claim().state, "reserved_dry_run")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM publication_identity").fetchone()[0], 1)

    def test_identical_retry_is_idempotent(self):
        self.claim()
        self.assertEqual(self.claim().state, "already_reserved")

    def test_different_slug_same_identity_holds(self):
        self.claim()
        result = self.claim(job="job-b")
        self.assertEqual(result.state, "duplicate_hold")
        self.assertEqual(result.canonical_job_id, "job-a")

    def test_changed_document_on_same_identity_holds(self):
        self.claim()
        self.assertEqual(self.claim(digest=HASH_B).state, "duplicate_hold")

    def test_same_slug_different_identity_holds(self):
        self.claim()
        key2 = canonical_identity("SSC", "Advt 13/2026", "2026", "Junior Engineer")
        self.assertEqual(self.claim(key=key2).state, "revision_conflict_hold")

    def test_distinct_post_in_same_ad_is_distinct(self):
        self.claim()
        key2 = canonical_identity("SSC", "Advt 12/2026", "2026", "Accountant")
        self.assertEqual(self.claim(job="job-b", key=key2).state, "reserved_dry_run")

    def test_same_ad_different_issuer_is_distinct(self):
        self.claim()
        key2 = canonical_identity("UPSC", "Advt 12/2026", "2026", "Junior Engineer")
        self.assertEqual(self.claim(job="job-b", key=key2).state, "reserved_dry_run")

    def test_case_and_whitespace_normalization(self):
        key2 = canonical_identity(" ssc ", "ADVT 12/2026", "2026", " junior   engineer ")
        self.assertEqual(key2, self.key)

    def test_missing_ad_is_not_reserved(self):
        self.assertIsNone(canonical_identity("SSC", "", "2026", "Engineer"))

    def test_invalid_sha_is_held(self):
        self.assertEqual(self.claim(digest="not-sha").state, "held_invalid_evidence")

    def test_never_marks_jobs_published(self):
        self.claim()
        fields = [r[1] for r in self.conn.execute("PRAGMA table_info(publication_identity)")]
        self.assertNotIn("verification_status", fields)
        self.assertNotIn("published", fields)

    def test_two_concurrent_reservations_one_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "test.db")
            root = sqlite3.connect(db_path, timeout=10)
            create_schema(root)
            root.close()
            barrier = threading.Barrier(2)
            output = []
            lock = threading.Lock()

            def worker(job_id):
                conn = sqlite3.connect(db_path, timeout=10)
                try:
                    barrier.wait(timeout=5)
                    result = reserve_identity(conn, job_id=job_id, identity_key=self.key,
                                              evidence_sha256=HASH_A)
                    with lock:
                        output.append(result.state)
                finally:
                    conn.close()

            jobs = [threading.Thread(target=worker, args=(slug,)) for slug in ("job-a", "job-b")]
            for job in jobs:
                job.start()
            for job in jobs:
                job.join(timeout=10)
            self.assertFalse(any(job.is_alive() for job in jobs))
            self.assertCountEqual(output, ["reserved_dry_run", "duplicate_hold"])
            verify = sqlite3.connect(db_path)
            self.assertEqual(verify.execute("SELECT COUNT(*) FROM publication_identity").fetchone()[0], 1)
            verify.close()


if __name__ == "__main__":
    unittest.main()
