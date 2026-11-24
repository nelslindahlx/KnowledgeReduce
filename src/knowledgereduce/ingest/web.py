"""Hardened async web crawler with SSRF checks, robots caching, and trafilatura extraction."""

from __future__ import annotations

import asyncio
import hashlib
import time
import warnings
from collections import deque
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import structlog
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field

from knowledgereduce.models import IngestionError, SourceDocument, SourceType, SSRFError, utc_now
from knowledgereduce.security import ResolverFn, validate_url_safe

logger = structlog.get_logger(__name__)

_ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_BOILERPLATE_TAGS = ("script", "style", "noscript", "svg", "nav", "footer", "header")
_LEAF_TEXT_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "td", "th")


class CrawlConfig(BaseModel):
    """Configuration for safe, bounded multi-page web ingestion."""

    model_config = ConfigDict(extra="forbid")

    seed_urls: list[str]
    allowed_domains: list[str] = Field(default_factory=list)
    max_depth: int = Field(default=1, ge=0, le=10)
    max_pages_per_domain: int = Field(default=20, ge=1, le=5000)
    rate_limit_seconds: float = Field(default=0.2, ge=0.0, le=60.0)
    request_timeout: float = Field(default=10.0, gt=0.0, le=120.0)
    max_response_bytes: int = Field(default=5_000_000, ge=1024)
    respect_robots: bool = True
    robots_failure_ttl_seconds: float = Field(default=300.0, ge=0.0)
    trust_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    user_agent: str = "KnowledgeReduceBot/1.0 (+https://github.com/nelslindahlx/KnowledgeReduce)"
    allow_private_ips: bool = False
    known_hashes: dict[str, str] = Field(default_factory=dict)


def _extract_metadata_from_html(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    author: str | None = None
    description: str | None = None
    published_at: str | None = None

    for meta in soup.find_all("meta"):
        name = str(meta.get("name") or meta.get("property") or "").strip().lower()
        content = str(meta.get("content") or "").strip()
        if not content:
            continue
        if name == "author" and author is None:
            author = content
        elif name in {"description", "og:description"} and description is None:
            description = content
        elif name in {"article:published_time", "pubdate", "date"} and published_at is None:
            published_at = content

    return {
        "title": title,
        "author": author,
        "description": description,
        "published_at": published_at,
    }


def _extract_with_trafilatura(html: str, url: str) -> str | None:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"SOCKS support in urllib3.*",
            category=Warning,
        )
        import trafilatura

    extracted = trafilatura.extract(
        html,
        url=url or None,
        include_comments=False,
        include_tables=True,
        favor_precision=False,
    )
    return extracted if isinstance(extracted, str) else None


