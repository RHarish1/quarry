"""Crawler stage tests for Quarry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from models.search import CrawlRequest, SearchResult, SearchResults
from pipeline.crawler import crawler as crawler_module


@dataclass
class FakeMarkdown:
    raw_markdown: str


class FakeCrawlResult:
    def __init__(
        self,
        *,
        success: bool,
        url: str,
        markdown: str,
        html: str,
        metadata: dict[str, object] | None = None,
        response_headers: dict[str, str] | None = None,
        error_message: str | None = None,
    ) -> None:
        self.success = success
        self.url = url
        self.markdown = FakeMarkdown(markdown)
        self.html = html
        self.metadata = metadata or {}
        self.response_headers = response_headers or {}
        self.error_message = error_message


class FakeRunConfig:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class FakeBrowserConfig:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class FakeCacheMode:
    ENABLED = "enabled"
    BYPASS = "bypass"


class FakeAsyncWebCrawler:
    last_run_config: FakeRunConfig | None = None

    def __init__(self, config=None) -> None:
        self.config = config

    async def __aenter__(self) -> "FakeAsyncWebCrawler":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def arun(self, url: str, config: FakeRunConfig):
        FakeAsyncWebCrawler.last_run_config = config
        if url.endswith("/good"):
            return FakeCrawlResult(
                success=True,
                url="https://example.com/good",
                markdown="# Title\n\nBody",
                html=(
                    "<html><head><title>Meta Title</title>"
                    "<link rel='canonical' href='https://example.com/canonical'/></head>"
                    "<body>Body</body></html>"
                ),
                metadata={"title": "Meta Title"},
                response_headers={"content-type": "text/html; charset=utf-8"},
            )

        if url.endswith("/robots"):
            return FakeCrawlResult(
                success=False,
                url=url,
                markdown="",
                html="",
                error_message="Blocked by robots.txt",
            )

        if url.endswith("/slow"):
            await asyncio.sleep(0.05)
            return FakeCrawlResult(
                success=True,
                url=url,
                markdown="slow",
                html="<html></html>",
            )

        return FakeCrawlResult(success=False, url=url, markdown="", html="", error_message="boom")


def _fake_load_crawl4ai():
    return FakeAsyncWebCrawler, FakeBrowserConfig, FakeCacheMode, FakeRunConfig


def test_crawler_skips_failures_and_preserves_metadata(monkeypatch) -> None:
    monkeypatch.setattr(crawler_module, "_load_crawl4ai", _fake_load_crawl4ai)

    crawl_request = CrawlRequest(
        search_results=SearchResults(
            results=[
                SearchResult(url="https://example.com/good", title="Good", content="Snippet", metadata={"engine": "google"}),
                SearchResult(url="https://example.com/robots", title="Robots", content="Snippet", metadata={"engine": "google"}),
                SearchResult(url="https://example.com/bad", title="Bad", content="Snippet", metadata={"engine": "google"}),
            ]
        ),
        crawl_websites=True,
        enable_caching=False,
        timeout_seconds=1.0,
        max_concurrency=2,
    )

    documents = asyncio.run(crawler_module.crawl_documents(crawl_request))
    assert len(documents.documents) == 3
    document = documents.documents[0]
    assert document.title == "Meta Title"
    assert document.canonical_url == "https://example.com/canonical"
    assert document.content_type == "text/html"
    assert document.metadata["engine"] == "google"
    assert FakeAsyncWebCrawler.last_run_config.check_robots_txt is True
    assert documents.documents[1].crawl_status == "robots_blocked"
    assert documents.documents[2].crawl_status == "crawl_failed"


def test_crawler_times_out_gracefully(monkeypatch) -> None:
    monkeypatch.setattr(crawler_module, "_load_crawl4ai", _fake_load_crawl4ai)

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
    monkeypatch.setattr(crawler_module, "_load_crawl4ai", _fake_load_crawl4ai)

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
