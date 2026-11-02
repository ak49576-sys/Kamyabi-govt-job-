import unittest

from correct_ongc_apprentice import JOB_ID, EXPECTED, PDF, correct


class CorrectionTests(unittest.TestCase):
    def test_mismatched_record_is_held_without_writes(self):
        calls = []
        row = {'job_id': JOB_ID, **EXPECTED, 'last_date': '2026-11-06'}
        result = correct('fake-key', request=lambda *a, **k: calls.append((a, k)),
                         find=lambda *a: row)
        self.assertEqual(result['status'], 'held')
        self.assertFalse(calls)

    def test_missing_record_is_held(self):
        result = correct('fake-key', find=lambda *a: None)
        self.assertEqual(result['status'], 'held')

    def test_two_phase_update_requires_pending_confirmation(self):
        calls = []
        row = {'job_id': JOB_ID, **EXPECTED}
        pending = {'job_id': JOB_ID, 'last_date': '2026-11-19',
                   'official_notification_url': PDF}
        def find(key, status):
            return row if status == 'approved' else pending
        def request(*args, **kwargs):
            calls.append(kwargs.get('body'))
            return {'ok': True, 'job_id': JOB_ID}
        with self.assertRaises(ValueError):
            correct('fake-key', request=request, find=find)
        self.assertEqual(len(calls), 1)

    def test_success_requires_new_approved_date(self):
        calls = []
        row = {'job_id': JOB_ID, **EXPECTED}
        pending = {'job_id': JOB_ID, 'last_date': '2026-11-20',
                   'official_notification_url': PDF}
        final = {'job_id': JOB_ID, 'last_date': '2026-11-20'}
        approved_calls = [row, final]
        def find(key, status):
            return approved_calls.pop(0) if status == 'approved' else pending
        def request(*args, **kwargs):
            calls.append(kwargs['body'])
            return {'ok': True, 'job_id': JOB_ID,
                    'verification_status': 'approved'}
        result = correct('fake-key', request=request, find=find)
        self.assertEqual(result['status'], 'corrected_and_approved')
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['fields']['lastDate'], '2026-11-20')
        self.assertEqual(calls[1]['fields']['verificationStatus'], 'approved')


if __name__ == '__main__':
    unittest.main()
