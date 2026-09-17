import unittest
from unittest.mock import patch

from ncs_validation import validate


class NcsValidationTests(unittest.TestCase):
    @patch("ncs_validation.fetch_html")
    def test_government_listing_is_verified_without_inference(self, fetch):
        fetch.return_value = (
            "<html><body>JOBS IN GOVERNMENT SECTOR</body></html>",
            "https://ncs.gov.in/job-listing?isGovernmentJob=true",
            "text/html",
        )
        report = validate()
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["government_filter_verified"])
        self.assertIsNone(report["records_observed"])
        self.assertFalse(report["publish_attempted"])

    @patch("ncs_validation.fetch_html")
    def test_generic_page_is_not_treated_as_government_jobs(self, fetch):
        fetch.return_value = (
            "<html><body>Find domestic jobs</body></html>",
            "https://ncs.gov.in/",
            "text/html",
        )
        report = validate()
        self.assertEqual(report["status"], "needs_attention")
        self.assertFalse(report["government_filter_verified"])
        self.assertFalse(report["publish_attempted"])

    @patch("ncs_validation.fetch_html")
    def test_access_failure_is_reported_and_never_publishes(self, fetch):
        fetch.side_effect = RuntimeError("HTTP 403")
        report = validate()
        self.assertEqual(report["status"], "needs_attention")
        self.assertIsNone(report["records_observed"])
        self.assertFalse(report["publish_attempted"])


if __name__ == "__main__":
    unittest.main()
