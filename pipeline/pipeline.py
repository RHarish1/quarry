"""Top-level pipeline orchestration for Quarry."""

from __future__ import annotations

from time import perf_counter

from config.settings import settings
from models.clean_document import CleanRequest
from models.search import CrawlRequest, SearchRequest, SearchResponse, SearchTimings
from pipeline.cleaning.cleaner import clean_documents
from pipeline.crawler.crawler import crawl_documents
from pipeline.retrieval.searxng import search_searxng


async def execute_search_pipeline(request: SearchRequest) -> SearchResponse:
    """Run the search, crawl, and cleaning pipeline."""

    total_started = perf_counter()

    search_started = perf_counter()
    try:
        search_results = await search_searxng(request)
    except Exception:
        search_results = None
    search_latency_ms = (perf_counter() - search_started) * 1000.0

    if search_results is None:
        total_request_latency_ms = (perf_counter() - total_started) * 1000.0
        return SearchResponse(
            query=request.query,
            timings=SearchTimings(
                search_latency_ms=search_latency_ms,
                crawl_latency_ms=0.0,
                cleaning_latency_ms=0.0,
                total_request_latency_ms=total_request_latency_ms,
            ),
            documents=[],
        )

    crawl_started = perf_counter()
    try:
        crawled_documents = await crawl_documents(
            CrawlRequest(
                search_results=search_results,
                crawl_websites=request.crawl_websites,
                enable_caching=request.enable_caching,
                timeout_seconds=settings.crawl_timeout_seconds,
                max_concurrency=settings.crawl_max_concurrency,
            )
        )
    except Exception:
        crawled_documents = None
    crawl_latency_ms = (perf_counter() - crawl_started) * 1000.0

    if crawled_documents is None:
        total_request_latency_ms = (perf_counter() - total_started) * 1000.0
        return SearchResponse(
            query=request.query,
            timings=SearchTimings(
                search_latency_ms=search_latency_ms,
                crawl_latency_ms=crawl_latency_ms,
                cleaning_latency_ms=0.0,
                total_request_latency_ms=total_request_latency_ms,
            ),
            documents=[],
        )

    cleaning_started = perf_counter()
    try:
        cleaned_documents = clean_documents(
            CleanRequest(
                documents=crawled_documents,
                cleaning_level=int(request.cleaning_level),
            )
        )
    except Exception:
        cleaned_documents = None
    cleaning_latency_ms = (perf_counter() - cleaning_started) * 1000.0

    if cleaned_documents is None:
        total_request_latency_ms = (perf_counter() - total_started) * 1000.0
        return SearchResponse(
            query=request.query,
            timings=SearchTimings(
                search_latency_ms=search_latency_ms,
                crawl_latency_ms=crawl_latency_ms,
                cleaning_latency_ms=cleaning_latency_ms,
                total_request_latency_ms=total_request_latency_ms,
            ),
            documents=[],
        )

    total_request_latency_ms = (perf_counter() - total_started) * 1000.0
    return SearchResponse(
        query=request.query,
        timings=SearchTimings(
            search_latency_ms=search_latency_ms,
            crawl_latency_ms=crawl_latency_ms,
            cleaning_latency_ms=cleaning_latency_ms,
            total_request_latency_ms=total_request_latency_ms,
        ),
        documents=cleaned_documents.documents,
    )
