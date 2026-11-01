"""Offline URL/DNS/redirect preflight for official-notice fetch design.

This is NOT a production HTTP fetcher: a real implementation must pin its TLS
connection to validated DNS IPs, verify cert hostnames and limit response sizes.
"""

from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit
import re


@dataclass(frozen=True)
class VerifiedTarget:
    host: str
    addresses: tuple[str, ...]


class UnsafeTarget(ValueError):
    pass


def _host(name: str) -> str:
    try:
        host = name.rstrip(".").encode("idna").decode("ascii").lower()
    except (UnicodeError, AttributeError) as exc:
        raise UnsafeTarget("invalid_host") from exc
    if not host or len(host) > 253 or not re.fullmatch(r"[a-z0-9.-]+", host):
        raise UnsafeTarget("invalid_host")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
           for label in host.split(".")):
        raise UnsafeTarget("invalid_host")
    return host


def preflight_official_url(url: str, allowed_domains: tuple[str, ...], resolver) -> VerifiedTarget:
    if len(url) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise UnsafeTarget("invalid_url")
    try:
        parts = urlsplit(url)
        host = _host(parts.hostname)
        port = parts.port
    except (ValueError, UnsafeTarget) as exc:
        raise UnsafeTarget("invalid_url_or_port") from exc
    if (parts.scheme.lower() != "https" or not parts.netloc or parts.username is not None
            or parts.password is not None or parts.fragment or port not in (None, 443)):
        raise UnsafeTarget("unsafe_url_parameters")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise UnsafeTarget("ip_literal_not_allowed")

    roots = [_host(root) for root in allowed_domains]
    if not roots or not any(host == root or host.endswith("." + root) for root in roots):
        raise UnsafeTarget("unapproved_official_host")
    try:
        answers = list(resolver(host))
    except Exception as exc:
        raise UnsafeTarget("dns_lookup_failed") from exc
    if not answers:
        raise UnsafeTarget("dns_missing")
    unique: set[str] = set()
    for raw_ip in answers:
        try:
            ip = ip_address(raw_ip)
        except ValueError as exc:
            raise UnsafeTarget("invalid_dns_answer") from exc
        if not ip.is_global:
            raise UnsafeTarget("non_public_dns_answer")
        unique.add(str(ip))
    return VerifiedTarget(host, tuple(sorted(unique)))


def preflight_redirect_chain(
    urls: list[str], allowed_domains: tuple[str, ...], resolver, *, max_redirects: int = 3
) -> tuple[VerifiedTarget, ...]:
    if not urls or len(urls) > max_redirects + 1:
        raise UnsafeTarget("redirect_count_invalid")
    return tuple(preflight_official_url(url, allowed_domains, resolver) for url in urls)
