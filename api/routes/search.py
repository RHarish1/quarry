"""Search route for Quarry."""

from fastapi import APIRouter

from models.search import SearchRequest, SearchResponse

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """Accept a search request and return an empty structured response scaffold."""

    return SearchResponse()
