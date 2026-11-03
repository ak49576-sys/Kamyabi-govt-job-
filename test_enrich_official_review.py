import unittest
from enrich_official_review import enrich


class EvidenceEnrichmentTests(unittest.TestCase):
    def test_pdf_evidence_is_only_unverified(self):
        queue = {'candidates': [{'source': 'BHEL', 'official_candidate_url': 'https://bhel.com/notice.pdf',
                                 'reviewed': False, 'publishable': False}]}
        pdf = {'documents': [{'official_pdf_url': 'https://bhel.com/notice.pdf',
                              'status': 'text_extracted',
                              'possible_closing_dates': [{'observed': '20/11/2026'}],
                              'qualification_keywords': ['ITI']}]}
        report = enrich(queue, pdf)
        item = report['candidates'][0]
        self.assertTrue(item['pdf_text_extracted'])
        self.assertEqual(item['possible_closing_dates_unverified'][0]['observed'], '20/11/2026')
        self.assertFalse(item['publishable'])
        self.assertFalse(item['reviewed'])
        self.assertIsNone(item['job_id'])
        self.assertFalse(report['submission_ready'])

    def test_missing_or_unavailable_pdf_cannot_create_facts(self):
        queue = {'candidates': [{'official_candidate_url': 'https://bhel.com/notice.pdf'}]}
        pdf = {'documents': [{'official_pdf_url': 'https://bhel.com/notice.pdf', 'status': 'unavailable',
                              'possible_closing_dates': [{'observed': '20/11/2026'}]}]}
        item = enrich(queue, pdf)['candidates'][0]
        self.assertEqual(item['possible_closing_dates_unverified'], [])
        self.assertFalse(item['pdf_text_extracted'])


if __name__ == '__main__':
    unittest.main()
