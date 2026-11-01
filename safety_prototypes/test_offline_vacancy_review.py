import sqlite3
import unittest
from dataclasses import replace
from datetime import date
from io import BytesIO

from reportlab.pdfgen import canvas

from atomic_job_identity import create_schema, reserve_identity
from offline_vacancy_review import rehearse_vacancy_review
from official_notice_matcher import Candidate


def make_pdf(lines=None):
    if lines is None:
        lines = [
            "Staff Selection Commission",
            "Advt 12/2026 - Junior Engineer",
            "Application start date: 2026-10-01",
            "Application last date: 2026-11-30",
        ]
    buf = BytesIO()
    document = canvas.Canvas(buf)
    for idx, line in enumerate(lines):
        document.drawString(40, 790 - idx * 22, line)
    document.showPage()
    document.save()
    return buf.getvalue()


class OfflineReviewTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        create_schema(self.conn)
        self.candidate = Candidate("Staff Selection Commission", "Advt 12/2026",
                                   "Junior Engineer", date(2026, 10, 1), date(2026, 11, 30))
        self.args = dict(
            job_id="ssc-je-2026",
            candidate=self.candidate,
            recruitment_cycle="2026",
            url_chain=["https://ssc.gov.in/notice.pdf"],
            allowed_domains=("ssc.gov.in",),
            resolve_dns=lambda _: ["8.8.8.8"],
            pdf_bytes=make_pdf(),
            latest_corrections_checked=True,
            withdrawn=False,
            inventory_complete=True,
            reserve_identity=lambda **kw: reserve_identity(
                self.conn, job_id=kw["job_id"], identity_key=kw["identity"],
                evidence_sha256=kw["document_sha256"],
            ),
            today=date(2026, 11, 1),
        )

    def tearDown(self):
        self.conn.close()

    def check(self, **overrides):
        return rehearse_vacancy_review(**{**self.args, **overrides})

    def test_matching_fixture_is_review_ready_not_published(self):
        self.assertEqual(self.check().status, "review_ready_dry_run")

    def test_bad_host_is_manual_review_and_not_reserved(self):
        result = self.check(url_chain=["https://ssc.gov.in.attacker.example/x.pdf"])
        self.assertEqual(result.status, "manual_review")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM publication_identity").fetchone()[0], 0)

    def test_unreadable_pdf_is_manual_review(self):
        self.assertEqual(self.check(pdf_bytes=make_pdf([])).status, "manual_review")

    def test_wrong_advertisement_is_manual_review(self):
        candidate = replace(self.candidate, advertisement_number="Advt 99/2026")
        self.assertIn("advertisement_not_in_notice", self.check(candidate=candidate).reasons)

    def test_wrong_dates_are_manual_review(self):
        candidate = replace(self.candidate, last_date=date(2026, 12, 31))
        self.assertIn("application_dates_not_matched", self.check(candidate=candidate).reasons)

    def test_unchecked_amendment_is_manual_review(self):
        self.assertIn("corrections_not_checked",
                      self.check(latest_corrections_checked=False).reasons)

    def test_withdrawn_notice_is_manual_review(self):
        self.assertIn("withdrawal_unknown_or_confirmed", self.check(withdrawn=True).reasons)

    def test_incomplete_inventory_blocks_reservation(self):
        self.assertIn("incomplete_duplicate_inventory", self.check(inventory_complete=False).reasons)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM publication_identity").fetchone()[0], 0)

    def test_duplicate_different_job_id_is_manual_review(self):
        self.assertEqual(self.check().status, "review_ready_dry_run")
        result = self.check(job_id="different-slug-same-notice")
        self.assertEqual(result.status, "manual_review")
        self.assertIn("identity_reservation:duplicate_hold", result.reasons)

    def test_expired_notice_is_manual_review(self):
        self.assertIn("deadline_expired", self.check(today=date(2027, 1, 1)).reasons)

    def test_pdf_text_mismatch_is_manual_review(self):
        different = make_pdf([
            "Staff Selection Commission", "Advt 12/2026 - Accountant",
            "Application start date: 2026-10-01", "Application last date: 2026-11-30",
        ])
        self.assertIn("post_not_in_notice", self.check(pdf_bytes=different).reasons)


if __name__ == "__main__":
    unittest.main()
