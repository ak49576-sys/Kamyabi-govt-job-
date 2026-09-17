import unittest
from datetime import date

from ssc_pipeline import build_report, normalise_record, parse_date


class SscPipelineTests(unittest.TestCase):
    def test_date_parsing_does_not_infer(self):
        self.assertEqual(parse_date("21/09/2026"), "2026-09-21")
        self.assertEqual(parse_date("2026-09-21T18:00:00"), "2026-09-21")
        self.assertIsNone(parse_date("September 2026"))
        self.assertIsNone(parse_date("coming soon"))

    def test_valid_record_gets_stable_id(self):
        result = normalise_record({
            "id": 42,
            "title": "Combined Recruitment",
            "closingDate": "21/09/2026",
            "notificationUrl": "https://ssc.gov.in/api/attachment/uploads/masterData/Notice.pdf",
            "vacancyCount": 10,
        }, today=date(2026, 9, 17))
        self.assertTrue(result["eligible_for_review"])
        self.assertEqual(result["candidate"]["job_id"], "ssc-advt-42")
        self.assertEqual(result["candidate"]["last_date"], "2026-09-21")
        self.assertEqual(result["candidate"]["vacancy_count"], 10)

    def test_expired_or_external_evidence_is_not_eligible(self):
        result = normalise_record({
            "id": "CGL-2026",
            "title": "CGL",
            "lastDate": "2026-04-19",
            "notificationUrl": "https://example.com/notice.pdf",
        }, today=date(2026, 9, 17))
        self.assertFalse(result["eligible_for_review"])
        self.assertIn("application deadline has passed", result["reasons"])
        self.assertIn("missing record-specific official SSC notification URL", result["reasons"])

    def test_duplicates_are_reported_and_never_submitted(self):
        payload = {"data": [
            {"id": 7, "title": "One"},
            {"id": 7, "title": "Duplicate"},
        ]}
        report = build_report(payload, today=date(2026, 9, 17))
        self.assertEqual(report["fetched"], 2)
        self.assertEqual(report["duplicates"], 1)
        self.assertEqual(report["submitted"], 0)
        self.assertFalse(report["publish_attempted"])

    def test_missing_fields_are_explicitly_held_for_review(self):
        result = normalise_record({"id": 9, "title": "Notice"}, today=date(2026, 9, 17))
        self.assertFalse(result["eligible_for_review"])
        self.assertIn("missing or unparseable application deadline", result["reasons"])
        self.assertIn("missing record-specific official SSC notification URL", result["reasons"])


if __name__ == "__main__":
    unittest.main()
