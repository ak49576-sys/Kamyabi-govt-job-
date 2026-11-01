"""Read-only, fail-closed Kamyabi admin inventory pager.

Requires a *separate* credential authorized to read /api/v1/admin/jobs.
No publication, writes, or credential logging. Never assumes the public feed
covers pending jobs. CLI prints aggregate counts only.
"""
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from api_http import NoRedirect
from check_api import USER_AGENT

BASE = "https://kamyabi.in/api/v1/admin/jobs"
STATUSES = ("pending", "approved", "rejected")
PAGE_SIZE = 200
MAX_PAGES = 100


class InventoryError(ValueError):
    pass


def fetch_inventory(key, open_request=None):
    if not isinstance(key, str) or not key or any(ch in key for ch in "\r\n"):
        raise InventoryError("Dedicated admin inventory credential required")
    if open_request is None:
        opener = build_opener(NoRedirect)
        def open_request(req):
            return opener.open(req, timeout=30)
    records = []
    job_ids = set()
    counts = {}
    for status in STATUSES:
        count = 0
        for page in range(MAX_PAGES):
            offset = page * PAGE_SIZE
            url = BASE + "?" + urlencode({"status": status, "limit": PAGE_SIZE, "offset": offset})
            request = Request(url, method="GET", headers={
                "Accept": "application/json", "X-Api-Key": key, "User-Agent": USER_AGENT,
                "Cache-Control": "no-cache",
            })
            try:
                with open_request(request) as response:
                    if response.status != 200:
                        raise InventoryError("Admin inventory HTTP status not 200")
                    body = response.read(5_000_001)
            except (HTTPError, URLError, OSError, TimeoutError) as error:
                raise InventoryError("Admin inventory request failed") from error
            if len(body) > 5_000_000:
                raise InventoryError("Admin inventory response too large")
            try:
                document = json.loads(body)
            except ValueError as error:
                raise InventoryError("Invalid inventory JSON") from error
            if (not isinstance(document, dict) or document.get("status") != status
                    or type(document.get("limit")) is not int or document["limit"] != PAGE_SIZE
                    or type(document.get("offset")) is not int or document["offset"] != offset
                    or not isinstance(document.get("jobs"), list)
                    or type(document.get("total")) is not int
                    or document["total"] != len(document["jobs"])
                    or len(document["jobs"]) > PAGE_SIZE):
                raise InventoryError("Inventory schema/page mismatch")
            rows = document["jobs"]
            for row in rows:
                if (not isinstance(row, dict) or not isinstance(row.get("job_id"), str)
                        or not row["job_id"] or row.get("verification_status") != status
                        or row["job_id"] in job_ids):
                    raise InventoryError("Inventory row or duplicate mismatch")
                job_ids.add(row["job_id"])
                # Status normalization for the offline decision gate.
                records.append({**row, "status": status})
            count += len(rows)
            if len(rows) < PAGE_SIZE:
                break
        else:
            raise InventoryError("Inventory pagination cap reached")
        counts[status] = count
    return {"inventory_complete": True, "records": records, "counts": counts}


def main():
    try:
        inventory = fetch_inventory(os.environ.get("KAMYABI_ADMIN_READ_KEY", ""))
        print(json.dumps({"mode": "read_only", "inventory_complete": True,
                          "counts": inventory["counts"], "submitted": 0, "published": 0}))
        return 0
    except InventoryError:
        print(json.dumps({"mode": "read_only", "inventory_complete": False,
                          "error": "Admin inventory unavailable or incomplete",
                          "submitted": 0, "published": 0}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
