import unittest
from datetime import date
from review_official_pdfs import extract_evidence, official_pdf, review


class OfficialPdfEvidenceTests(unittest.TestCase):
    def test_official_domain_and_https_required(self):
        domains = {'bhel.com'}
        self.assertTrue(official_pdf('https://www.bhel.com/jobs/notice.pdf', domains))
        self.assertFalse(official_pdf('https://bhel.com.evil.test/jobs/notice.pdf', domains))
        self.assertFalse(official_pdf('http://bhel.com/jobs/notice.pdf', domains))
        self.assertFalse(official_pdf('https://bhel.com/jobs/html', domains))

    def test_possible_closing_date_is_only_evidence(self):
        evidence = extract_evidence('Graduate Engineer Recruitment. Last date 20/11/2026. Eligibility B.Tech and Diploma.')
        self.assertEqual(evidence['possible_closing_dates'][0]['observed'], '20/11/2026')
        self.assertFalse(evidence['publication_approved'])
        self.assertFalse(evidence['vacancy_count_verified'])

    def test_review_never_publishes(self):
        sources = [{'name': 'BHEL', 'allowed_domains': ['bhel.com']}]
        notices = [{'source': 'BHEL', 'title': 'Recruitment 2026',
                    'notice_url': 'https://bhel.com/notice.pdf'}]
        result = review(notices, sources, fetch=lambda url: 'Closing date 30-Nov-2026. ITI')
        self.assertFalse(result['submission_ready'])
        self.assertEqual(result['published'], 0)
        self.assertFalse(result['documents'][0]['publishable'])
        self.assertEqual(result['documents'][0]['status'], 'text_extracted')

    def test_recent_recruitment_notice_is_reviewed_before_old_link(self):
        sources = [{'name': 'BHEL', 'allowed_domains': ['bhel.com']}]
        notices = [
            {'source': 'BHEL', 'title': 'Result 2024',
             'notice_url': 'https://bhel.com/old.pdf'},
            {'source': 'BHEL', 'title': 'Engineer Recruitment 2026',
             'notice_url': 'https://bhel.com/current.pdf'},
        ]
        examined = []
        def fetch(url):
            examined.append(url)
            return 'Closing date 20-Nov-2026'
        result = review(notices, sources, max_documents=1, fetch=fetch,
                        today=date(2026, 11, 3))
        self.assertEqual(examined, ['https://bhel.com/current.pdf'])
        self.assertFalse(result['submission_ready'])

    def test_unavailable_pdf_is_reported_without_import(self):
        sources = [{'name': 'BHEL', 'allowed_domains': ['bhel.com']}]
        notices = [{'source': 'BHEL', 'notice_url': 'https://bhel.com/notice.pdf'}]
        def blocked(url):
            raise ValueError('not reachable')
        result = review(notices, sources, fetch=blocked)
        self.assertEqual(result['documents'][0]['status'], 'unavailable')
        self.assertEqual(result['published'], 0)


if __name__ == '__main__':
    unittest.main()
