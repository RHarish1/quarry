"""Search route for Quarry."""

import logging
from uuid import uuid4

from fastapi import APIRouter
request_id = str(uuid4())

from api.middleware import DEFAULT_RATE_LIMIT
from models.search import SearchRequest, SearchResponse, SearchTimings
from pipeline.pipeline import execute_search_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


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
        200: {
            "description": "Search completed, including empty partial-failure results."
        },
        422: {"description": "The JSON request body did not match SearchRequest."},
        429: {
            "description": "The Redis-backed limit of 30 requests per minute was exceeded."
        },
    },
)
async def search(request: SearchRequest) -> SearchResponse:
    """Accept a search request and return crawled, cleaned documents."""

    try:
        return await execute_search_pipeline(request, request_id)
    except Exception:  # noqa: BLE001
        return SearchResponse(
            request_id=request_id,
            query=request.query,
            timings=SearchTimings(
                search_latency_ms=0.0,
                crawl_latency_ms=0.0,
                cleaning_latency_ms=0.0,
                compression_latency_ms=0.0,
                total_request_latency_ms=0.0,
            ),
            documents=[],
        )
