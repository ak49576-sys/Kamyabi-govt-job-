import unittest
import json
from io import BytesIO
from datetime import date
from pathlib import Path
from unittest.mock import patch

from auto_publish import admin_pending, eligible, run


JOB = {
    'job_id': 'sbi-review-test',
    'title': 'SBI Specialist Cadre Officers',
    'recruiting_body': 'State Bank of India',
    'source_url': 'https://sbi.bank.in/web/careers/Current-openings',
    'official_notification_url': 'https://sbi.bank.in/documents/notice.pdf',
    'last_date': '2026-11-23',
    'application_start_date': '2026-11-02',
    'application_last_date': '2026-11-23',
}
PENDING = [{
    'jobId': 'sbi-review-test',
    'title': JOB['title'],
    'officialNotificationUrl': JOB['official_notification_url'],
    'verificationStatus': 'pending',
}]


class ApprovalTests(unittest.TestCase):
    def test_basic_match_is_eligible(self):
        self.assertEqual(eligible(JOB, PENDING, date(2026, 11, 2)),
                         (True, 'basic_checks_passed'))

    def test_placeholder_2099_is_held(self):
        placeholder = {**JOB, 'last_date': '2099-12-31',
                       'application_last_date': '2099-12-31'}
        self.assertEqual(eligible(placeholder, PENDING, date(2026, 11, 2))[1],
                         'placeholder_or_distant_deadline')

    def test_plausible_future_deadline_remains_eligible(self):
        upcoming = {**JOB, 'last_date': '2027-04-30',
                    'application_last_date': '2027-04-30'}
        self.assertEqual(eligible(upcoming, PENDING, date(2026, 11, 2)),
                         (True, 'basic_checks_passed'))

    def test_expired_is_held(self):
        self.assertEqual(eligible(JOB, PENDING, date(2026, 11, 24))[1], 'expired')

    def test_not_pending_is_held(self):
        self.assertEqual(eligible(JOB, [], date(2026, 11, 2))[1], 'not_in_pending_queue')

    def test_changed_pending_details_are_held(self):
        changed = [{**PENDING[0], 'officialNotificationUrl': 'https://sbi.bank.in/other'}]
        self.assertEqual(eligible(JOB, changed, date(2026, 11, 2))[1],
                         'pending_official_url_differs')

    def test_duplicate_official_notice_is_held(self):
        pending = PENDING + [{**PENDING[0], 'jobId': 'another-sbi-job'}]
        self.assertEqual(eligible(JOB, pending, date(2026, 11, 2))[1], 'possible_duplicate')

    def test_unofficial_url_is_held(self):
        wrong = {**JOB, 'official_notification_url': 'https://example.com/notice.pdf'}
        self.assertEqual(eligible(wrong, PENDING, date(2026, 11, 2))[1], 'unofficial_url')

    @patch('auto_publish.load_queue', return_value=([JOB], []))
    def test_preview_never_approves(self, load):
        approved = []
        result = run(Path('.'), key='test', publish=False, today=date(2026, 11, 2),
                     get_pending=lambda key: PENDING,
                     approve_job=lambda *args: approved.append(args))
        self.assertEqual(result.get('eligible_preview'), ['sbi-review-test'])
        self.assertEqual(approved, [])

    @patch('auto_publish.load_queue', return_value=([JOB], []))
    def test_publish_only_eligible(self, load):
        approved = []
        result = run(Path('.'), key='test', publish=True, today=date(2026, 11, 2),
                     get_pending=lambda key: PENDING,
                     approve_job=lambda job_id, key: approved.append(job_id))
        self.assertEqual(approved, ['sbi-review-test'])
        self.assertEqual(result['approved'], approved)

    @patch('auto_publish.load_queue', return_value=([JOB], []))
    def test_missing_key_never_approves(self, load):
        result = run(Path('.'), key='', publish=True, today=date(2026, 11, 2))
        self.assertEqual(result['status'], 'configuration_required')
        self.assertEqual(result['approved'], [])


class FakeResponse:
    status = 200
    headers = {'Content-Type': 'application/json'}

    def __init__(self, payload):
        self.body = BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.body.read(size)


class FakeOpener:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.urls = []

    def open(self, request, timeout):
        self.urls.append(request.full_url)
        return FakeResponse(next(self.pages))


class PendingInventoryTests(unittest.TestCase):
    def test_multiple_pages_are_read_before_approval(self):
        opener = FakeOpener([
            {'total': 2, 'jobs': [{'jobId': 'one'}]},
            {'total': 2, 'jobs': [{'jobId': 'two'}]},
        ])
        rows = admin_pending('key', opener)
        self.assertEqual([r['jobId'] for r in rows], ['one', 'two'])
        self.assertIn('offset=1', opener.urls[1])

    def test_missing_page_fails_closed(self):
        opener = FakeOpener([{'total': 2, 'jobs': [{'jobId': 'one'}]},
                             {'total': 2, 'jobs': []}])
        with self.assertRaises(ValueError):
            admin_pending('key', opener)

    def test_duplicate_ids_fail_closed(self):
        opener = FakeOpener([{'total': 2, 'jobs': [
            {'jobId': 'same'}, {'jobId': 'same'}]}])
        with self.assertRaises(ValueError):
            admin_pending('key', opener)

    def test_missing_total_fails_closed(self):
        with self.assertRaises(ValueError):
            admin_pending('key', FakeOpener([{'jobs': [{'jobId': 'one'}]}]))


if __name__ == '__main__':
    unittest.main()
