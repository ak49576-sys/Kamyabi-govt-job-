import unittest
from datetime import date
from unittest.mock import patch
from submit_jobs import validate_document, NoRedirect, send_jobs


class SubmissionTests(unittest.TestCase):
    def document(self):
        return {'reviewed': True, 'jobs': [{
            'job_id': 'test-notice-2026', 'title': 'Test notice', 'department': 'Test department',
            'qualification': 'Graduate', 'state_or_central': 'Central', 'last_date': '2026-10-31',
            'source_url': 'https://example.gov.in/',
            'official_notification_url': 'https://example.gov.in/notice.pdf', 'vacancy_count': 5}]}

    def validate(self, doc):
        return validate_document(doc, today=date(2026, 9, 13))

    def test_valid_contract_preserves_id(self):
        self.assertEqual(self.validate(self.document())[0]['job_id'], 'test-notice-2026')

    def test_raw_candidates_cannot_be_submitted(self):
        with self.assertRaises(ValueError):
            self.validate({'notices': []})

    def test_unreviewed_rejected(self):
        doc = self.document()
        doc['reviewed'] = False
        with self.assertRaises(ValueError):
            self.validate(doc)

    def test_expired_sentinel_and_mismatched_dates_rejected(self):
        for changes in [{'last_date': '2026-01-01'}, {'last_date': '2099-12-31'},
                        {'application_last_date': '2026-10-30'}, {'application_start_date': '2026-11-01'}]:
            doc = self.document()
            doc['jobs'][0].update(changes)
            with self.assertRaises(ValueError):
                self.validate(doc)

    def test_duplicate_id_rejected(self):
        doc = self.document()
        doc['jobs'] *= 2
        with self.assertRaises(ValueError):
            self.validate(doc)

    def test_boolean_vacancies_rejected(self):
        doc = self.document()
        doc['jobs'][0]['vacancy_count'] = True
        with self.assertRaises(ValueError):
            self.validate(doc)

    def test_redirect_does_not_forward_key(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.test/'))

    @patch('submit_jobs.build_opener')
    def test_api_wire_format_and_staging_result(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"inserted":1,"skipped":0,"skipped_ids":[]}'
        result = send_jobs(self.validate(self.document()), 'test-key')
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://kamyabi.in/api/v1/add-jobs')
        self.assertEqual(request.get_header('X-api-key'), 'test-key')
        self.assertTrue(request.data.startswith(b'['))
        self.assertEqual(result['inserted'], 1)
        self.assertIn('not verified', result['publication_status'])

    @patch('submit_jobs.build_opener')
    def test_incomplete_response_is_not_success(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"inserted":0,"skipped":0}'
        with self.assertRaises(ValueError):
            send_jobs(self.validate(self.document()), 'test-key')


if __name__ == '__main__':
    unittest.main()
