import unittest
from monitor import extract


class ParsingTests(unittest.TestCase):
    source = {'name': 'Test', 'url': 'https://example.gov.in/notices',
              'allowed_domains': ['example.gov.in'], 'pattern': 'recruit|notification'}

    def test_links_resolve_deduplicate_and_keep_nested_text(self):
        html = '<a href="/recruit.pdf"><b>Recruitment</b> notice</a><a href="/recruit.pdf#page=2">Recruitment</a>'
        rows = extract(html, self.source['url'], self.source)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['notice_url'], 'https://example.gov.in/recruit.pdf')
        self.assertEqual(rows[0]['status'], 'needs_review')
        self.assertEqual(rows[0]['notice_id'], extract(html, self.source['url'], self.source)[0]['notice_id'])

    def test_rejects_lookalike_domain_and_unsafe_links(self):
        html = ''.join(f'<a href="{url}">Recruitment</a>' for url in [
            'https://example.gov.in.evil.test/recruit', 'http://example.gov.in/recruit',
            'javascript:alert(1)', 'https://evil.test/recruit'])
        self.assertEqual(extract(html, self.source['url'], self.source), [])

    def test_allows_official_subdomain(self):
        rows = extract('<a href="https://files.example.gov.in/recruit.pdf">Notification</a>',
                       self.source['url'], self.source)
        self.assertEqual(len(rows), 1)


if __name__ == '__main__':
    unittest.main()
