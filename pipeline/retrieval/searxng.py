"""SearXNG retrieval client for Quarry."""

from collections.abc import Mapping

import httpx
from fastapi import HTTPException

from config.settings import settings
from models.search import SearchRequest, SearchResult, SearchResults


def _build_params(request: SearchRequest) -> dict[str, str]:
    """Build a form payload for SearXNG."""

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


def _extract_results(payload: Mapping[str, object]) -> list[SearchResult]:
    """Convert a SearXNG JSON payload into SearchResult objects."""

    raw_results = payload.get("results", [])
    if not isinstance(raw_results, list):
        return []

    results: list[SearchResult] = []
    for item in raw_results:
        if not isinstance(item, Mapping):
            continue

        known_keys = {"url", "title", "content"}
        results.append(
            SearchResult(
                url=str(item.get("url", "")),
                title=str(item.get("title", "")),
                content=str(item.get("content", "")),
                metadata={
                    key: value for key, value in item.items() if key not in known_keys
                },
            )
        )

    return results


async def search_searxng(request: SearchRequest) -> SearchResults:
    """Query SearXNG and normalize the response into Quarry search results."""

    params = _build_params(request)

    try:
        async with httpx.AsyncClient(
            base_url=settings.searxng_base_url,
            timeout=settings.searxng_timeout_seconds,
        ) as client:
            response = await client.post(
                "/search",
                data=params,
                headers={"Accept": "application/json"},
            )
    except (httpx.TimeoutException, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail="SearXNG request failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="SearXNG request failed") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="SearXNG returned an error")

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail="Unexpected SearXNG response"
        ) from exc

    if not isinstance(payload, Mapping):
        raise HTTPException(status_code=502, detail="Unexpected SearXNG response")

    return SearchResults(results=_extract_results(payload))
