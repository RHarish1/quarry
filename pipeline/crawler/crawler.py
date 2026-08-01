"""Crawler stage for Quarry."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from models.document import Document, Documents
from models.search import CrawlRequest, SearchResult
from pipeline.crawler.fetcher import fetch_raw_document
from pipeline.crawler.manager import ExtractorManager

logger = logging.getLogger(__name__)


def _fallback_document(search_result: SearchResult, status: str, reason: str) -> Document:
    """Create a conservative document fallback when fetching or extraction fails."""

    now = datetime.now(timezone.utc)
    metadata = {
        **search_result.metadata,
        "source": "search_provider",
        "crawl_fallback_reason": reason,
    }

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


def _search_result_to_document(search_result: SearchResult) -> Document:
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


async def _crawl_search_result(
    search_result: SearchResult,
    crawl_request: CrawlRequest,
    manager: ExtractorManager,
) -> Document:
    """Fetch and extract a single search hit into a raw document."""

    crawl_started = perf_counter()
    try:
        raw_document = await fetch_raw_document(search_result, timeout_seconds=crawl_request.timeout_seconds)
    except Exception as exc:
        logger.exception("crawler.fetch_failed", extra={"url": search_result.url})
        return _fallback_document(search_result, "fetch_failed", str(exc))

    try:
        extracted_document = await manager.extract(raw_document)
    except Exception as exc:
        logger.exception("crawler.extract_failed", extra={"url": search_result.url})
        return _fallback_document(search_result, "extract_failed", str(exc))

    crawl_latency_ms = (perf_counter() - crawl_started) * 1000.0
    document = extracted_document.to_document(
        raw_document,
        crawl_status=extracted_document.extraction_method or "success",
    )
    document.crawl_latency_ms = crawl_latency_ms
    return document


async def crawl_documents(crawl_request: CrawlRequest) -> Documents:
    """Crawl search results into raw documents, skipping failures gracefully."""

    if not crawl_request.search_results.results:
        return Documents()

    if not crawl_request.crawl_websites:
        return Documents(
            documents=[_search_result_to_document(search_result) for search_result in crawl_request.search_results.results]
        )

    manager = ExtractorManager()
    semaphore = asyncio.Semaphore(max(1, crawl_request.max_concurrency))

    async def guarded_crawl(search_result: SearchResult) -> Document:
        async with semaphore:
            return await _crawl_search_result(search_result, crawl_request, manager)

    documents = await asyncio.gather(
        *(guarded_crawl(search_result) for search_result in crawl_request.search_results.results),
        return_exceptions=False,
    )

    return Documents(documents=list(documents))