import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock
from auto_import import load_queue, deliver

JOB = json.loads(Path('reviewed-ibps-jobs.json').read_text())['jobs'][0]

class AutomaticImportTests(unittest.TestCase):
    def queue(self, job, reviewed=True, today=date(2026, 9, 18)):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'reviewed-test-jobs.json').write_text(json.dumps({'reviewed': reviewed, 'jobs': [job]}))
            return load_queue(root, today)

    def test_valid_reviewed(self):
        self.assertEqual(self.queue(JOB)[0], [JOB])

    def test_expired_skipped(self):
        self.assertEqual(self.queue(JOB, today=date(2026, 9, 22)), ([], [JOB['job_id']]))

    def test_review_required(self):
        with self.assertRaises(ValueError): self.queue(JOB, reviewed=False)

    def test_unofficial_domain(self):
        job = copy.deepcopy(JOB)
        job['official_notification_url'] = 'https://ibps.in.evil.test/a.pdf'
        with self.assertRaises(ValueError): self.queue(job)

    def test_unknown_employer(self):
        job = dict(JOB, recruiting_body='Private Bank')
        with self.assertRaises(ValueError): self.queue(job)

    def test_unchanged_no_write(self):
        send = Mock()
        deliver([JOB], True, 'key', {}, fetch=lambda: {JOB['job_id']: JOB}, send=send)
        send.assert_not_called()

    def test_preview_no_write(self):
        send = Mock()
        deliver([JOB], False, '', {}, fetch=lambda: {}, send=send)
        send.assert_not_called()

    def test_import_and_public_verification(self):
        fetch = Mock(side_effect=[{}, {JOB['job_id']: JOB}])
        send = Mock(return_value={'inserted': 1})
        report = {}
        deliver([JOB], True, 'key', report, fetch=fetch, send=send)
        send.assert_called_once_with([JOB], 'key')
        self.assertEqual(report['publication_status'], 'verified in public API')

    def test_pending_is_not_success(self):
        with self.assertRaisesRegex(ValueError, 'not visible'):
            deliver([JOB], True, 'key', {}, fetch=lambda: {}, send=Mock())

    def test_read_failure_blocks_write(self):
        send = Mock()
        with self.assertRaises(OSError):
            deliver([JOB], True, 'key', {}, fetch=Mock(side_effect=OSError()), send=send)
        send.assert_not_called()

    def test_post_failure_not_retried(self):
        send = Mock(side_effect=OSError())
        with self.assertRaises(OSError):
            deliver([JOB], True, 'key', {}, fetch=lambda: {}, send=send)
        self.assertEqual(send.call_count, 1)

if __name__ == '__main__': unittest.main()
