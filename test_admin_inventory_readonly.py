import json
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from admin_inventory_readonly import fetch_inventory, InventoryError, PAGE_SIZE


class Response:
    status = 200
    def __init__(self, document):
        self.body = json.dumps(document).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, count): return self.body


def responder(req, *, corrupt=None, duplicate=False):
    query = parse_qs(urlparse(req.full_url).query)
    status, offset = query["status"][0], int(query["offset"][0])
    if status == "pending" and offset == 0:
        rows = [{"job_id": f"pending-{i}", "verification_status": status}
                for i in range(PAGE_SIZE)]
    elif status == "pending" and offset == PAGE_SIZE:
        rows = [{"job_id": "pending-extra", "verification_status": status}]
    elif status == "approved" and duplicate:
        rows = [{"job_id": "pending-1", "verification_status": status}]
    else:
        rows = []
    doc = {"status": status, "limit": PAGE_SIZE, "offset": offset,
           "jobs": rows, "total": len(rows)}
    if corrupt == status and offset == 0:
        doc["total"] = 999
    return Response(doc)


class AdminInventoryTests(unittest.TestCase):
    def test_reads_every_status_and_full_page(self):
        seen = []
        def op(req):
            self.assertEqual(req.get_method(), "GET")
            self.assertEqual(req.get_header("X-api-key"), "test-key")
            seen.append(req.full_url)
            return responder(req)
        result = fetch_inventory("test-key", op)
        self.assertTrue(result["inventory_complete"])
        self.assertEqual(result["counts"], {"pending": 201, "approved": 0, "rejected": 0})
        self.assertEqual(len(seen), 4)
        self.assertEqual(result["records"][-1]["status"], "pending")

    def test_rejects_missing_key(self):
        with self.assertRaises(InventoryError):
            fetch_inventory("", responder)

    def test_rejects_incomplete_page(self):
        with self.assertRaises(InventoryError):
            fetch_inventory("test-key", lambda req: responder(req, corrupt="approved"))

    def test_rejects_cross_status_duplicate(self):
        with self.assertRaises(InventoryError):
            fetch_inventory("test-key", lambda req: responder(req, duplicate=True))

    def test_rejects_unauthorized(self):
        def unauthorized(req):
            raise HTTPError(req.full_url, 401, "Unauthorized", {}, None)
        with self.assertRaises(InventoryError):
            fetch_inventory("test-key", unauthorized)

    def test_rejects_redirect_or_non_200(self):
        class Redirect(Response):
            status = 302
        with self.assertRaises(InventoryError):
            fetch_inventory("test-key", lambda req: Redirect({}))


if __name__ == "__main__":
    unittest.main()
