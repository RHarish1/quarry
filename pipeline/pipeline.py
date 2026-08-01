"""Top-level pipeline orchestration for Quarry."""

from __future__ import annotations

import logging
from time import perf_counter

from config.settings import settings
from models.clean_document import CleanRequest
from models.search import CrawlRequest, SearchRequest, SearchResponse, SearchTimings
from pipeline.cleaning.cleaner import clean_documents
from pipeline.crawler.crawler import crawl_documents
from pipeline.ranking.manager import rank_documents
from pipeline.retrieval.searxng import search_searxng
from pipeline.query.normalizer import normalize_query
from .cache import get, make_cache_key, set

logger = logging.getLogger(__name__)


async def execute_search_pipeline(request: SearchRequest) -> SearchResponse:
    """Run the search, crawl, and cleaning pipeline."""
    key = make_cache_key(request)
    logger.info("Original Query", request.query)
    request = normalize_query(request)

    if request.enable_caching:
        logger.info("Cache Check")
        cached = await get(key)
        if cached is not None:
            logger.info("Cache Hit!")
            return cached
        logger.info("Cache Miss!")

    logger.info(
        "Starting search pipeline for normalized query '%s'",
        request.query,
    )
    total_started = perf_counter()

    search_started = perf_counter()
    logger.info("Starting search stage")
    try:
        search_results = await search_searxng(request)
        logger.info("Returned from search_searxng: %r", search_results)
        logger.info("Type: %s", type(search_results))

    except Exception:
        logger.exception("Search stage failed")
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
    logger.info(
        "Search completed: %d results (%.2f ms)",
        len(search_results.results),
        search_latency_ms,
    )
    logger.info("Starting crawl stage")
    crawl_started = perf_counter()
    try:
        crawl_request = CrawlRequest(
            search_results=search_results,
            crawl_websites=request.crawl_websites,
            enable_caching=request.enable_caching,
            timeout_seconds=settings.crawl_timeout_seconds,
            max_concurrency=settings.crawl_max_concurrency,
        )

        if request.rank_and_score_deterministically and request.crawl_websites:
            crawled_documents = await rank_documents(
                search_results,
                target_documents=request.target_documents,
                crawl_request=crawl_request,
            )
        else:
            crawled_documents = await crawl_documents(crawl_request)
    except Exception:
        logger.exception("Crawling stage failed")
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
    logger.info(
        "Crawl completed: %d documents (%.2f ms)",
        len(crawled_documents.documents),
        crawl_latency_ms,
    )
    logger.info("Starting cleaning stage")
    cleaning_started = perf_counter()
    try:
        cleaned_documents = clean_documents(
            CleanRequest(
                documents=crawled_documents,
                cleaning_level=int(request.cleaning_level),
            )
        )
    except Exception:
        logger.exception("Cleaning stage failed")
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
    logger.info(
        "Cleaning completed: %d documents (%.2f ms)",
        len(cleaned_documents.documents),
        cleaning_latency_ms,
    )

    total_request_latency_ms = (perf_counter() - total_started) * 1000.0
    response = SearchResponse(
        query=request.query,
        timings=SearchTimings(
            search_latency_ms=search_latency_ms,
            crawl_latency_ms=crawl_latency_ms,
            cleaning_latency_ms=cleaning_latency_ms,
            total_request_latency_ms=total_request_latency_ms,
        ),
        documents=cleaned_documents.documents,
    )
    if request.enable_caching and response.documents:
        await set(key, response)
    return response
