import unittest
from enrich_official_review import enrich, date_suggestions


class EvidenceEnrichmentTests(unittest.TestCase):
    def test_coherent_dates_are_suggestions_only(self):
        item = {'possible_opening_dates_unverified': [{'observed': '02-Nov-2026'}],
                'possible_closing_dates_unverified': [{'observed': '25/11/2026'}]}
        dates = date_suggestions(item)
        self.assertEqual(dates['application_start_date'], '2026-11-02')
        self.assertEqual(dates['application_last_date'], '2026-11-25')
        self.assertIn('unverified', dates['status'])

    def test_conflicting_or_inverted_dates_are_held(self):
        item = {'possible_opening_dates_unverified': [{'observed': '26-Nov-2026'}],
                'possible_closing_dates_unverified': [{'observed': '25-Nov-2026'}]}
        self.assertIsNone(date_suggestions(item)['application_last_date'])
        item['possible_opening_dates_unverified'].append({'observed': '01-Nov-2026'})
        self.assertIsNone(date_suggestions(item)['application_start_date'])

    def test_pdf_evidence_is_only_unverified(self):
        queue = {'candidates': [{'source': 'BHEL', 'official_candidate_url': 'https://bhel.com/notice.pdf',
                                 'reviewed': False, 'publishable': False}]}
        pdf = {'documents': [{'official_pdf_url': 'https://bhel.com/notice.pdf',
                              'status': 'text_extracted',
                              'possible_closing_dates': [{'observed': '20/11/2026'}],
                              'possible_opening_dates': [{'observed': '01/11/2026'}],
                              'qualification_keywords': ['ITI']}]}
        report = enrich(queue, pdf)
        item = report['candidates'][0]
        self.assertTrue(item['pdf_text_extracted'])
        self.assertEqual(item['possible_opening_dates_unverified'][0]['observed'], '01/11/2026')
        self.assertEqual(item['possible_closing_dates_unverified'][0]['observed'], '20/11/2026')
        self.assertFalse(item['publishable'])
        self.assertFalse(item['reviewed'])
        self.assertIsNone(item['job_id'])
        self.assertFalse(report['submission_ready'])

    def test_prioritize_pdf_dates_and_report_all_missing_fields(self):
        queue = {'candidates': [
            {'source': 'BHEL', 'official_candidate_url': 'https://bhel.com/unknown.pdf'},
            {'source': 'BHEL', 'official_candidate_url': 'https://bhel.com/current.pdf'}]}
        pdf = {'documents': [{'official_pdf_url': 'https://bhel.com/current.pdf',
                              'status': 'text_extracted',
                              'possible_closing_dates': [{'observed': '25-Nov-2026'}]}]}
        report = enrich(queue, pdf)
        self.assertEqual(report['candidates'][0]['official_candidate_url'],
                         'https://bhel.com/current.pdf')
        self.assertEqual(report['ready_for_import'], 0)
        self.assertEqual(report['missing_field_counts']['qualification'], 2)
        self.assertIn('application_start_date', report['candidates'][0]['missing_required_fields'])
        self.assertFalse(report['submission_ready'])

    def test_missing_or_unavailable_pdf_cannot_create_facts(self):
        queue = {'candidates': [{'official_candidate_url': 'https://bhel.com/notice.pdf'}]}
        pdf = {'documents': [{'official_pdf_url': 'https://bhel.com/notice.pdf', 'status': 'unavailable',
                              'possible_closing_dates': [{'observed': '20/11/2026'}]}]}
        item = enrich(queue, pdf)['candidates'][0]
        self.assertEqual(item['possible_closing_dates_unverified'], [])
        self.assertFalse(item['pdf_text_extracted'])


    def test_current_pdf_dates_rank_ahead_of_expired_and_ambiguous(self):
        from datetime import date
        queue = {'candidates': [
            {'official_candidate_url': 'https://bhel.com/expired.pdf'},
            {'official_candidate_url': 'https://bhel.com/current.pdf'},
            {'official_candidate_url': 'https://bhel.com/unknown.pdf'}]}
        pdf = {'documents': [
            {'official_pdf_url': 'https://bhel.com/expired.pdf',
             'status': 'text_extracted',
             'possible_opening_dates': [{'observed': '01-Nov-2025'}],
             'possible_closing_dates': [{'observed': '15-Nov-2025'}]},
            {'official_pdf_url': 'https://bhel.com/current.pdf',
             'status': 'text_extracted',
             'possible_opening_dates': [{'observed': '01-Nov-2026'}],
             'possible_closing_dates': [{'observed': '20-Nov-2026'}]}]}
        report = enrich(queue, pdf, today=date(2026, 11, 3))
        ordered = report['candidates']
        self.assertEqual(ordered[0]['official_candidate_url'], 'https://bhel.com/current.pdf')
        self.assertEqual(ordered[-1]['priority_reason'], 'pdf_deadline_expired')
        self.assertEqual(report['current_coherent_pdf_date_candidates'], 1)
        self.assertEqual(report['expired_date_candidates_held'], 1)
        self.assertFalse(report['submission_ready'])


if __name__ == '__main__':
    unittest.main()
