import unittest
from unittest.mock import Mock
from verify_publications import verify


class PublicApprovalVerificationTests(unittest.TestCase):
    def test_no_approvals_needs_no_public_request(self):
        fetch = Mock()
        report = verify([], fetch=fetch)
        self.assertEqual(report['status'], 'ok')
        fetch.assert_not_called()

    def test_visible_approved_job(self):
        report = verify(['sbi-2026'], fetch=lambda: {'sbi-2026': {'job_id': 'sbi-2026'}})
        self.assertEqual(report['visible'], ['sbi-2026'])
        self.assertEqual(report['missing'], [])

    def test_missing_approval_is_reported(self):
        sleep = Mock()
        report = verify(['sbi-2026'], fetch=lambda: {}, wait=sleep, attempts=3)
        self.assertEqual(report['status'], 'missing_public_jobs')
        self.assertEqual(report['missing'], ['sbi-2026'])
        self.assertEqual(sleep.call_count, 2)

    def test_publication_after_retry(self):
        fetch = Mock(side_effect=[{}, {'sbi-2026': {}}])
        report = verify(['sbi-2026'], fetch=fetch, wait=lambda seconds: None)
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(fetch.call_count, 2)


if __name__ == '__main__':
    unittest.main()
