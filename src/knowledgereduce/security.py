"""Security helpers for path containment and SSRF-safe URL validation."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from knowledgereduce.models.exceptions import PathSecurityError, SSRFError

ALLOWED_SCHEMES = frozenset({"http", "https"})

ResolverFn = Callable[[str, int], list[str]]


def ensure_within_base(path: Path | str, base_dir: Path | str) -> Path:
    """Resolve *path* and assert it stays strictly inside *base_dir*."""
    base = Path(base_dir).resolve()
    raw = Path(path)
    candidate = raw.resolve() if raw.is_absolute() else (base / raw).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise PathSecurityError(
            f"Path {str(path)!r} escapes allowed base directory {str(base)!r}."
        ) from exc
    return candidate


def _default_dns_resolver(hostname: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SSRFError(f"DNS resolution failed for host {hostname!r}: {exc}") from exc
    ips: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            ips.append(str(sockaddr[0]))
    return ips


def _is_forbidden_ip(ip_str: str) -> bool:
    # Strip IPv6 zone index if present (e.g., fe80::1%lo0)
    clean_ip = ip_str.split("%", 1)[0]
    try:
        addr = ipaddress.ip_address(clean_ip)
    except ValueError:
        return True
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or not addr.is_global
    )


def canonicalize_url(url: str) -> str:
    """Normalize scheme/hostname casing, drop fragments, and strip default ports."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise SSRFError(f"Disallowed URL scheme {parsed.scheme!r}; only http/https are permitted.")
    if not parsed.hostname:
        raise SSRFError(f"URL {url!r} does not contain a valid hostname.")

    hostname = parsed.hostname.lower()
    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    host_part = f"[{hostname}]" if ":" in hostname else hostname
    netloc = f"{host_part}:{port}" if port is not None else host_part
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def validate_url_safe(
    url: str,
    *,
    allow_private_ips: bool = False,
    resolver: ResolverFn | None = None,
) -> str:
    """Validate URL scheme and resolved IP addresses against SSRF attacks.

    Returns the canonicalized URL if safe; raises ``SSRFError`` otherwise.
    """
    normalized = canonicalize_url(url)
    parsed = urlparse(normalized)
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError(f"URL {url!r} missing hostname.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    # Check literal IP hostnames directly first without needing DNS.
    try:
        ipaddress.ip_address(hostname)
        ips = [hostname]
    except ValueError:
        if hostname == "localhost" or hostname.endswith(".localhost"):
            if not allow_private_ips:
                raise SSRFError(f"Localhost target {hostname!r} is forbidden.") from None
            return normalized
        resolve = resolver or _default_dns_resolver
        ips = resolve(hostname, port)

    if not ips:
        raise SSRFError(f"No IP addresses resolved for host {hostname!r}.")

    if not allow_private_ips:
        for ip_str in ips:
            if _is_forbidden_ip(ip_str):
                raise SSRFError(f"Target host {hostname!r} resolves to non-public IP {ip_str!r}.")

    return normalized
