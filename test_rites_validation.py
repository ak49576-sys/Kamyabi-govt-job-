import unittest

from rites_validation import extract_candidates


class RitesValidationTests(unittest.TestCase):
    def test_keeps_only_official_recruitment_links(self):
        page = """
        <a href="/Upload/Career/notice.pdf">Recruitment notice</a>
        <a href="https://example.com/fake.pdf">Recruitment notice</a>
        <a href="/about">About</a>
        """
        self.assertEqual(
            extract_candidates(page, "https://rites.com/"),
            [{"title": "Recruitment notice", "url": "https://rites.com/Upload/Career/notice.pdf"}],
        )

    def test_rejects_http_and_lookalike_domains(self):
        page = """
        <a href="http://rites.com/Upload/Career/a.pdf">Vacancy</a>
        <a href="https://rites.com.evil.example/a.pdf">Vacancy</a>
        """
        self.assertEqual(extract_candidates(page, "https://rites.com/"), [])


if __name__ == "__main__":
    unittest.main()
