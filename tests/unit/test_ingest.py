"""Unit tests for file connectors, JSONL checkpoints, and SSRF-safe AsyncWebCrawler."""

from __future__ import annotations

import gzip
import hashlib
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from knowledgereduce.ingest import (
    AsyncWebCrawler,
    CrawlConfig,
    CSVConnector,
    DirectoryConnector,
    HTMLConnector,
    JSONConnector,
    MarkdownConnector,
    PDFConnector,
    TextConnector,
    extract_main_text,
    ingest_local_directory,
    ingest_local_file,
    read_jsonl_checkpoint,
    write_jsonl_checkpoint,
)
from knowledgereduce.map import DeterministicNLPMapper
from knowledgereduce.models import (
    IngestionError,
    PathSecurityError,
    SourceDocument,
    SourceType,
    SSRFError,
)


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


async def test_web_crawler_handles_gzip_compressed_responses_and_http_errors() -> None:
    robots_gz = gzip.compress(b"User-agent: *\nAllow: /\n")
    html_gz = gzip.compress(
        b"<html><head><title>Gzip Page</title></head>"
        b"<body><main><p>Gzipped civic content works cleanly.</p></main></body></html>"
    )

    def gzip_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                headers={
                    "content-type": "text/plain",
                    "content-encoding": "gzip",
                    "content-length": str(len(robots_gz)),
                },
                stream=httpx.ByteStream(robots_gz),
            )
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html; charset=utf-8",
                "content-encoding": "gzip",
                "content-length": str(len(html_gz)),
            },
            stream=httpx.ByteStream(html_gz),
        )

    cfg = CrawlConfig(
        seed_urls=["https://civichonors.com/p/the-book"],
        max_depth=0,
        rate_limit_seconds=0.0,
        respect_robots=True,
    )
    crawler = AsyncWebCrawler(
        cfg, transport=httpx.MockTransport(gzip_handler), resolver=_public_dns
    )
    docs = await crawler.crawl()
    assert len(docs) == 1
    assert docs[0].title == "Gzip Page"
    assert "Gzipped civic content works cleanly." in docs[0].content

    def connect_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection reset", request=request)

    cfg_no_robots = CrawlConfig(
        seed_urls=["https://civichonors.com/p/the-book"],
        max_depth=0,
        rate_limit_seconds=0.0,
        respect_robots=False,
    )
    failing_connect = AsyncWebCrawler(
        cfg_no_robots,
        transport=httpx.MockTransport(connect_error_handler),
        resolver=_public_dns,
    )
    with pytest.raises(IngestionError, match="HTTP error fetching"):
        await failing_connect.crawl()

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    failing_timeout = AsyncWebCrawler(
        cfg_no_robots,
        transport=httpx.MockTransport(timeout_handler),
        resolver=_public_dns,
    )
    with pytest.raises(IngestionError, match="HTTP error fetching"):
        await failing_timeout.crawl()


