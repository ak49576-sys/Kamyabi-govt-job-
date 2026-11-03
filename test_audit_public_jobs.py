import unittest
from datetime import date
from audit_public_jobs import audit


class JobQualityAuditTests(unittest.TestCase):
    def test_detects_expired_and_unofficial_link(self):
        jobs = [{'job_id': 'old', 'last_date': '2026-10-30',
                 'official_notification_url': 'http://example.com/notice'}]
        result = audit(jobs, date(2026, 11, 3))
        self.assertEqual(result['issue_counts']['expired_still_in_public_feed'], 1)
        self.assertEqual(result['issue_counts']['missing_https_official_notification'], 1)
        self.assertEqual(result['published_or_changed'], 0)

    def test_valid_current_job_has_no_issues(self):
        job = {'jobId': 'active', 'lastDate': '2026-11-20',
               'officialNotificationUrl': 'https://www.ongcindia.com/notice.pdf'}
        self.assertEqual(audit([job], date(2026, 11, 3))['issues'], [])

    def test_detects_duplicate_and_placeholder(self):
        job = {'job_id': 'duplicated', 'last_date': '2099-12-31',
               'official_notification_url': 'https://www.sbi.bank.in/notice'}
        result = audit([job, job], date(2026, 11, 3))
        self.assertEqual(result['issue_counts']['duplicate_public_id'], 2)
        self.assertEqual(result['issue_counts']['placeholder_or_distant_deadline'], 2)

    def test_missing_information_reported_without_writes(self):
        report = audit([{}], date(2026, 11, 3))
        self.assertEqual(report['issues'], [{'job_id': None, 'issue': 'missing_job_id'}])
        self.assertEqual(report['published_or_changed'], 0)


if __name__ == '__main__':
    unittest.main()
