import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from check_api import check


class ApiCheckTests(unittest.TestCase):
    @patch('check_api.build_opener')
    def test_missing_secret_makes_no_request(self, opener):
        self.assertFalse(check('')['authentication_verified'])
        opener.assert_not_called()

    @patch('check_api.build_opener')
    def test_read_only_request_and_redacted_report(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"ok":true,"auth":"api_key"}'
        report = check('synthetic-key')
        request = opener.return_value.open.call_args.args[0]
        self.assertIsNone(request.data)
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.full_url, 'https://kamyabi.in/api/v1/status')
        self.assertEqual(request.get_header('X-api-key'), 'synthetic-key')
        self.assertTrue(report['authentication_verified'])
        self.assertNotIn('synthetic-key', str(report))

    @patch('check_api.build_opener')
    def test_validation_rejection_is_not_authentication_proof(self, opener):
        opener.return_value.open.side_effect = HTTPError('https://kamyabi.in/', 400, '', {}, None)
        self.assertFalse(check('synthetic-key')['authentication_verified'])

    @patch('check_api.build_opener')
    def test_auth_failure_is_reported(self, opener):
        opener.return_value.open.side_effect = HTTPError('https://kamyabi.in/', 401, '', {}, None)
        report = check('synthetic-key')
        self.assertFalse(report['authentication_verified'])
        self.assertEqual(report['result'], 'API rejected authentication')

    @patch('check_api.build_opener')
    def test_generic_html_200_is_not_success(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'<html>Home page</html>'
        self.assertFalse(check('synthetic-key')['authentication_verified'])


if __name__ == '__main__':
    unittest.main()
