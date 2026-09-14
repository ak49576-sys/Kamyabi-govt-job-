import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from check_api import check
from check_api import response_details


class ApiCheckTests(unittest.TestCase):
    def test_response_metadata_does_not_echo_body_or_key(self):
        report = response_details({'Server': 'cloudflare', 'Content-Type': 'text/html', 'CF-Ray': 'abc123-BOM'},
                                  b'<html>Just a moment challenge-platform secret-test-value</html>')
        self.assertTrue(report['challenge_indicated'])
        self.assertEqual(report['cf_ray'], 'abc123-BOM')
        self.assertNotIn('secret-test-value', str(report))

    def test_cloudflare_header_alone_is_not_a_challenge(self):
        report = response_details({'Server': 'cloudflare', 'Content-Type': 'application/json'}, b'{"error":"Forbidden"}')
        self.assertTrue(report['server_mentions_cloudflare'])
        self.assertFalse(report['challenge_indicated'])

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
