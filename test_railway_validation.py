import unittest
from unittest.mock import patch

from railway_validation import extract_candidates, validate


class RailwayValidationTests(unittest.TestCase):
    def test_only_official_railway_notice_links_are_retained(self):
        page = """<a href="/cen-01-2026.pdf">CEN 01/2026 Notification</a>
                  <a href="https://fake-rrb.example/jobs">Railway Recruitment</a>
                  <a href="/about">About</a>"""
        links = extract_candidates(page, "https://rrb.indianrailways.gov.in/")
        self.assertEqual(links, [{
            "title": "CEN 01/2026 Notification",
            "url": "https://rrb.indianrailways.gov.in/cen-01-2026.pdf",
        }])

    @patch("railway_validation.fetch_html")
    def test_portal_identity_and_scope_are_required(self, fetch):
        fetch.return_value = (
            "<html>Government of India, Ministry of Railways, Railway Recruitment Board</html>",
            "https://rrb.indianrailways.gov.in/",
            "text/html",
        )
        report = validate()
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["portal_verified"])
        self.assertEqual(report["scope_category"], "railways")
        self.assertFalse(report["publish_attempted"])

    @patch("railway_validation.fetch_html")
    def test_generic_page_fails_closed(self, fetch):
        fetch.return_value = (
            "<html>General careers portal</html>",
            "https://rrb.indianrailways.gov.in/",
            "text/html",
        )
        report = validate()
        self.assertEqual(report["status"], "needs_attention")
        self.assertFalse(report["portal_verified"])
        self.assertFalse(report["publish_attempted"])

    @patch("railway_validation.fetch_html")
    def test_access_failure_is_reported_without_publishing(self, fetch):
        fetch.side_effect = RuntimeError("timeout")
        report = validate()
        self.assertEqual(report["status"], "needs_attention")
        self.assertEqual(report["pages_fetched"], 0)
        self.assertEqual(len(report["attempts"]), 3)
        self.assertFalse(report["publish_attempted"])


if __name__ == "__main__":
    unittest.main()
