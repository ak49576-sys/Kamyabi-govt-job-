import sqlite3
import unittest
from dataclasses import replace
from datetime import date

from fast_track_reservation import create_schema, reserve_notice_identity
from fast_track_review import OfficialPageEvidence, review_official_page_fast_track
from official_notice_matcher import Candidate


class FastTrackReviewTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        create_schema(self.connection)
        self.candidate = Candidate("Staff Selection Commission", "Advt 12/2026",
                                   "Junior Engineer", date(2026, 10, 1), date(2026, 11, 30))
        self.evidence = OfficialPageEvidence(
            recruiting_body="Staff Selection Commission", advertisement_number="Advt 12/2026",
            post_name="Junior Engineer", start_date=date(2026, 10, 1),
            last_date=date(2026, 11, 30),
            page_text=("Staff Selection Commission | Advt 12/2026 | Junior Engineer | "
                       "Apply 01/10/2026 to 30/11/2026"),
            checked_on=date(2026, 11, 1), verified_retrieval=True,
            employer_type="central_government", employer_type_verified=True,
        )
        self.args = dict(
            job_id="ssc-junior-engineer-2026", candidate=self.candidate,
            category="central_government", recruitment_cycle="2026", evidence=self.evidence,
            url_chain=["https://ssc.gov.in/jobs/je-2026"], allowed_domains=("ssc.gov.in",),
            resolve_dns=lambda _: ("8.8.8.8",), inventory_complete=True,
            existing_duplicate=False,
            reserve_notice_identity=lambda **kwargs: reserve_notice_identity(self.connection, **kwargs),
            today=date(2026, 11, 1),
        )

    def tearDown(self):
        self.connection.close()

    def review(self, **overrides):
        return review_official_page_fast_track(**{**self.args, **overrides})

    def count(self):
        return self.connection.execute("SELECT COUNT(*) FROM safety_fast_track_reservations").fetchone()[0]

    def test_official_html_without_pdf_is_dry_run_eligible_not_published(self):
        result = self.review()
        self.assertEqual(result.status, "fast_track_eligible_dry_run")
        self.assertEqual(self.count(), 1)
        self.assertEqual(len(result.evidence_sha256), 64)

    def test_repeated_same_job_is_idempotent(self):
        self.assertEqual(self.review().status, "fast_track_eligible_dry_run")
        self.assertEqual(self.review().status, "fast_track_eligible_dry_run")
        self.assertEqual(self.count(), 1)

    def test_unverified_html_and_apify_metadata_are_held(self):
        result = self.review(evidence=replace(self.evidence, verified_retrieval=False))
        self.assertIn("official_page_not_independently_verified", result.reasons)
        self.assertEqual(self.count(), 0)

    def test_wrong_official_host_is_held(self):
        result = self.review(url_chain=["https://ssc.gov.in.attacker.invalid/job"])
        self.assertEqual(result.status, "manual_review")
        self.assertTrue(any(r.startswith("unsafe_official_url:") for r in result.reasons))
        self.assertEqual(self.count(), 0)

    def test_private_bank_misclassification_is_held(self):
        result = self.review(evidence=replace(self.evidence, employer_type="private_sector"))
        self.assertIn("government_psu_classification_unverified", result.reasons)

    def test_missing_independent_classification_is_held(self):
        result = self.review(evidence=replace(self.evidence, employer_type_verified=False))
        self.assertIn("government_psu_classification_unverified", result.reasons)

    def test_psu_scope_is_supported(self):
        result = self.review(category="psu", evidence=replace(self.evidence, employer_type="psu"))
        self.assertEqual(result.status, "fast_track_eligible_dry_run")

    def test_expired_deadline_is_held(self):
        result = self.review(today=date(2026, 12, 1))
        self.assertIn("deadline_expired", result.reasons)
        self.assertEqual(self.count(), 0)

    def test_mismatched_official_deadline_is_held(self):
        result = self.review(evidence=replace(self.evidence, last_date=date(2026, 11, 29)))
        self.assertIn("application_dates_mismatch", result.reasons)

    def test_post_not_visible_on_official_page_is_held(self):
        result = self.review(evidence=replace(self.evidence, page_text="Staff Selection Commission Advt 12/2026"))
        self.assertIn("post_name_missing_from_official_page", result.reasons)

    def test_old_snapshot_is_held(self):
        result = self.review(evidence=replace(self.evidence, checked_on=date(2026, 10, 31)))
        self.assertIn("official_page_not_checked_today", result.reasons)

    def test_known_withdrawal_is_held(self):
        result = self.review(evidence=replace(self.evidence, withdrawn=True))
        self.assertIn("notice_withdrawn", result.reasons)

    def test_incomplete_inventory_is_held_even_with_verified_notice(self):
        result = self.review(inventory_complete=False)
        self.assertIn("incomplete_duplicate_inventory", result.reasons)
        self.assertEqual(self.count(), 0)

    def test_unknown_duplicate_status_is_held(self):
        result = self.review(existing_duplicate=None)
        self.assertIn("existing_or_unchecked_duplicate", result.reasons)

    def test_existing_duplicate_is_held(self):
        result = self.review(existing_duplicate=True)
        self.assertIn("existing_or_unchecked_duplicate", result.reasons)

    def test_same_advertisement_different_job_id_is_held(self):
        self.review()
        result = self.review(job_id="other-slug")
        self.assertEqual(result.status, "manual_review")
        self.assertIn("duplicate_reservation:duplicate_hold", result.reasons)

    def test_different_advertisement_same_official_url_is_held(self):
        self.review()
        candidate = replace(self.candidate, advertisement_number="Advt 13/2026")
        evidence = replace(self.evidence, advertisement_number="Advt 13/2026",
                           page_text="Staff Selection Commission Advt 13/2026 Junior Engineer")
        result = self.review(job_id="other-slug", candidate=candidate, evidence=evidence)
        self.assertIn("duplicate_reservation:duplicate_hold", result.reasons)

    def test_missing_reservation_is_held(self):
        result = self.review(reserve_notice_identity=lambda **kw: object())
        self.assertIn("duplicate_reservation:unknown", result.reasons)


if __name__ == "__main__":
    unittest.main()
