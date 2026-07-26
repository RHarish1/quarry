"""Crawler stage for Quarry."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from config.settings import settings
from models.document import Document, Documents
from models.search import CrawlRequest, SearchResult

CANONICAL_PATTERN = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\'](?P<href>[^"\']+)["\']',
    re.IGNORECASE,
)
TITLE_PATTERN = re.compile(r"<title>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)


def _load_crawl4ai() -> tuple[Any, Any, Any, Any]:
    """Import Crawl4AI lazily so the app remains import-safe when the package is absent."""

    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except ImportError as exc:  # pragma: no cover - exercised in packaged runtime
        raise RuntimeError("crawl4ai is required for crawling") from exc

    return AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig


def _fallback_document(search_result: SearchResult, status: str, reason: str) -> Document:
    """Create a conservative document fallback when crawling cannot proceed."""

    now = datetime.now(timezone.utc)
    metadata: dict[str, Any] = {}
    if isinstance(search_result.metadata, dict):
        metadata.update(search_result.metadata)
    metadata.update({"crawl_fallback_reason": reason})

    return Document(
        id=uuid4().hex,
        url=search_result.url,
        canonical_url=search_result.url,
        title=search_result.title,
        markdown=search_result.content,
        html=None,
        metadata=metadata,
        crawl_timestamp=now,
        crawl_latency_ms=0.0,
        crawl_status=status,
        content_type="text/plain",
    )


def _extract_markdown(result: Any) -> str:
    """Extract raw markdown from a Crawl4AI result."""

    markdown = getattr(result, "markdown", None)
    if markdown is None:
        return ""

    raw_markdown = getattr(markdown, "raw_markdown", None)
    if isinstance(raw_markdown, str):
        return raw_markdown

    if isinstance(markdown, str):
        return markdown

    return str(markdown)


def _extract_html(result: Any) -> str:
    """Extract HTML from a Crawl4AI result."""

    html = getattr(result, "html", None)
    return html if isinstance(html, str) else ""


def _extract_title(result: Any, html: str, fallback_title: str) -> str:
    """Preserve the page title when available."""

    metadata = getattr(result, "metadata", None)
    if isinstance(metadata, dict):
        title = metadata.get("title") or metadata.get("og:title")
        if isinstance(title, str) and title.strip():
            return title.strip()

    match = TITLE_PATTERN.search(html)
    if match:
        title = re.sub(r"\s+", " ", match.group("title")).strip()
        if title:
            return title

    return fallback_title


def _extract_canonical_url(result: Any, html: str, fallback_url: str) -> str:
    """Preserve the canonical URL when available."""

    metadata = getattr(result, "metadata", None)
    if isinstance(metadata, dict):
        canonical_url = metadata.get("canonical_url") or metadata.get("canonicalURL")
        if isinstance(canonical_url, str) and canonical_url.strip():
            return canonical_url.strip()

    match = CANONICAL_PATTERN.search(html)
    if match:
        canonical_url = match.group("href").strip()
        if canonical_url:
            return canonical_url

    return fallback_url


def _extract_content_type(result: Any) -> str:
    """Preserve the response content type when available."""

    response_headers = getattr(result, "response_headers", None)
    if isinstance(response_headers, dict):
        content_type = response_headers.get("content-type") or response_headers.get("Content-Type")
        if isinstance(content_type, str) and content_type.strip():
            return content_type.split(";", 1)[0].strip()

    return "text/html"


def _result_to_document(search_result: SearchResult) -> Document:
    """Convert a search hit directly into a raw document when crawling is disabled."""

    now = datetime.now(timezone.utc)
    return Document(
        id=uuid4().hex,
        url=search_result.url,
        canonical_url=search_result.url,
        title=search_result.title,
        markdown=search_result.content,
        html=None,
        metadata={**search_result.metadata, "source": "search_provider"},
        crawl_timestamp=now,
        crawl_latency_ms=0.0,
        crawl_status="skipped",
        content_type="text/plain",
    )


async def _crawl_search_result(search_result: SearchResult, crawl_request: CrawlRequest) -> Document | None:
    """Crawl a single search hit into a raw document."""

    try:
        AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig = _load_crawl4ai()
    except Exception:
        return _fallback_document(search_result, "crawl_unavailable", "crawl4ai unavailable")

    browser_config = BrowserConfig(headless=True, text_mode=True)
    run_config = CrawlerRunConfig(
        check_robots_txt=True,
        page_timeout=int(crawl_request.timeout_seconds * 1000),
        wait_until="domcontentloaded",
        cache_mode=CacheMode.ENABLED if crawl_request.enable_caching else CacheMode.BYPASS,
    )

    crawl_started = perf_counter()
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await asyncio.wait_for(
                crawler.arun(url=search_result.url, config=run_config),
                timeout=crawl_request.timeout_seconds,
            )
    except (asyncio.TimeoutError, TimeoutError):
        return _fallback_document(search_result, "timeout", "crawl timed out")
    except Exception:
        return _fallback_document(search_result, "crawl_failed", "crawl execution failed")

    crawl_latency_ms = (perf_counter() - crawl_started) * 1000.0
    if not getattr(result, "success", False):
        error_message = str(getattr(result, "error_message", "")).lower()
        if "robots" in error_message:
            return _fallback_document(search_result, "robots_blocked", "blocked by robots.txt")

        return _fallback_document(search_result, "crawl_failed", error_message or "crawl failed")

    html = _extract_html(result)
    markdown = _extract_markdown(result)
    metadata = getattr(result, "metadata", None)
    response_headers = getattr(result, "response_headers", None)
    document_metadata: dict[str, Any] = {}
    if isinstance(search_result.metadata, dict):
        document_metadata.update(search_result.metadata)
    if isinstance(metadata, dict):
        document_metadata.update(metadata)
    if isinstance(response_headers, dict):
        document_metadata["response_headers"] = response_headers

    return Document(
        id=uuid4().hex,
        url=str(getattr(result, "url", search_result.url)),
        canonical_url=_extract_canonical_url(result, html, search_result.url),
        title=_extract_title(result, html, search_result.title),
        markdown=markdown,
        html=html or None,
        metadata=document_metadata,
        crawl_timestamp=datetime.now(timezone.utc),
        crawl_latency_ms=crawl_latency_ms,
        crawl_status="success",
        content_type=_extract_content_type(result),
    )


async def crawl_documents(crawl_request: CrawlRequest) -> Documents:
    """Crawl search results into raw documents, skipping failures gracefully."""

    if not crawl_request.search_results.results:
        return Documents()

    if not crawl_request.crawl_websites:
        return Documents(
            documents=[_result_to_document(search_result) for search_result in crawl_request.search_results.results]
        )

    semaphore = asyncio.Semaphore(max(1, crawl_request.max_concurrency))

    async def guarded_crawl(search_result: SearchResult) -> Document | None:
        async with semaphore:
            return await _crawl_search_result(search_result, crawl_request)

    results = await asyncio.gather(
        *(guarded_crawl(search_result) for search_result in crawl_request.search_results.results),
        return_exceptions=False,
    )

    documents = [
        document
        for document in results
        if document is not None
    ]
    return Documents(documents=documents)
