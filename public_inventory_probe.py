"""Read-only Kamyabi public jobs feed contract probe.

Prints metadata only: HTTP status, item count, field names and whether the
feed is suitable as a complete inventory (it is not, pending jobs are omitted).
Never prints record values, secrets, or submits data.
"""
import json
from urllib.request import Request, build_opener
from check_api import USER_AGENT
from api_http import NoRedirect

URL = "https://kamyabi.in/api/v1/jobs"


def probe(open_request=None):
    if open_request is None:
        def open_request(req):
            return build_opener(NoRedirect).open(req, timeout=30)
    request = Request(URL, method="GET",
                      headers={"Accept": "application/json", "User-Agent": USER_AGENT,
                               "Cache-Control": "no-cache"})
    with open_request(request) as response:
        status = response.status
        body = response.read(5_000_001)
    document = json.loads(body)
    if status != 200 or not isinstance(document, dict) or not isinstance(document.get("jobs"), list):
        raise ValueError("Public jobs endpoint does not meet expected contract")
    rows = document["jobs"]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("Unexpected job row")
    fields = sorted(set().union(*(row.keys() for row in rows))) if rows else []
    return {"http_status": status, "public_job_count": len(rows),
            "field_names": fields, "includes_pending_inventory": False,
            "sufficient_for_auto_publish_dedup": False}


if __name__ == "__main__":
    print(json.dumps(probe(), indent=2))
