import unittest
from datetime import date
from dataclasses import replace

from official_notice_matcher import (
    Candidate, ExtractedNotice, evaluate_extracted_notice,
)


TODAY = date(2026, 11, 1)
CANDIDATE = Candidate("Staff Selection Commission", "Advt 12/2026", "Junior Engineer",
                      date(2026, 10, 1), date(2026, 11, 30))
NOTICE = ExtractedNotice(
    "Staff Selection Commission. Advt 12/2026. Junior Engineer. "
    "Applications open 01-10-2026 and close 30-11-2026.",
    True, True, True, False,
)


class NoticeMatcherTests(unittest.TestCase):
    def check(self, candidate=CANDIDATE, notice=NOTICE):
        return evaluate_extracted_notice(candidate, notice, today=TODAY)

    def test_even_matching_text_is_not_auto_approval(self):
        self.assertEqual(self.check().status, "hold")
        self.assertIn("dates_require_structured_extraction", self.check().reasons)

    def test_fake_source(self):
        self.assertIn("official_source_unconfirmed",
                      self.check(notice=replace(NOTICE, official_source_confirmed=False)).reasons)

    def test_scanned_unreadable_pdf(self):
        reasons = self.check(notice=replace(NOTICE, text=None, extraction_complete=False)).reasons
        self.assertIn("content_missing_or_incomplete", reasons)

    def test_wrong_advertisement(self):
        self.assertIn("advertisement_not_in_notice",
                      self.check(candidate=replace(CANDIDATE, advertisement_number="Advt 99/2026")).reasons)

    def test_advertisement_boundary_prevents_substring(self):
        self.assertIn("advertisement_not_in_notice",
                      self.check(candidate=replace(CANDIDATE, advertisement_number="12/202")).reasons)

    def test_wrong_post(self):
        self.assertIn("post_not_in_notice",
                      self.check(candidate=replace(CANDIDATE, post_name="Accountant")).reasons)

    def test_wrong_issuer(self):
        self.assertIn("issuer_not_in_notice",
                      self.check(candidate=replace(CANDIDATE, recruiting_body="Railway Board")).reasons)

    def test_withdrawn(self):
        self.assertIn("withdrawal_unknown_or_confirmed",
                      self.check(notice=replace(NOTICE, withdrawn=True)).reasons)

    def test_unknown_withdrawal(self):
        self.assertIn("withdrawal_unknown_or_confirmed",
                      self.check(notice=replace(NOTICE, withdrawn=None)).reasons)

    def test_unchecked_correction(self):
        self.assertIn("corrections_not_checked",
                      self.check(notice=replace(NOTICE, correction_chain_checked=False)).reasons)

    def test_expired_job(self):
        self.assertIn("deadline_expired",
                      self.check(candidate=replace(CANDIDATE, last_date=date(2026, 10, 31))).reasons)

    def test_reversed_dates(self):
        self.assertIn("date_order_invalid",
                      self.check(candidate=replace(CANDIDATE, start_date=date(2026, 12, 1))).reasons)

    def test_blank_advertisement_not_accepted(self):
        self.assertIn("advertisement_not_in_notice",
                      self.check(candidate=replace(CANDIDATE, advertisement_number="")).reasons)


if __name__ == "__main__":
    unittest.main()
