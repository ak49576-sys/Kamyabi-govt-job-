import unittest

from official_source_url_policy import (
    UnsafeTarget, preflight_official_url, preflight_redirect_chain,
)


ALLOWED = ("ssc.gov.in",)


def resolve(host):
    return ["8.8.8.8", "1.1.1.1"]  # synthetic DNS answers; no network


class OfficialUrlPolicyTests(unittest.TestCase):
    def approved(self, url, resolver=resolve):
        return preflight_official_url(url, ALLOWED, resolver)

    def blocked(self, url, resolver=resolve):
        with self.assertRaises(UnsafeTarget):
            self.approved(url, resolver)

    def test_exact_host(self):
        self.assertEqual(self.approved("https://ssc.gov.in/jobs/notice.pdf").host, "ssc.gov.in")

    def test_valid_subdomain(self):
        self.assertEqual(self.approved("https://cdn.ssc.gov.in/a.pdf").host, "cdn.ssc.gov.in")

    def test_trailing_dot_canonicalized(self):
        self.assertEqual(self.approved("https://SSC.GOV.IN./a.pdf").host, "ssc.gov.in")

    def test_suffix_spoof(self):
        self.blocked("https://ssc.gov.in.attacker.example/fake.pdf")

    def test_same_suffix_not_registered(self):
        self.blocked("https://fakegov.in/a.pdf")

    def test_http_rejected(self):
        self.blocked("http://ssc.gov.in/a.pdf")

    def test_credentials_rejected(self):
        self.blocked("https://user:password@ssc.gov.in/a.pdf")

    def test_fragment_rejected(self):
        self.blocked("https://ssc.gov.in/a.pdf#fragment")

    def test_nonstandard_port(self):
        self.blocked("https://ssc.gov.in:8443/a.pdf")

    def test_localhost_rejected(self):
        self.blocked("https://localhost/a.pdf")

    def test_ip_literal_rejected(self):
        self.blocked("https://8.8.8.8/a.pdf")

    def test_private_dns_rejected(self):
        self.blocked("https://ssc.gov.in/a.pdf", lambda _: ["10.0.0.5"])

    def test_mixed_public_private_dns_rejected(self):
        self.blocked("https://ssc.gov.in/a.pdf", lambda _: ["8.8.8.8", "127.0.0.1"])

    def test_ipv6_local_dns_rejected(self):
        self.blocked("https://ssc.gov.in/a.pdf", lambda _: ["fd00::1"])

    def test_dns_failure_rejected(self):
        self.blocked("https://ssc.gov.in/a.pdf", lambda _: (_ for _ in ()).throw(OSError("offline")))

    def test_empty_dns_rejected(self):
        self.blocked("https://ssc.gov.in/a.pdf", lambda _: [])

    def test_valid_redirect_chain(self):
        chain = preflight_redirect_chain(
            ["https://ssc.gov.in/a", "https://cdn.ssc.gov.in/a.pdf"], ALLOWED, resolve)
        self.assertEqual(len(chain), 2)

    def test_redirect_to_other_host_rejected(self):
        with self.assertRaises(UnsafeTarget):
            preflight_redirect_chain(
                ["https://ssc.gov.in/a", "https://outside.example/a"], ALLOWED, resolve)

    def test_redirect_to_private_dns_rejected(self):
        def malicious(host):
            return ["192.168.1.1"] if host.startswith("cdn.") else ["8.8.8.8"]
        with self.assertRaises(UnsafeTarget):
            preflight_redirect_chain(
                ["https://ssc.gov.in/a", "https://cdn.ssc.gov.in/a"], ALLOWED, malicious)

    def test_too_many_redirects(self):
        with self.assertRaises(UnsafeTarget):
            preflight_redirect_chain(["https://ssc.gov.in/a"] * 5, ALLOWED, resolve)


if __name__ == "__main__":
    unittest.main()
