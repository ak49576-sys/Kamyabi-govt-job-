import unittest
from triage_official_results import classify, triage


class ResultTriageTests(unittest.TestCase):
    def row(self, title, url='https://sscnr.nic.in/results/result.pdf'):
        return {'source': 'SSC Northern Region', 'title': title, 'notice_url': url}

    def test_current_and_previous_exam_year_stay_unverified(self):
        for year in (2025, 2026):
            status, _ = classify(self.row(f'Selection Post result {year}'), 2026)
            self.assertEqual(status, 'potential_current_cycle')
        self.assertEqual(classify(self.row('Result 2023'), 2026)[0], 'held')

    def test_excludes_answer_keys_and_generic_navigation(self):
        for title in ('Result answer key 2026', 'Admit card 2026',
                      'Results', 'Selection Post vacancies 2026'):
            self.assertEqual(classify(self.row(title), 2026)[0], 'held')

    def test_deduplicates_urls_and_never_marks_published(self):
        rows = [self.row('Result 2026'), self.row('Result 2026'),
                self.row('Merit list 2024', 'https://sscnr.nic.in/old.pdf')]
        report = triage(rows, 2026)
        self.assertEqual(report['duplicates_removed'], 1)
        self.assertEqual(len(report['potential_current_cycle']), 1)
        self.assertEqual(len(report['held']), 1)
        self.assertFalse(report['potential_current_cycle'][0]['publishable'])
        self.assertIsNone(report['potential_current_cycle'][0]['verified_upload_date'])
        self.assertEqual(report['published'], 0)

    def test_unofficial_scheme_rejected(self):
        self.assertEqual(classify(self.row('Result 2026', 'http://sscnr.nic.in/x'), 2026)[0], 'held')


if __name__ == '__main__':
    unittest.main()
