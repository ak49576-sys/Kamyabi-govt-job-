import io
import unittest
from unittest.mock import Mock
from public_inventory_probe import probe

class Response:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size): return b'{"jobs":[{"job_id":"x","title":"Y"}]}'

class PublicInventoryProbeTests(unittest.TestCase):
    def test_public_feed_is_never_complete_pending_inventory(self):
        result = probe(open_request=lambda req: Response())
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["public_job_count"], 1)
        self.assertEqual(result["field_names"], ["job_id", "title"])
        self.assertFalse(result["sufficient_for_auto_publish_dedup"])
        self.assertFalse(result["includes_pending_inventory"])

    def test_unexpected_schema_fails(self):
        class Invalid(Response):
            def read(self, size): return b'{"items":[]}'
        with self.assertRaises(ValueError):
            probe(open_request=lambda req: Invalid())

if __name__ == "__main__":
    unittest.main()
