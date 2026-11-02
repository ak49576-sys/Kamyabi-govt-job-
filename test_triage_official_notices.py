import unittest
from datetime import date

from triage_official_notices import classify, triage, prepare_review_queue, parse_observed_deadline


TODAY = date(2026, 11, 2)


def notice(title, url='https://ntpc.co.in/recruitment-2026'):
    return {'source': 'NTPC', 'title': title, 'notice_url': url}


class OfficialTriageTests(unittest.TestCase):
    def test_recent_recruitment_is_only_priority_review(self):
        self.assertEqual(classify(notice('Recruitment of Engineer Trainees 2026'), TODAY)[0],
                         'priority_review')

    def test_result_announcement_not_opening(self):
        self.assertEqual(classify(notice('Recruitment Result 2026'), TODAY),
                         ('excluded', 'non_opening_notice'))

    def test_old_recruitment_is_excluded(self):
        self.assertEqual(classify(notice('Recruitment of Apprentice 2024',
                                         'https://ntpc.co.in/recruitment-2024'), TODAY)[0], 'excluded')

    def test_unknown_year_kept_for_review(self):
        self.assertEqual(classify(notice('Recruitment of Apprentice',
                                         'https://ntpc.co.in/careers'), TODAY)[0], 'needs_review')

    def test_generic_navigation_not_priority(self):
        self.assertEqual(classify(notice('View More', 'https://ntpc.co.in/node/266'), TODAY)[0],
                         'needs_review')

    def test_duplicate_urls_removed(self):
        n = notice('Recruitment 2026')
        groups = triage([n, dict(n, title='Recruitment 2026 duplicate')], TODAY)
        self.assertEqual(sum(len(v) for v in groups.values()), 1)

    def test_structured_review_queue_never_marks_notice_publishable(self):
        n = notice('Recruitment of Engineer Trainees 2026')
        groups = triage([n], TODAY)
        prepared = prepare_review_queue(groups)
        self.assertIs(prepared['reviewed'], False)
        self.assertIs(prepared['submission_ready'], False)
        item = prepared['candidates'][0]
        self.assertEqual(item['official_candidate_url'], n['notice_url'])
        self.assertIsNone(item['last_date'])
        self.assertIsNone(item['official_notification_url'])
        self.assertIs(item['publishable'], False)

    def test_review_queue_excludes_results_and_deduplicates(self):
        n = notice('Recruitment of Engineer Trainees 2026')
        groups = triage([n, n, notice('Recruitment Result 2026',
                                     'https://ntpc.co.in/result-2026')], TODAY)
        self.assertEqual(len(prepare_review_queue(groups)['candidates']), 1)

    def test_rajasthan_card_deadline_is_only_unverified_evidence(self):
        n = {'source': 'Rajasthan Recruitment Portal',
             'title': 'Contractual Recruitment 2026',
             'notice_url': 'https://recruitment.rajasthan.gov.in/',
             'observed_deadline': '20-Nov-2026'}
        prepared = prepare_review_queue(triage([n], TODAY))['candidates'][0]
        self.assertEqual(prepared['observed_deadline_iso_unverified'], '2026-11-20')
        self.assertIsNone(prepared['last_date'])
        self.assertIs(prepared['publishable'], False)

    def test_invalid_card_deadline_does_not_become_job_deadline(self):
        self.assertIsNone(parse_observed_deadline('31-Dec-2099x'))
        self.assertIsNone(parse_observed_deadline('31-Feb-2026'))

    def test_invalid_url_excluded(self):
        self.assertEqual(classify(notice('Recruitment 2026', 'http://example.com'), TODAY)[0],
                         'excluded')


if __name__ == '__main__':
    unittest.main()
