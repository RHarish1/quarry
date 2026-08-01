"""Search route for Quarry."""

import logging

from fastapi import APIRouter

from api.middleware import DEFAULT_RATE_LIMIT
from models.search import SearchRequest, SearchResponse, SearchTimings
from pipeline.pipeline import execute_search_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/search", response_model=SearchResponse, dependencies=[DEFAULT_RATE_LIMIT]
)
async def search(request: SearchRequest) -> SearchResponse:
    """Accept a search request and return crawled, cleaned documents."""

    try:
        return await execute_search_pipeline(request)
    except Exception:  # noqa: BLE001
        return SearchResponse(
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
