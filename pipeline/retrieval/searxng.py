"""SearXNG retrieval client for Quarry."""

from collections.abc import Mapping

import httpx
from fastapi import HTTPException

from config.settings import settings
from models.search import SearchRequest, SearchResult, SearchResults
from pipeline.http import get_http_client
from pipeline.resilience import (
    FAST_PROVIDER_BREAKER,
    SEARCH_PROVIDER_RETRY,
    CircuitBreaker,
    retry,
)

SEARXNG_BREAKER = CircuitBreaker(
    name="searxng",
    failure_threshold=FAST_PROVIDER_BREAKER.failure_threshold,
    recovery_timeout=FAST_PROVIDER_BREAKER.recovery_timeout,
)


def _build_params(request: SearchRequest) -> dict[str, str]:
    """Build query parameters for SearXNG."""

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


async def _raw_search(request: SearchRequest) -> SearchResults:
    """Execute a single SearXNG request."""

    params = _build_params(request)
    base_url = settings.searxng_base_url.rstrip("/")

    try:
        client = get_http_client()
        # Use GET request with params for standard SearXNG API behavior
        response = await client.get(
            f"{base_url}/search",
            params=params,
            headers={"Accept": "application/json"},
        )
    except (httpx.TimeoutException, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=502, detail=f"SearXNG connection failed to {base_url}: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="SearXNG request failed") from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502, detail=f"SearXNG returned HTTP {response.status_code}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Unexpected non-JSON SearXNG response",
        ) from exc

    if not isinstance(payload, Mapping):
        raise HTTPException(
            status_code=502,
            detail="Unexpected SearXNG response payload structure",
        )

    return SearchResults(results=_extract_results(payload))


async def search_searxng(request: SearchRequest) -> SearchResults:
    """Query SearXNG with resilience."""

    return await SEARXNG_BREAKER.execute(
        lambda: retry(
            lambda: _raw_search(request),
            provider="SearXNG",
            policy=SEARCH_PROVIDER_RETRY,
        )
    )
