import unittest
from datetime import date
from smart_publish_preview import build_report
from test_smart_publish_gate import JOB, EVIDENCE

class SmartPublishingPreviewTests(unittest.TestCase):
    def document(self, complete=False):
        return {
            "candidates": [JOB],
            "existing_records": [],
            "evidence_by_job_id": {JOB["job_id"]: EVIDENCE},
            "inventory_complete": complete,
        }

    def test_unverified_inventory_holds_every_job(self):
        report = build_report(self.document(), date(2026, 11, 1))
        self.assertEqual(report["counts"]["eligible_for_dry_run"], 0)
        self.assertEqual(report["counts"]["manual_review"], 1)
        self.assertFalse(report["publication_enabled"])
        self.assertEqual(report["published"], 0)
        self.assertEqual(report["submitted"], 0)

    def test_complete_inventory_only_produces_preview(self):
        report = build_report(self.document(True), date(2026, 11, 1))
        self.assertEqual(report["counts"]["eligible_for_dry_run"], 1)
        self.assertEqual(report["mode"], "dry_run_only")
        self.assertFalse(report["publication_enabled"])

    def test_pending_duplicate_is_not_eligible(self):
        doc = self.document(True)
        doc["existing_records"] = [{**JOB, "status": "pending"}]
        report = build_report(doc, date(2026, 11, 1))
        self.assertEqual(report["counts"]["duplicate_or_update_review"], 1)

    def test_bad_input_fails_closed(self):
        for doc in ({}, {"candidates": []}, {"candidates": [{}], "existing_records": [],
                                        "evidence_by_job_id": {}}):
            with self.assertRaises(ValueError):
                build_report(doc, date(2026, 11, 1))

    def test_untrusted_flag_does_not_count_as_true(self):
        doc = self.document("yes")
        self.assertEqual(build_report(doc, date(2026, 11, 1))["counts"]["manual_review"], 1)

if __name__ == "__main__":
    unittest.main()
