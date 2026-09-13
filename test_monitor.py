import unittest
from monitor import extract
from monitor import check_source, ibps_ca_bundle
from unittest.mock import patch


class ParsingTests(unittest.TestCase):
    source = {'name': 'Test', 'url': 'https://example.gov.in/notices',
              'allowed_domains': ['example.gov.in'], 'pattern': 'recruit|notification'}

    def test_pinned_intermediate_verifies_against_system_roots(self):
        self.assertIn(b'BEGIN CERTIFICATE', ibps_ca_bundle())

    def test_portal_cards_deduplicate_and_require_body_and_deadline(self):
        source = dict(self.source, parser='rajasthan_cards')
        html = '<h6>DIRECT JOINT RECRUITMENT OF JEN 2026</h6><p>(RSSB)</p><button>Apply</button><span>14-Sep-2026</span>'
        rows = extract(html + html + '<h6>Rajasthan Staff Selection Board</h6><p>0 Applications</p>', source['url'], source)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['recruiting_body'], 'RSSB')
        self.assertEqual(rows[0]['observed_deadline'], '14-Sep-2026')
        self.assertEqual(rows[0]['status'], 'needs_review')
        self.assertIn('notification still required', rows[0]['kind'])

    def test_portal_script_and_incomplete_cards_do_not_create_jobs(self):
        source = dict(self.source, parser='rajasthan_cards')
        html = '<h6>Recruitment</h6><p>Apply</p><script>(RSSB) 14-Sep-2026</script>'
        self.assertEqual(extract(html, source['url'], source), [])

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

    @patch('monitor.time.sleep')
    @patch('monitor.fetch_page')
    def test_official_fallback_preserves_failed_attempt(self, fetch, sleep):
        source = dict(self.source, fallback_urls=['https://example.gov.in/'])
        fetch.side_effect = [RuntimeError('HTTP 403'), ('<a href="/recruit.pdf">Notification</a>', source['fallback_urls'][0])]
        rows, report = check_source(source)
        self.assertEqual(len(rows), 1)
        self.assertEqual(report['status'], 'ok')
        self.assertIn('HTTP 403', report['attempts'][0]['error'])

    @patch('monitor.time.sleep')
    @patch('monitor.fetch_page', return_value=('<html></html>', 'https://example.gov.in/'))
    def test_empty_page_is_not_reported_as_success(self, fetch, sleep):
        rows, report = check_source(self.source)
        self.assertEqual(rows, [])
        self.assertEqual(report['status'], 'needs_attention')


if __name__ == '__main__':
    unittest.main()
