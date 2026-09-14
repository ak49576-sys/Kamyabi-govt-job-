"""Shared redirect policy for requests carrying API credentials."""
from urllib.request import HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
