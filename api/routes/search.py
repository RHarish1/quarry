"""Search route for Quarry."""

import logging
from uuid import uuid4
from time import perf_counter

from fastapi import APIRouter, Request

from api.middleware import DEFAULT_RATE_LIMIT
from models.search import SearchBenchmark, SearchRequest, SearchResponse, SearchTimings
from pipeline.pipeline import execute_search_pipeline

# Your custom metrics
from api.metrics import (
    SEARCH_CACHE_HITS, CACHE_LOOKUP_MS, URLS_FOUND, 
    PAGES_CRAWLED, CRAWL_FAILURES, COMPRESSION_RATIO, TOKENS_SAVED
)

logger = logging.getLogger(__name__)
router = APIRouter()
request_id = str(uuid4())

@router.post(
    "/search",
    response_model=SearchResponse,
    dependencies=[DEFAULT_RATE_LIMIT],
    tags=["Search"],
    summary="Search, optionally crawl and rank, then clean documents",
    description=(
        "Searches SearXNG for candidate URLs. By default, Quarry returns search "
        "snippets. Enable `crawl_websites` to fetch and extract page content. "
        "Enable `rank_and_score_deterministically` as well to crawl filtered "
        "candidates in batches and stop once `target_documents` quality-qualified "
        "documents have been found. Cleaning always runs; compression is optional."
    ),
    response_description="A normalized response containing cleaned documents and stage timings.",
    responses={
        200: {"description": "Search completed, including empty partial-failure results."},
        422: {"description": "The JSON request body did not match SearchRequest."},
        429: {"description": "The Redis-backed limit of 30 requests per minute was exceeded."},
    },
)
async def search(req: Request, body: SearchRequest) -> SearchResponse:
    """Accept a search request and return crawled, cleaned documents."""
    start = perf_counter()
    mode = req.headers.get("x-mode", "production")
    
    try:
        # 1. Capture the response instead of returning it immediately
        response = await execute_search_pipeline(body, request_id, mode)
        benchmark = response.benchmark

        # 2. --- POPULATE PROMETHEUS METRICS ---
        if benchmark.cache_hit:
            SEARCH_CACHE_HITS.inc()
            
        URLS_FOUND.inc(benchmark.urls_found)
        PAGES_CRAWLED.inc(benchmark.pages_successfully_crawled)
        CRAWL_FAILURES.inc(benchmark.crawl_failures)
        
        tokens_saved = benchmark.tokens_before - benchmark.tokens_after
        TOKENS_SAVED.inc(tokens_saved)

        CACHE_LOOKUP_MS.observe(benchmark.cache_lookup_ms)
        COMPRESSION_RATIO.observe(benchmark.compression_ratio)

        # 3. Return the response to the user
        return response

    except Exception:  # noqa: BLE001
        total_latency = (perf_counter() - start) * 1000

        benchmark = SearchBenchmark(
            timings=SearchTimings(
                search_latency_ms=0.0,
                crawl_latency_ms=0.0,
                cleaning_latency_ms=0.0,
                compression_latency_ms=0.0,
                total_request_latency_ms=total_latency,
            ),
        )

        return SearchResponse(
            success=False,
            request_id=request_id,
            query=body.query,
            timings=benchmark.timings,
            benchmark=benchmark,
            documents=[],
        )