"""SearXNG adapter tests for Quarry."""

from __future__ import annotations

import asyncio
from typing import Self

from models.search import CleaningLevel, SearchRequest
from pipeline.retrieval import searxng as searxng_module


class FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload


class FakeAsyncClient:
    last_data: dict[str, str] | None = None

    def __init__(self, *args, **kwargs) -> None:
        self.base_url = kwargs.get("base_url")
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url, params=None, headers=None, **kwargs):
        FakeAsyncClient.last_data = params
        return FakeResponse(
            {
                "results": [
                    {
                        "url": "https://example.com/one",
                        "title": "One",
                        "content": "Snippet",
                        "engine": "google",
                    }
                ]
            }
        )

    async def post(self, path: str, data: dict[str, str], headers: dict[str, str]):
        FakeAsyncClient.last_data = data
        return FakeResponse(
            {
                "results": [
                    {
                        "url": "https://example.com/one",
                        "title": "One",
                        "content": "Snippet",
                        "engine": "google",
                    }
                ]
            }
        )


def test_search_searxng_maps_response_and_parameters(monkeypatch) -> None:
    monkeypatch.setattr(searxng_module, "get_http_client", lambda: FakeAsyncClient())

    request = SearchRequest(
        query="quarry",
        cleaning_level=CleaningLevel.LEVEL_2,
        crawl_websites=True,
        enable_caching=False,
        compress_output=False,
        enhance_query=False,
        rank_and_score_deterministically=False,
        time_range="day",
        language="en",
        engines=["google"],
        categories=["general"],
    )

    results = asyncio.run(searxng_module.search_searxng(request))
    assert len(results.results) == 1
    assert results.results[0].url == "https://example.com/one"
    assert results.results[0].metadata["engine"] == "google"
    assert FakeAsyncClient.last_data == {
        "q": "quarry",
        "format": "json",
        "categories": "general",
        "language": "en",
        "time_range": "day",
        "engines": "google",
    }
