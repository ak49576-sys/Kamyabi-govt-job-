import sqlite3
import unittest

from fast_track_reservation import canonical_notice_url, create_schema, reserve_notice_identity


class FastTrackReservationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        create_schema(self.conn)
        self.args = dict(job_id="ssc-je", identity="staff selection commission|advt 12/2026|je|2026",
                         notice_url="https://ssc.gov.in/jobs/je?utm_source=mail&b=2&a=1",
                         evidence_sha256="a" * 64)

    def tearDown(self):
        self.conn.close()

    def reserve(self, **kw):
        return reserve_notice_identity(self.conn, **{**self.args, **kw})

    def test_reservation_and_idempotence(self):
        self.assertEqual(self.reserve().state, "reserved_dry_run")
        self.assertEqual(self.reserve().state, "already_reserved")

    def test_notice_url_tracking_variants_collapse(self):
        self.reserve()
        result = self.reserve(identity="new-key", job_id="other-job",
                              notice_url="https://SSC.gov.in/jobs/je?a=1&b=2")
        self.assertEqual(result.state, "duplicate_hold")

    def test_same_identity_new_url_is_duplicate(self):
        self.reserve()
        self.assertEqual(self.reserve(job_id="other", notice_url="https://ssc.gov.in/other").state,
                         "duplicate_hold")

    def test_changed_document_is_held_for_revision(self):
        self.reserve()
        self.assertEqual(self.reserve(evidence_sha256="b" * 64).state, "duplicate_hold")

    def test_invalid_digest_does_not_reserve(self):
        self.assertEqual(self.reserve(evidence_sha256="bad").state, "hold_invalid_inputs")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM safety_fast_track_reservations").fetchone()[0], 0)

    def test_untrusted_url_is_held(self):
        for url in ("http://ssc.gov.in/x", "https://user@ssc.gov.in/x",
                    "https://ssc.gov.in/x#part", "https://ssc.gov.in:8443/x", "https://[invalid"):
            with self.subTest(url=url):
                self.assertEqual(self.reserve(notice_url=url).state, "hold_invalid_inputs")

    def test_query_normalization(self):
        self.assertEqual(canonical_notice_url("https://SSC.gov.in/a?b=2&utm_medium=email&a=1"),
                         "https://ssc.gov.in/a?a=1&b=2")


if __name__ == "__main__":
    unittest.main()