def extract_main_text(html: str, url: str = "") -> tuple[str, dict[str, str | None]]:
    """Extract clean prose and metadata from HTML without nested DOM duplication."""
    meta = _extract_metadata_from_html(html)
    extracted = _extract_with_trafilatura(html, url)
    if extracted and extracted.strip():
        return extracted.strip(), meta

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_BOILERPLATE_TAGS):
        tag.decompose()

    blocks: list[str] = []
    seen: set[str] = set()
    for elem in soup.find_all(_LEAF_TEXT_TAGS):
        # Skip block containers that wrap leaf block children to avoid duplicate text.
        if elem.name == "li" and elem.find(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
            continue
        text = " ".join(elem.stripped_strings)
        if text and text not in seen:
            seen.add(text)
            blocks.append(text)

    if blocks:
        return "\n".join(blocks), meta

    fallback = " ".join(soup.stripped_strings)
    return fallback.strip(), meta


def _parse_optional_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _domain_matches(hostname: str, allowed_domains: set[str]) -> bool:
    host = hostname.lower()
    return any(host == dom or host.endswith(f".{dom}") for dom in allowed_domains)


class AsyncWebCrawler:
    """Bounded, SSRF-hardened, robots-compliant async web crawler."""

    def __init__(
        self,
        config: CrawlConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: ResolverFn | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self._resolver = resolver
        self._robots_cache: dict[str, tuple[RobotFileParser | None, float]] = {}
        self._domain_last_request: dict[str, float] = {}

    def _allowed_domain_set(self) -> set[str]:
        if self.config.allowed_domains:
            return {d.strip().lower() for d in self.config.allowed_domains if d.strip()}
        domains: set[str] = set()
        for url in self.config.seed_urls:
            parsed = urlparse(url)
            if parsed.hostname:
                domains.add(parsed.hostname.lower())
        return domains

    async def _rate_limit_domain(self, domain: str) -> None:
        interval = self.config.rate_limit_seconds
        if interval <= 0:
            return
        now = time.monotonic()
        last = self._domain_last_request.get(domain)
        if last is not None:
            wait = interval - (now - last)
            if wait > 0:
                await asyncio.sleep(wait)
        self._domain_last_request[domain] = time.monotonic()

    async def _safe_get(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        current = validate_url_safe(
            url,
            allow_private_ips=self.config.allow_private_ips,
            resolver=self._resolver,
        )
        max_redirects = 5
        for _ in range(max_redirects + 1):
            parsed = urlparse(current)
            domain = parsed.hostname or ""
            await self._rate_limit_domain(domain)

            async with client.stream("GET", current, follow_redirects=False) as response:
                if 300 <= response.status_code < 400 and "location" in response.headers:
                    next_url = urljoin(current, response.headers["location"])
                    current = validate_url_safe(
                        next_url,
                        allow_private_ips=self.config.allow_private_ips,
                        resolver=self._resolver,
                    )
                    continue

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self.config.max_response_bytes:
                        raise IngestionError(
                            f"Response from {current!r} exceeded max_response_bytes "
                            f"({self.config.max_response_bytes})."
                        )
                    chunks.append(chunk)
                raw_body = b"".join(chunks)
                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=raw_body,
                    request=httpx.Request("GET", current),
                )

        raise IngestionError(f"Exceeded maximum redirects ({max_redirects}) for {url!r}.")

    async def _can_fetch(self, client: httpx.AsyncClient, url: str) -> bool:
        if not self.config.respect_robots:
            return True
        parsed = urlparse(url)
        scheme = parsed.scheme
        netloc = parsed.netloc
        domain = parsed.hostname or ""
        now = time.monotonic()

        cached = self._robots_cache.get(domain)
        if cached is not None:
            parser, expires_at = cached
            if expires_at == 0.0 or now < expires_at:
                return True if parser is None else parser.can_fetch(self.config.user_agent, url)

        robots_url = f"{scheme}://{netloc}/robots.txt"
        try:
            resp = await self._safe_get(client, robots_url)
            if resp.status_code == 200:
                rp = RobotFileParser()
                rp.parse(resp.text.splitlines())
                self._robots_cache[domain] = (rp, 0.0)
                return rp.can_fetch(self.config.user_agent, url)
            # Cache non-200 failure cleanly for TTL so we don't spam /robots.txt
            ttl = now + self.config.robots_failure_ttl_seconds
            self._robots_cache[domain] = (None, ttl)
            return True
        except (httpx.HTTPError, IngestionError) as exc:
            logger.debug("robots_fetch_failed", url=robots_url, error=str(exc))
            ttl = now + self.config.robots_failure_ttl_seconds
            self._robots_cache[domain] = (None, ttl)
            return True

    def _extract_links(self, html: str, base_url: str, allowed: set[str]) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = str(anchor["href"]).strip()
            if not href or href.startswith("#"):
                continue
            joined = urljoin(base_url, href)
            try:
                safe_url = validate_url_safe(
                    joined,
                    allow_private_ips=self.config.allow_private_ips,
                    resolver=self._resolver,
                )
            except SSRFError:
                continue
            host = urlparse(safe_url).hostname or ""
            if _domain_matches(host, allowed):
                links.append(safe_url)
        return links

    async def crawl(self) -> list[SourceDocument]:
        """Execute bounded BFS crawl and return normalized ``SourceDocument`` items."""
        allowed = self._allowed_domain_set()
        frontier: deque[tuple[str, int]] = deque()
        queued: set[str] = set()
        visited: set[str] = set()
        domain_counts: dict[str, int] = {}
        documents: list[SourceDocument] = []

        for seed in self.config.seed_urls:
            safe_seed = validate_url_safe(
                seed,
                allow_private_ips=self.config.allow_private_ips,
                resolver=self._resolver,
            )
            host = urlparse(safe_seed).hostname or ""
            if not _domain_matches(host, allowed):
                raise IngestionError(f"Seed URL {safe_seed!r} is outside allowed_domains.")
            if safe_seed not in queued:
                frontier.append((safe_seed, 0))
                queued.add(safe_seed)

        timeout = httpx.Timeout(self.config.request_timeout)
        headers = {"User-Agent": self.config.user_agent}

        async with httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            transport=self._transport,
        ) as client:
            while frontier:
                url, depth = frontier.popleft()
                if url in visited:
                    continue

                domain = urlparse(url).hostname or ""
                if domain_counts.get(domain, 0) >= self.config.max_pages_per_domain:
                    continue

                if not await self._can_fetch(client, url):
                    logger.info("crawl_skipped_robots", url=url)
                    visited.add(url)
                    continue

                visited.add(url)
                resp = await self._safe_get(client, url)
                if resp.status_code >= 400:
                    logger.warning("crawl_http_error", url=url, status_code=resp.status_code)
                    continue

                content_type = (
                    str(resp.headers.get("content-type", "")).split(";", 1)[0].strip().lower()
                )
                if content_type and not any(
                    content_type.startswith(ct) for ct in _ALLOWED_CONTENT_TYPES
                ):
                    logger.info("crawl_skipped_content_type", url=url, content_type=content_type)
                    continue

                final_url = str(resp.url)
                final_domain = urlparse(final_url).hostname or domain
                domain_counts[final_domain] = domain_counts.get(final_domain, 0) + 1

                html = resp.text
                if content_type == "text/plain":
                    text = html.strip()
                    meta: dict[str, str | None] = {
                        "title": final_url,
                        "author": None,
                        "description": None,
                        "published_at": None,
                    }
                else:
                    text, meta = extract_main_text(html, url=final_url)

                content_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if self.config.known_hashes.get(final_url) == content_sha:
                    logger.info("crawl_skipped_unchanged", url=final_url)
                    continue

                source_id = f"web_{hashlib.sha256(final_url.encode('utf-8')).hexdigest()[:12]}"
                doc_meta: dict[str, Any] = {
                    "status_code": resp.status_code,
                    "content_type": content_type,
                    "description": meta.get("description"),
                    "depth": depth,
                }
                documents.append(
                    SourceDocument(
                        source_id=source_id,
                        uri=final_url,
                        source_type=SourceType.WEB,
                        title=meta.get("title") or final_url,
                        author=meta.get("author"),
                        published_at=_parse_optional_iso(meta.get("published_at")),
                        fetched_at=utc_now(),
                        content=text,
                        content_sha256=content_sha,
                        trust_weight=self.config.trust_weight,
                        metadata=doc_meta,
                    )
                )

                if depth < self.config.max_depth and content_type != "text/plain":
                    for child_url in self._extract_links(html, final_url, allowed):
                        child_domain = urlparse(child_url).hostname or ""
                        if (
                            child_url not in visited
                            and child_url not in queued
                            and domain_counts.get(child_domain, 0)
                            < self.config.max_pages_per_domain
                        ):
                            frontier.append((child_url, depth + 1))
                            queued.add(child_url)

        return documents


class WebConnector:
    """Synchronous ``BaseConnector`` wrapper around ``AsyncWebCrawler``."""

    def __init__(
        self,
        config: CrawlConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: ResolverFn | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self._resolver = resolver

    def ingest(self) -> list[SourceDocument]:
        """Run the async web crawl synchronously."""
        crawler = AsyncWebCrawler(
            self.config,
            transport=self._transport,
            resolver=self._resolver,
        )
        return asyncio.run(crawler.crawl())
