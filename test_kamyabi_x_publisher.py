import tempfile
import unittest
from datetime import date
from pathlib import Path

from kamyabi_x_publisher import open_job, post_text, read_state, run, write_state


TODAY = date(2026, 9, 24)
JOB = {'job_id': 'sample-job-2026', 'title': 'Sample recruitment',
       'status': 'APPLICATION_OPEN', 'application_start_date': '2026-09-01',
       'application_last_date': '2026-10-07'}


class PublisherTests(unittest.TestCase):
    def test_rejects_closed_upcoming_and_placeholder_deadlines(self):
        self.assertTrue(open_job(JOB, TODAY))
        for change in ({'status': 'CLOSED'}, {'application_start_date': '2026-10-01'},
                       {'application_last_date': '2099-12-31'}, {'application_last_date': None}):
            self.assertFalse(open_job({**JOB, **change}, TODAY))

    def test_first_run_baselines_and_never_backfills(self):
        state, outcome, job = run([JOB], None, TODAY, send=lambda _: self.fail('unexpected post'))
        self.assertEqual((outcome, job), ('baseline', None))
        self.assertIn(JOB['job_id'], state['seen'])
        self.assertEqual(run([JOB], state, TODAY, send=lambda _: self.fail('duplicate'))[1], 'unchanged')
        with self.assertRaisesRegex(ValueError, 'No open jobs'):
            run([], None, TODAY)

    def test_new_job_posts_once_then_persists_receipt(self):
        state = {'version': 1, 'seen': {}}
        calls = []
        state, outcome, job = run([JOB], state, TODAY, send=lambda j: calls.append(j['job_id']) or 'post-1')
        self.assertEqual((outcome, calls), ('posted', ['sample-job-2026']))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            write_state(state, path)
            self.assertEqual(read_state(path)['seen'][JOB['job_id']]['buffer_post_id'], 'post-1')
        self.assertEqual(run([JOB], state, TODAY, send=lambda _: self.fail('duplicate'))[1], 'unchanged')

    def test_failed_post_does_not_mark_job_seen(self):
        state = {'version': 1, 'seen': {}}
        with self.assertRaisesRegex(ValueError, 'failed'):
            run([JOB], state, TODAY, send=lambda _: (_ for _ in ()).throw(ValueError('failed')))
        self.assertEqual(state['seen'], {})

    def test_post_has_canonical_link_and_fits_standard_limit(self):
        text = post_text({**JOB, 'title': 'A' * 500})
        self.assertLessEqual(len(text), 280)
        self.assertIn('https://kamyabi.in/jobs/sample-job-2026', text)


if __name__ == '__main__':
    unittest.main()
