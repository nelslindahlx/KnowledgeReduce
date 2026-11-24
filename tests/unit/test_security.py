"""Unit tests for SSRF protection and path containment helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledgereduce.models import PathSecurityError, SSRFError
from knowledgereduce.security import canonicalize_url, ensure_within_base, validate_url_safe


def test_ensure_within_base_allows_contained_paths(tmp_path: Path) -> None:
    nested = ensure_within_base("sub/file.json", tmp_path)
    assert nested == (tmp_path / "sub" / "file.json").resolve()


def test_ensure_within_base_blocks_traversal(tmp_path: Path) -> None:
    with pytest.raises(PathSecurityError):
        ensure_within_base("../../etc/passwd", tmp_path)

    with pytest.raises(PathSecurityError):
        ensure_within_base("/etc/passwd", tmp_path)


def test_canonicalize_url_normalizes_ports_and_case() -> None:
    assert canonicalize_url("HTTPS://CivicHonors.COM:443/p/the-book#sec1") == (
        "https://civichonors.com/p/the-book"
    )
    assert canonicalize_url("http://Example.com:80") == "http://example.com/"


@pytest.mark.parametrize(
    "bad_url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "javascript:alert(1)",
        "http://127.0.0.1/admin",
        "http://10.0.0.5/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://localhost:8080/status",
    ],
)
def test_validate_url_safe_blocks_schemes_and_private_ips(bad_url: str) -> None:
    with pytest.raises(SSRFError):
        validate_url_safe(bad_url)


def test_validate_url_safe_blocks_dns_resolving_to_private_ip() -> None:
    def fake_resolver(host: str, port: int) -> list[str]:
        return ["172.16.0.10"]

    with pytest.raises(SSRFError, match="non-public IP"):
        validate_url_safe("https://internal.corp.example/page", resolver=fake_resolver)


def test_validate_url_safe_allows_public_ip_resolution() -> None:
    def fake_resolver(host: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    cleaned = validate_url_safe("https://Example.COM:443/path#frag", resolver=fake_resolver)
    assert cleaned == "https://example.com/path"
