"""Search route for Quarry."""

from fastapi import APIRouter, HTTPException

from models.search import SearchRequest, SearchResponse
from pipeline.retrieval.searxng import search_searxng

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """Accept a search request and return normalized SearXNG results."""

    try:
        return await search_searxng(request)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary for upstream calls
        raise HTTPException(status_code=502, detail="SearXNG request failed") from exc
