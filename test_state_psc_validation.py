import unittest
from unittest.mock import patch

from state_psc_validation import candidate_links, official_https, validate


class StatePscValidationTests(unittest.TestCase):
    def test_official_domain_allowlist(self):
        self.assertTrue(official_https("https://rpsc.rajasthan.gov.in/advertisements",
                                       ("rpsc.rajasthan.gov.in",)))
        self.assertTrue(official_https("https://www.jpsc.gov.in/file.pdf", ("jpsc.gov.in",)))
        self.assertFalse(official_https("http://psc.wb.gov.in/file", ("psc.wb.gov.in",)))
        self.assertFalse(official_https("https://rpsc.rajasthan.gov.in.evil.test/file",
                                        ("rpsc.rajasthan.gov.in",)))

    def test_candidate_links_are_official_and_recruitment_related(self):
        page = """<a href="/notice.pdf">Recruitment Advertisement</a>
                  <a href="https://evil.test/fake.pdf">Vacancy</a>
                  <a href="/about">About</a>"""
        links = candidate_links(page, "https://psc.wb.gov.in/", ("psc.wb.gov.in",))
        self.assertEqual(links, [{
            "title": "Recruitment Advertisement",
            "url": "https://psc.wb.gov.in/notice.pdf",
        }])

    @patch("state_psc_validation.fetch_html")
    def test_source_failures_are_isolated_and_never_publish(self, fetch):
        fetch.side_effect = RuntimeError("HTTP 403")
        report = validate("rpsc")
        self.assertEqual(report["status"], "needs_attention")
        self.assertEqual(report["candidate_links"], 0)
        self.assertFalse(report["publish_attempted"])

    @patch("state_psc_validation.fetch_html")
    def test_success_is_candidate_discovery_not_job_creation(self, fetch):
        fetch.return_value = (
            '<a href="/advertisement.pdf">Advertisement 01/2026</a>',
            "https://rpsc.rajasthan.gov.in/advertisements",
            "text/html",
        )
        report = validate("rpsc")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["candidate_links"], 1)
        self.assertFalse(report["publish_attempted"])
        self.assertIn("no vacancy", report["note"].lower())


if __name__ == "__main__":
    unittest.main()
