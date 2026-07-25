"""SearXNG retrieval client for Quarry."""

from collections.abc import Mapping

import httpx
from fastapi import HTTPException

from config.settings import settings
from models.search import (
    SearchFormat,
    SearchMetadata,
    SearchRequest,
    SearchResponse,
    SearchResult,
)


def _format_for_searxng(search_format: SearchFormat) -> str:
    """Map the request format to the upstream SearXNG format name."""

    if search_format is SearchFormat.CSS:
        return "csv"

    return search_format.value


def _build_params(request: SearchRequest) -> dict[str, str]:
    """Build a minimal form payload for SearXNG."""

    params: dict[str, str] = {
        "q": request.query,
        "format": "json",
    }

    if request.categories:
        params["categories"] = ",".join(request.categories)

    if request.language:
        params["language"] = request.language

    if request.time_range:
        params["time_range"] = request.time_range.value

    if request.engines:
        params["engines"] = ",".join(request.engines)

    return params


def _extract_results(payload: Mapping[str, object], request: SearchRequest) -> list[SearchResult]:
    """Convert a SearXNG JSON payload into SearchResult objects."""

    raw_results = payload.get("results", [])
    if not isinstance(raw_results, list):
        return []

    results: list[SearchResult] = []
    for item in raw_results:
        if not isinstance(item, Mapping):
            continue

        results.append(
            SearchResult(
                url=str(item.get("url", "")),
                title=str(item.get("title", "")),
                content=str(item.get("content", "")),
                metadata=SearchMetadata(
                    source="searxng",
                    crawl_websites=False,
                    rank_and_score_deterministically=False,
                    compress_output_using_headroom=False,
                    tokens_before_compression=None,
                    tokens_after_compression=None,
                    websites_dropped_percentage=None,
                    compression_rate=None,
                ),
            )
        )

    return results


async def search_searxng(request: SearchRequest) -> SearchResponse:
    """Query SearXNG and normalize the response into Quarry's response model."""

    params = _build_params(request)
    params["format"] = _format_for_searxng(request.format)

    async with httpx.AsyncClient(
        base_url=settings.searxng_base_url,
        timeout=settings.searxng_timeout_seconds,
    ) as client:
        response = await client.post(
            "/search",
            data=params,
            headers={"Accept": "application/json"},
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="SearXNG returned an error")

    payload = response.json()
    if not isinstance(payload, Mapping):
        raise HTTPException(status_code=502, detail="Unexpected SearXNG response")

    return SearchResponse(results=_extract_results(payload, request))