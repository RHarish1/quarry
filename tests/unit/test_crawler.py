"""Crawler stage tests for Quarry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from models.search import CrawlRequest, SearchResult, SearchResults
from pipeline.crawler import crawler as crawler_module


@dataclass
class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        url: str,
        html: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.text = html
        self.headers = headers or {}


class FakeAsyncClient:
    last_requested_url: str | None = None

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, headers: dict[str, str] | None = None):
        FakeAsyncClient.last_requested_url = url
        if url.endswith("/good"):
            return FakeResponse(
                status_code=200,
                url="https://example.com/good",
                html=(
                    "<html><head><title>Meta Title</title>"
                    "<link rel='canonical' href='https://example.com/canonical'/></head>"
                    "<body><main><h1>Title</h1><p>Body</p></main></body></html>"
                ),
                headers={"content-type": "text/html; charset=utf-8"},
            )

        if url.endswith("/slow"):
            await asyncio.sleep(0.05)
            return FakeResponse(
                status_code=200,
                url=url,
                html="<html><body><main><p>slow</p></main></body></html>",
            )

        if url.endswith("/missing"):
            return FakeResponse(status_code=404, url=url, html="<html></html>")

        raise httpx.HTTPError("boom")


def test_crawler_skips_failures_and_preserves_metadata(monkeypatch) -> None:
    monkeypatch.setattr(crawler_module.httpx, "AsyncClient", FakeAsyncClient)

    crawl_request = CrawlRequest(
        search_results=SearchResults(
            results=[
                SearchResult(url="https://example.com/good", title="Good", content="Snippet", metadata={"engine": "google"}),
                SearchResult(url="https://example.com/missing", title="Missing", content="Snippet", metadata={"engine": "google"}),
            ]
        ),
        crawl_websites=True,
        enable_caching=False,
        timeout_seconds=1.0,
        max_concurrency=2,
    )

    documents = asyncio.run(crawler_module.crawl_documents(crawl_request))
    assert len(documents.documents) == 2
    document = documents.documents[0]
    assert document.title == "Meta Title"
    assert document.canonical_url == "https://example.com/canonical"
    assert document.content_type == "text/html"
    assert document.metadata["engine"] == "google"
    assert document.markdown == "# Title\n\nBody"
    assert FakeAsyncClient.last_requested_url == "https://example.com/missing"
    assert documents.documents[1].crawl_status == "http_error"


def test_crawler_times_out_gracefully(monkeypatch) -> None:
    monkeypatch.setattr(crawler_module.httpx, "AsyncClient", FakeAsyncClient)

    crawl_request = CrawlRequest(
        search_results=SearchResults(
            results=[
                SearchResult(url="https://example.com/slow", title="Slow", content="Snippet", metadata={}),
            ]
        ),
        crawl_websites=True,
        enable_caching=False,
        timeout_seconds=0.01,
        max_concurrency=1,
    )

    documents = asyncio.run(crawler_module.crawl_documents(crawl_request))
    assert len(documents.documents) == 1
    assert documents.documents[0].crawl_status == "timeout"


def test_crawler_passthrough_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(crawler_module.httpx, "AsyncClient", FakeAsyncClient)

    crawl_request = CrawlRequest(
        search_results=SearchResults(
            results=[
                SearchResult(url="https://example.com/good", title="Good", content="Snippet", metadata={"engine": "google"}),
            ]
        ),
        crawl_websites=False,
        enable_caching=False,
        timeout_seconds=1.0,
        max_concurrency=1,
    )

    documents = asyncio.run(crawler_module.crawl_documents(crawl_request))
    assert len(documents.documents) == 1
    assert documents.documents[0].crawl_status == "skipped"
    assert documents.documents[0].markdown == "Snippet"
