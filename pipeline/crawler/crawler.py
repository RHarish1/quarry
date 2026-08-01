"""Crawler stage for Quarry."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from urllib.parse import urljoin
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
from markdownify import markdownify as md

from models.document import Document, Documents
from models.search import CrawlRequest, SearchResult
from pipeline.cleaning.steps import normalize_markdown

NOISY_TAGS = {"script", "style", "noscript", "svg", "iframe", "form"}
CONTAINER_TAGS = {"body", "main", "article", "section", "div", "header", "aside"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def _load_http_client() -> type[httpx.AsyncClient]:
    """Return the HTTP client used for fetching pages."""

    return httpx.AsyncClient


def _fallback_document(
    search_result: SearchResult, status: str, reason: str
) -> Document:
    """Create a conservative document fallback when crawling cannot proceed."""

    now = datetime.now(UTC)
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


def _inline_text(element: Tag) -> str:
    """Collapse inline HTML content into readable text."""

    return re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip()


def _render_markdown_blocks(element: Tag) -> list[str]:
    """Convert a limited HTML subset into deterministic markdown-like blocks."""

    blocks: list[str] = []
    for child in element.children:
        if isinstance(child, NavigableString):
            text = re.sub(r"\s+", " ", str(child)).strip()
            if text:
                blocks.append(text)
            continue

        if not isinstance(child, Tag):
            continue

        name = child.name.lower()
        if name in NOISY_TAGS:
            continue

        if name in HEADING_TAGS:
            heading_level = int(name[1])
            text = _inline_text(child)
            if text:
                blocks.append(f"{'#' * heading_level} {text}")
            continue

        if name == "p":
            text = _inline_text(child)
            if text:
                blocks.append(text)
            continue

        if name == "blockquote":
            text = _inline_text(child)
            if text:
                blocks.append(f"> {text}")
            continue

        if name == "pre":
            text = child.get_text("\n", strip=True)
            if text:
                blocks.append("```")
                blocks.append(text)
                blocks.append("```")
            continue

        if name == "li":
            text = _inline_text(child)
            if text:
                blocks.append(f"- {text}")
            continue

        if name in {"ul", "ol"}:
            items = [item for item in child.find_all("li", recursive=False)]
            for index, item in enumerate(items, start=1):
                text = _inline_text(item)
                if not text:
                    continue

                prefix = f"{index}." if name == "ol" else "-"
                blocks.append(f"{prefix} {text}")
            continue

        if name == "table":
            text = _inline_text(child)
            if text:
                blocks.append(text)
            continue

        if name in CONTAINER_TAGS:
            blocks.extend(_render_markdown_blocks(child))
            continue

        text = _inline_text(child)
        if text:
            blocks.append(text)

    return blocks


def _html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup.find_all(NOISY_TAGS):
        tag.decompose()

    # remove comments
    from bs4 import Comment

    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    root = soup.find("main") or soup.find("article") or soup.body or soup

    markdown = md(
        str(root),
        heading_style="ATX",
        bullets="-",
        strip=["span"],
        escape_asterisks=False,
        escape_underscores=False,
    )

    return normalize_markdown(markdown)


def _extract_title_from_html(html: str, fallback_title: str) -> str:
    """Preserve the page title when available."""

    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if title_tag:
        title = re.sub(r"\s+", " ", title_tag.get_text(" ", strip=True)).strip()
        if title:
            return title

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and isinstance(og_title.get("content"), str):
        title = re.sub(r"\s+", " ", og_title.get("content", "")).strip()
        if title:
            return title

    return fallback_title


def _extract_canonical_url_from_html(html: str, fallback_url: str) -> str:
    """Preserve the canonical URL when available."""

    soup = BeautifulSoup(html, "html.parser")
    canonical_tag = soup.find(
        "link", attrs={"rel": lambda value: value and "canonical" in value}
    )
    if canonical_tag and isinstance(canonical_tag.get("href"), str):
        canonical_url = canonical_tag.get("href", "").strip()
        if canonical_url:
            return urljoin(fallback_url, canonical_url)

    return fallback_url


def _extract_content_type(response: httpx.Response) -> str:
    """Preserve the response content type when available."""

    content_type = response.headers.get("content-type") or response.headers.get(
        "Content-Type"
    )
    if isinstance(content_type, str) and content_type.strip():
        return content_type.split(";", 1)[0].strip()

    return "text/html"


def _result_to_document(search_result: SearchResult) -> Document:
    """Convert a search hit directly into a raw document when crawling is disabled."""

    now = datetime.now(UTC)
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


async def _crawl_search_result(
    search_result: SearchResult, crawl_request: CrawlRequest
) -> Document | None:
    """Crawl a single search hit into a raw document."""

    crawl_started = perf_counter()
    try:
        http_client = _load_http_client()
        async with http_client(
            follow_redirects=True, timeout=crawl_request.timeout_seconds
        ) as client:
            response = await asyncio.wait_for(
                client.get(
                    search_result.url,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "User-Agent": "Quarry/1.0",
                    },
                ),
                timeout=crawl_request.timeout_seconds,
            )
    except TimeoutError:
        return _fallback_document(search_result, "timeout", "crawl timed out")
    except httpx.HTTPError:
        return _fallback_document(search_result, "crawl_failed", "http fetch failed")
    except Exception:  # noqa: BLE001
        return _fallback_document(
            search_result, "crawl_failed", "crawl execution failed"
        )

    crawl_latency_ms = (perf_counter() - crawl_started) * 1000.0
    if response.status_code >= 400:
        return _fallback_document(
            search_result, "http_error", f"http {response.status_code}"
        )

    html = response.text
    markdown = _html_to_markdown(html)
    if not markdown.strip():
        markdown = search_result.content

    document_metadata: dict[str, Any] = {}
    if isinstance(search_result.metadata, dict):
        document_metadata.update(search_result.metadata)
    document_metadata["source"] = "fetched_html"
    document_metadata["final_url"] = str(response.url)

    return Document(
        id=uuid4().hex,
        url=str(response.url),
        canonical_url=_extract_canonical_url_from_html(html, str(response.url)),
        title=_extract_title_from_html(html, search_result.title),
        markdown=markdown,
        html=html or None,
        metadata=document_metadata,
        crawl_timestamp=datetime.now(UTC),
        crawl_latency_ms=crawl_latency_ms,
        crawl_status="success",
        content_type=_extract_content_type(response),
    )


async def crawl_documents(crawl_request: CrawlRequest) -> Documents:
    """Crawl search results into raw documents, skipping failures gracefully."""

    if not crawl_request.search_results.results:
        return Documents()

    if not crawl_request.crawl_websites:
        return Documents(
            documents=[
                _result_to_document(search_result)
                for search_result in crawl_request.search_results.results
            ]
        )

    semaphore = asyncio.Semaphore(max(1, crawl_request.max_concurrency))

    async def guarded_crawl(search_result: SearchResult) -> Document | None:
        async with semaphore:
            return await _crawl_search_result(search_result, crawl_request)

    results = await asyncio.gather(
        *(
            guarded_crawl(search_result)
            for search_result in crawl_request.search_results.results
        ),
        return_exceptions=False,
    )

    documents = [document for document in results if document is not None]
    return Documents(documents=documents)
