"""Unit tests for file connectors, JSONL checkpoints, and SSRF-safe AsyncWebCrawler."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from knowledgereduce.ingest import (
    AsyncWebCrawler,
    CrawlConfig,
    CSVConnector,
    JSONConnector,
    MarkdownConnector,
    TextConnector,
    extract_main_text,
    ingest_local_file,
    read_jsonl_checkpoint,
    write_jsonl_checkpoint,
)
from knowledgereduce.models import IngestionError, SourceDocument, SourceType, SSRFError


def _public_dns(_host: str, _port: int) -> list[str]:
    return ["93.184.216.34"]


def test_local_connectors_and_checkpoint_roundtrip(tmp_path: Path) -> None:
    csv_file = tmp_path / "facts.csv"
    csv_file.write_text("subject,predicate,object\nA,IS_A,B\n", encoding="utf-8")
    json_file = tmp_path / "notes.json"
    json_file.write_text('[{"statement": "Fact one"}]', encoding="utf-8")
    jsonl_file = tmp_path / "stream.jsonl"
    jsonl_file.write_text('{"statement": "Line 1"}\n{"statement": "Line 2"}\n', encoding="utf-8")
    md_file = tmp_path / "doc.md"
    md_file.write_text(
        "---\ntitle: Test Note\nauthor: Nels Lindahl\n---\n\n# Heading\nBody text here.\n",
        encoding="utf-8",
    )
    txt_file = tmp_path / "plain.txt"
    txt_file.write_text("Plain text paragraph.", encoding="utf-8")

    docs = [
        *CSVConnector(csv_file).ingest(),
        *JSONConnector(json_file).ingest(),
        *JSONConnector(jsonl_file).ingest(),
        *MarkdownConnector(md_file).ingest(),
        *TextConnector(txt_file).ingest(),
    ]
    assert [d.source_type for d in docs] == [
        SourceType.CSV,
        SourceType.JSON,
        SourceType.JSONL,
        SourceType.MARKDOWN,
        SourceType.TEXT,
    ]
    assert docs[3].title == "Test Note"
    assert docs[3].author == "Nels Lindahl"

    # Dispatch helper and unsupported suffix
    assert ingest_local_file(txt_file)[0].content == "Plain text paragraph."
    bad_file = tmp_path / "bin.exe"
    bad_file.write_text("nope", encoding="utf-8")
    with pytest.raises(IngestionError):
        ingest_local_file(bad_file)

    ckpt = tmp_path / "01_ingested.jsonl"
    write_jsonl_checkpoint(docs, ckpt)
    restored = read_jsonl_checkpoint(ckpt, SourceDocument)
    assert len(restored) == 5
    assert restored[0].content_sha256 == docs[0].content_sha256


def test_extract_main_text_strips_boilerplate_and_avoids_nested_duplication() -> None:
    html = """
    <html><head><title>Title</title></head>
    <body>
      <script>var secret = 1;</script>
      <nav><a href="/x">Menu</a></nav>
      <main>
        <ul><li><p>First unique bullet item.</p></li></ul>
        <p>Second unique paragraph.</p>
      </main>
    </body></html>
    """
    text, meta = extract_main_text(html, "https://civichonors.com/")
    assert meta["title"] == "Title"
    assert "var secret" not in text
    assert text.count("First unique bullet item.") == 1
    assert "Second unique paragraph." in text


async def test_web_crawler_robots_depth_domain_limit_and_incremental_skip() -> None:
    robots_fetches = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal robots_fetches
        path = request.url.path
        if path == "/robots.txt":
            robots_fetches += 1
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        if path == "/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    "<html><head><title>Home</title></head><body><main>"
                    "<p>Civic Honors root content paragraph.</p>"
                    "<a href='/p1'>P1</a><a href='/private'>Priv</a>"
                    "<a href='https://evil.example/'>Offsite</a>"
                    "<a href='file:///etc/passwd'>Local</a>"
                    "</main></body></html>"
                ),
            )
        if path == "/p1":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    "<html><head><title>P1</title></head><body><main>"
                    "<p>Second page prose about Civic Honors.</p>"
                    "<a href='/p2'>P2</a>"
                    "</main></body></html>"
                ),
            )
        if path == "/p2":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<main><p>Should not be crawled past max_pages_per_domain=2</p></main>",
            )
        return httpx.Response(404)

    cfg = CrawlConfig(
        seed_urls=["https://civichonors.com/"],
        max_depth=2,
        max_pages_per_domain=2,
        rate_limit_seconds=0.0,
    )
    crawler = AsyncWebCrawler(cfg, transport=httpx.MockTransport(handler), resolver=_public_dns)
    docs = await crawler.crawl()

    assert robots_fetches == 1
    assert [d.uri for d in docs] == [
        "https://civichonors.com/",
        "https://civichonors.com/p1",
    ]

    # Incremental skip when content_sha256 matches known_hashes
    known = {d.uri: d.content_sha256 for d in docs}
    cfg2 = CrawlConfig(
        seed_urls=["https://civichonors.com/"],
        max_depth=0,
        rate_limit_seconds=0.0,
        known_hashes=known,
    )
    crawler2 = AsyncWebCrawler(cfg2, transport=httpx.MockTransport(handler), resolver=_public_dns)
    assert await crawler2.crawl() == []


async def test_web_crawler_blocks_ssrf_redirects_and_oversized_responses() -> None:
    def redirect_to_loopback(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/secret"})

    cfg = CrawlConfig(
        seed_urls=["https://civichonors.com/"],
        rate_limit_seconds=0.0,
        respect_robots=True,
    )
    crawler = AsyncWebCrawler(
        cfg, transport=httpx.MockTransport(redirect_to_loopback), resolver=_public_dns
    )
    with pytest.raises(SSRFError):
        await crawler.crawl()

    def oversized_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            content=b"A" * 5000,
        )

    cfg_small = CrawlConfig(
        seed_urls=["https://civichonors.com/"],
        rate_limit_seconds=0.0,
        max_response_bytes=1024,
        respect_robots=False,
    )
    crawler_small = AsyncWebCrawler(
        cfg_small, transport=httpx.MockTransport(oversized_handler), resolver=_public_dns
    )
    with pytest.raises(IngestionError, match="max_response_bytes"):
        await crawler_small.crawl()


def test_extract_main_text_handles_plain_fallback() -> None:
    text, _ = extract_main_text("<html><body><div>Raw prose block.</div></body></html>")
    assert hashlib.sha256(text.encode()).hexdigest()
    assert "Raw prose block." in text
