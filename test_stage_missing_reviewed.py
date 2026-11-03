import unittest
from unittest.mock import Mock
from stage_missing_reviewed import stage_missing, admin_inventory

JOB = {
    'job_id': 'sbi-example-2026',
    'official_notification_url': 'https://sbi.bank.in/recruitment-2026.pdf',
}


class StageReviewedTests(unittest.TestCase):
    def test_existing_approved_id_is_not_resubmitted(self):
        send = Mock()
        report = stage_missing([JOB], [{'jobId': JOB['job_id'],
                                        'verificationStatus': 'approved'}], 'import-key', send)
        self.assertEqual(report['submitted'], 0)
        send.assert_not_called()

    def test_existing_pending_id_is_not_resubmitted(self):
        send = Mock()
        report = stage_missing([JOB], [{'job_id': JOB['job_id'],
                                        'verification_status': 'pending'}], 'import-key', send)
        self.assertEqual(report['submitted'], 0)
        send.assert_not_called()

    def test_duplicate_notice_with_other_id_is_held(self):
        send = Mock()
        report = stage_missing([JOB], [{'jobId': 'other-job',
                          'officialNotificationUrl': JOB['official_notification_url']}], 'key', send)
        self.assertEqual(report['held'][0]['reason'], 'same_official_notice_already_exists')
        send.assert_not_called()

    def test_missing_job_submitted_once(self):
        send = Mock(return_value={'inserted': 1, 'updated': 0, 'skipped': 0})
        result = stage_missing([JOB], [], 'key', send)
        self.assertEqual(result['submitted'], 1)
        send.assert_called_once_with([JOB], 'key')

    def test_no_missing_requires_no_import_key(self):
        report = stage_missing([JOB], [{'jobId': JOB['job_id']}], '')
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['submitted'], 0)

    def test_unexpected_update_fails_closed(self):
        send = Mock(return_value={'inserted': 0, 'updated': 1, 'skipped': 0})
        with self.assertRaises(ValueError):
            stage_missing([JOB], [], 'key', send)

    def test_skipped_new_job_is_not_reported_as_success(self):
        send = Mock(return_value={'inserted': 0, 'updated': 0, 'skipped': 1})
        with self.assertRaises(ValueError):
            stage_missing([JOB], [], 'key', send)

    def test_malformed_admin_record_blocks_staging(self):
        send = Mock()
        with self.assertRaises(ValueError):
            stage_missing([JOB], [{'officialNotificationUrl': 'https://sbi.bank.in/other.pdf'}], 'key', send)
        send.assert_not_called()

    def test_unavailable_admin_key_blocks_staging(self):
        with self.assertRaises(ValueError):
            admin_inventory('')


if __name__ == '__main__':
    unittest.main()
