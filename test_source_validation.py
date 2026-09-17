import unittest
from unittest.mock import patch

from source_validation import dict_record_lists, official_https, validate


class SourceValidationTests(unittest.TestCase):
    def test_only_official_https_domains_are_allowed(self):
        self.assertTrue(official_https("https://ssc.gov.in/api/test", "ssc"))
        self.assertTrue(official_https("https://www.upsc.gov.in/test", "upsc"))
        self.assertFalse(official_https("http://ssc.gov.in/api/test", "ssc"))
        self.assertFalse(official_https("https://ssc.gov.in.evil.test/api", "ssc"))
        self.assertFalse(official_https("https://user@example.com/api", "ssc"))

    def test_nested_ssc_record_lists_are_detected(self):
        payload = {"result": {"data": [{"id": 1}, {"id": 2}]}, "errors": []}
        lists = dict_record_lists(payload)
        self.assertEqual(max(lists, key=len), [{"id": 1}, {"id": 2}])

    @patch("source_validation.fetch_json")
    def test_ssc_validation_never_publishes(self, fetch):
        fetch.return_value = ({"data": [{"id": 1, "title": "Advertisement"}]},
                              "https://ssc.gov.in/api/admin/5.1/getAllCandiateAdvertisements",
                              "application/json")
        report = validate("ssc")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["records_observed"], 1)
        self.assertFalse(report["publish_attempted"])

    @patch("source_validation.check_source")
    def test_html_failure_is_isolated_and_reported(self, check):
        check.return_value = ([], {"status": "needs_attention", "attempts": [],
                                   "detail": "HTTP 403", "fetched_url": ""})
        report = validate("upsc")
        self.assertEqual(report["status"], "needs_attention")
        self.assertEqual(report["records_observed"], 0)
        self.assertFalse(report["publish_attempted"])


if __name__ == "__main__":
    unittest.main()
