import unittest
from datetime import date

from triage_official_notices import classify, triage


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

    def test_invalid_url_excluded(self):
        self.assertEqual(classify(notice('Recruitment 2026', 'http://example.com'), TODAY)[0],
                         'excluded')


if __name__ == '__main__':
    unittest.main()