def test_html_connector_extracts_metadata_and_enforces_base_dir(tmp_path: Path) -> None:
    html_file = tmp_path / "civic_article.html"
    html_file.write_text(
        """
        <html>
          <head>
            <title>Civic Honors Article</title>
            <meta name="author" content="Dr. Nels Lindahl" />
            <meta name="description" content="Civic Honors history." />
            <meta property="article:published_time" content="2020-06-14T12:00:00Z" />
          </head>
          <body>
            <script>var secret = 1;</script>
            <nav><a href="/nav">Navigation link</a></nav>
            <main><p>Civic Honors began in 2002 at the University of Kansas.</p></main>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    htm_file = tmp_path / "brief.htm"
    htm_file.write_text(
        "<html><body><p>Short HTM summary line.</p></body></html>", encoding="utf-8"
    )

    docs = HTMLConnector(html_file, base_dir=tmp_path).ingest()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.source_type == SourceType.HTML
    assert doc.title == "Civic Honors Article"
    assert doc.author == "Dr. Nels Lindahl"
    assert doc.published_at is not None and doc.published_at.year == 2020
    assert "University of Kansas" in doc.content
    assert "var secret" not in doc.content

    dispatched = ingest_local_file(htm_file, base_dir=tmp_path)
    assert dispatched[0].source_type == SourceType.HTML
    assert dispatched[0].title == "brief"
    assert "Short HTM summary line." in dispatched[0].content

    outside = tmp_path.parent / "outside.html"
    with pytest.raises(PathSecurityError):
        HTMLConnector(outside, base_dir=tmp_path).ingest()


async def test_ingest_fallback_and_crawler_status_and_content_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from knowledgereduce.ingest import web as web_mod

    monkeypatch.setattr(web_mod, "_extract_with_trafilatura", lambda _h, _u: None)
    html_blocks = (
        "<html><body><nav>Skip</nav>"
        "<ul><li><p>Nested list paragraph.</p></li><li>Plain list item.</li></ul>"
        "</body></html>"
    )
    txt_blocks, _ = extract_main_text(html_blocks, "https://example.org/")
    assert "Skip" not in txt_blocks
    assert txt_blocks.count("Nested list paragraph.") == 1
    assert "Plain list item." in txt_blocks

    txt_raw, _ = extract_main_text(
        "<html><body><span>  Loose  </span><span>body text</span></body></html>"
    )
    assert txt_raw == "Loose body text"
    assert web_mod._parse_optional_iso("not-a-date") is None

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if path == "/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    "<html><body><p>Root page.</p>"
                    "<a href='/missing'>404</a>"
                    "<a href='/doc.pdf'>PDF</a>"
                    "<a href='/notes.txt'>TXT</a></body></html>"
                ),
            )
        if path == "/missing":
            return httpx.Response(404, text="not found")
        if path == "/doc.pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        if path == "/notes.txt":
            return httpx.Response(200, headers={"content-type": "text/plain"}, text="Plain body.")
        return httpx.Response(404)

    cfg = CrawlConfig(
        seed_urls=["https://example.org/"],
        max_depth=1,
        max_pages_per_domain=10,
        rate_limit_seconds=0.0,
    )
    docs = await AsyncWebCrawler(
        cfg, transport=httpx.MockTransport(handler), resolver=_public_dns
    ).crawl()
    assert len(docs) == 2
    assert any(d.content == "Plain body." for d in docs)

    offsite_cfg = CrawlConfig(
        seed_urls=["https://other.org/"],
        allowed_domains=["example.org"],
        rate_limit_seconds=0.0,
    )
    with pytest.raises(IngestionError, match="outside allowed_domains"):
        await AsyncWebCrawler(
            offsite_cfg, transport=httpx.MockTransport(handler), resolver=_public_dns
        ).crawl()


def test_read_jsonl_checkpoint_skips_blanks_and_rejects_invalid_json(tmp_path: Path) -> None:
    ckpt = tmp_path / "mixed.jsonl"
    doc = SourceDocument(
        source_id="ok-1",
        uri="https://example.org/ok",
        source_type=SourceType.TEXT,
        content="Valid content.",
    )
    write_jsonl_checkpoint([doc], ckpt)
    # Inject blank lines around the valid record and verify clean reload.
    ckpt.write_text("\n" + ckpt.read_text(encoding="utf-8") + "\n   \n", encoding="utf-8")
    loaded = read_jsonl_checkpoint(ckpt, SourceDocument)
    assert [d.source_id for d in loaded] == ["ok-1"]

    bad_ckpt = tmp_path / "bad.jsonl"
    bad_ckpt.write_text("{corrupt-json\n", encoding="utf-8")
    with pytest.raises(IngestionError, match="Invalid JSONL record"):
        read_jsonl_checkpoint(bad_ckpt, SourceDocument)


def test_markdown_frontmatter_date_tags_and_mapper_propagation(tmp_path: Path) -> None:
    md_list = tmp_path / "report.md"
    md_list.write_text(
        "---\n"
        "title: Annual Report\n"
        "author: Nels Lindahl\n"
        "published_at: 2024-06-15T12:30:00Z\n"
        "date: 2020-01-01\n"
        "tags: [Civic, Kansas, Civic]\n"
        "---\n\n"
        "Nels Lindahl founded Civic Honors at the University of Kansas in 2006.\n",
        encoding="utf-8",
    )
    docs_list = MarkdownConnector(md_list).ingest()
    assert len(docs_list) == 1
    doc = docs_list[0]
    assert doc.published_at == datetime(2024, 6, 15, 12, 30, tzinfo=UTC)
    assert doc.metadata["tags"] == ["Civic", "Kansas"]

    batch = DeterministicNLPMapper(min_sentence_length=20).map_document(doc)
    assert batch.claims
    assert all("Civic" in clm.tags and "Kansas" in clm.tags for clm in batch.claims)

    md_date_only = tmp_path / "date_only.md"
    md_date_only.write_text(
        "---\ndate: 2024-03-15\ntags: policy, Governance\n---\n\nBody text.",
        encoding="utf-8",
    )
    doc_date = MarkdownConnector(md_date_only).ingest()[0]
    assert doc_date.published_at == datetime(2024, 3, 15, 0, 0, tzinfo=UTC)
    assert doc_date.metadata["tags"] == ["policy", "Governance"]

    md_invalid_date = tmp_path / "bad_date.md"
    md_invalid_date.write_text("---\ndate: not-a-date\n---\n\nBody text.", encoding="utf-8")
    assert MarkdownConnector(md_invalid_date).ingest()[0].published_at is None


def test_pdf_connector_missing_extra_extraction_and_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "brief.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%stub\n")

    monkeypatch.delitem(sys.modules, "pypdf", raising=False)
    monkeypatch.setattr("importlib.util.find_spec", lambda _name: None)
    with pytest.raises(IngestionError, match="uv sync --extra pdf"):
        PDFConnector(pdf_path).ingest()

    outside = tmp_path.parent / "outside_secret.pdf"
    with pytest.raises(PathSecurityError):
        PDFConnector(outside, base_dir=tmp_path).ingest()

    class _FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _FakePdfReader:
        def __init__(self, _file_path: str) -> None:
            self.pages = [_FakePage("First page text."), _FakePage("  Second page text.  ")]
            self.metadata = {"/Title": "PDF Briefing", "/Author": "Jane Doe"}

    fake_mod = types.ModuleType("pypdf")
    fake_mod.PdfReader = _FakePdfReader  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pypdf", fake_mod)

    docs = ingest_local_file(pdf_path, trust_weight=0.85)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.source_type == SourceType.PDF
    assert doc.title == "PDF Briefing"
    assert doc.author == "Jane Doe"
    assert doc.content == "First page text.\n\nSecond page text."
    assert doc.metadata["page_count"] == 2
    assert doc.trust_weight == 0.85


def test_directory_connector_globs_filtering_and_symlink_safety(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus"
    nested = corpus / "sub"
    hidden_dir = corpus / ".hidden"
    nested.mkdir(parents=True)
    hidden_dir.mkdir(parents=True)

    (corpus / "top.md").write_text("---\ntitle: Top Note\n---\n\nTop body.", encoding="utf-8")
    (corpus / "notes.txt").write_text("Plain top notes.", encoding="utf-8")
    (corpus / "ignored.bin").write_bytes(b"\x00\x01\x02")
    (corpus / "skip.pdf").write_bytes(b"%PDF-1.4\n")
    (corpus / ".dotfile.md").write_text("Hidden file.", encoding="utf-8")
    (hidden_dir / "secret.md").write_text("Hidden dir file.", encoding="utf-8")
    (nested / "deep.md").write_text("Deep markdown note.", encoding="utf-8")

    monkeypatch.delitem(sys.modules, "pypdf", raising=False)
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)

    docs_all = DirectoryConnector(corpus).ingest()
    titles_all = {d.title for d in docs_all}
    assert titles_all == {"Top Note", "notes.txt", "deep"}

    docs_shallow_md = ingest_local_directory(corpus, patterns=["**/*.md"], recursive=False)
    assert [d.title for d in docs_shallow_md] == ["Top Note"]

    with pytest.raises(IngestionError, match="uv sync --extra pdf"):
        ingest_local_directory(corpus, patterns=["*.pdf"], recursive=False)

    with pytest.raises(IngestionError, match="Input directory not found"):
        ingest_local_directory(tmp_path / "does_not_exist")

    outside_file = tmp_path / "outside.md"
    outside_file.write_text("Outside target.", encoding="utf-8")
    escape_link = corpus / "escape.md"
    escape_link.symlink_to(outside_file)
    with pytest.raises(PathSecurityError):
        ingest_local_directory(corpus)
