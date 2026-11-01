"""Tests require only a disposable MYSQL_TEST_* environment, never production."""
import os
import threading
import unittest
from uuid import uuid4

from atomic_job_identity import canonical_identity
from mysql_atomic_identity import CREATE_TEST_TABLE, reserve_mysql_identity


class MysqlReservationInputTests(unittest.TestCase):
    def test_bad_types_are_held_without_touching_db(self):
        class ForbiddenConnection:
            def cursor(self):
                raise AssertionError("Invalid inputs must never reach database")
        invalid = [
            (None, "identity", "a" * 64),
            (123, "identity", "a" * 64),
            ("job", None, "a" * 64),
            ("job", 55, "a" * 64),
            ("job", "identity", None),
            ("job", "identity", 77),
            ("job", "identity", "not-a-digest"),
        ]
        for job_id, identity, digest in invalid:
            with self.subTest(job_id=job_id, identity=identity, digest=digest):
                result = reserve_mysql_identity(ForbiddenConnection(), job_id=job_id,
                                                identity=identity, document_sha256=digest)
                self.assertEqual(result.state, "hold_invalid_inputs")


class MysqlReservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("MYSQL_TEST_HOST"):
            raise unittest.SkipTest("No isolated MYSQL_TEST_HOST configured")
        import mysql.connector
        cls.mysql = mysql.connector
        cls.config = dict(
            host=os.environ["MYSQL_TEST_HOST"],
            port=int(os.getenv("MYSQL_TEST_PORT", "3306")),
            user=os.environ["MYSQL_TEST_USER"],
            password=os.environ["MYSQL_TEST_PASSWORD"],
            database=os.environ["MYSQL_TEST_DATABASE"],
            autocommit=False,
            connection_timeout=5,
        )
        conn = cls.mysql.connect(**cls.config)
        cur = conn.cursor()
        cur.execute(CREATE_TEST_TABLE)
        conn.commit()
        cur.close()
        conn.close()

    def setUp(self):
        self.conn = self.mysql.connect(**self.config)
        self.marker = uuid4().hex
        self.identity = canonical_identity(
            "SSC", f"Advt-{self.marker}", "2026", "Junior Engineer"
        )
        self.job_a = f"job-{self.marker}-a"
        self.job_b = f"job-{self.marker}-b"

    def tearDown(self):
        self.conn.close()

    def reserve(self, job_id=None, identity=None, digest="a" * 64):
        return reserve_mysql_identity(
            self.conn, job_id=job_id or self.job_a,
            identity=identity or self.identity, document_sha256=digest,
        )

    def test_first_reservation(self):
        self.assertEqual(self.reserve().state, "reserved_dry_run")

    def test_identical_retry_is_idempotent(self):
        self.reserve()
        self.assertEqual(self.reserve().state, "already_reserved")

    def test_second_slug_same_notice_is_duplicate(self):
        self.reserve()
        self.assertEqual(self.reserve(job_id=self.job_b).state, "duplicate_hold")

    def test_document_revision_not_silent_reapproval(self):
        self.reserve()
        self.assertEqual(self.reserve(digest="b" * 64).state, "duplicate_hold")

    def test_same_slug_new_identity_held(self):
        self.reserve()
        another = canonical_identity("SSC", f"Advt-X-{self.marker}", "2026", "Engineer")
        self.assertEqual(self.reserve(identity=another).state, "revision_conflict_hold")

    def test_separate_posts_do_not_collide(self):
        self.reserve()
        another = canonical_identity("SSC", f"Advt-{self.marker}", "2026", "Accountant")
        self.assertEqual(self.reserve(job_id=self.job_b, identity=another).state, "reserved_dry_run")

    def test_invalid_hash_fails_closed(self):
        self.assertEqual(self.reserve(digest="bad").state, "hold_invalid_inputs")

    def test_concurrent_imports_one_reservation(self):
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def worker(job_id):
            connection = self.mysql.connect(**self.config)
            try:
                barrier.wait(timeout=5)
                result = reserve_mysql_identity(
                    connection, job_id=job_id, identity=self.identity,
                    document_sha256="a" * 64,
                )
                with lock:
                    results.append(result.state)
            finally:
                connection.close()

        threads = [
            threading.Thread(target=worker, args=(job_id,))
            for job_id in (self.job_a, self.job_b)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(results, ["reserved_dry_run", "duplicate_hold"])
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM safety_identity_reservations WHERE identity_hash = SHA2(%s, 256)",
                    (self.identity,))
        self.assertEqual(cur.fetchone()[0], 1)
        cur.close()


if __name__ == "__main__":
    unittest.main()
