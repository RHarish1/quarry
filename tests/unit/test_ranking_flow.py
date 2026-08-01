"""Ranking flow tests for Quarry."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from models.clean_document import CleanDocument, CleanDocuments
from models.document import Document, Documents
from models.search import (
    CleaningLevel,
    CrawlRequest,
    SearchFormat,
    SearchRequest,
    SearchResult,
    SearchResults,
)
from pipeline import pipeline as pipeline_module
from pipeline.ranking import manager as ranking_manager


def _make_document(url: str, score: float) -> Document:
    return Document(
        id=url,
        url=url,
        canonical_url=url,
        title="Title",
        markdown="Body content",
        html=None,
        metadata={"extraction_confidence": score},
        crawl_timestamp=datetime.now(UTC),
        crawl_latency_ms=1.0,
        crawl_status="success",
        content_type="text/html",
    )


def test_rank_documents_uses_extraction_confidence(monkeypatch) -> None:
    async def fake_crawl_documents(crawl_request: CrawlRequest) -> Documents:
        urls = [result.url for result in crawl_request.search_results.results]

        if urls == ["https://example.com/1", "https://example.com/2"]:
            return Documents(
                documents=[
                    _make_document("https://example.com/1", 0.70),
                    _make_document("https://example.com/2", 0.20),
                ]
            )

        if urls == ["https://example.com/3"]:
            return Documents(documents=[_make_document("https://example.com/3", 0.95)])

        return Documents()

    monkeypatch.setattr(ranking_manager, "crawl_documents", fake_crawl_documents)

    search_results = SearchResults(
        results=[
            SearchResult(url="https://example.com/1", title="A", content="x"),
            SearchResult(url="https://example.com/2", title="B", content="y"),
            SearchResult(url="https://example.com/3", title="C", content="z"),
        ]
    )
    crawl_request = CrawlRequest(
        search_results=search_results,
        crawl_websites=True,
        max_concurrency=2,
    )

    ranked = asyncio.run(
        ranking_manager.rank_documents(
            search_results,
            target_documents=2,
            crawl_request=crawl_request,
        )
    )

    assert len(ranked.documents) == 2
    assert ranked.documents[0].url == "https://example.com/3"
    assert ranked.documents[0].metadata["quality_score"] == 0.95
    assert ranked.documents[1].url == "https://example.com/1"
    assert ranked.documents[1].metadata["quality_score"] == 0.70


def test_pipeline_uses_ranking_when_enabled(monkeypatch) -> None:
    async def fake_search_searxng(request: SearchRequest) -> SearchResults:
        return SearchResults(
            results=[
                SearchResult(
                    url="https://example.com/article",
                    title="Example",
                    content="Snippet",
                    metadata={"engine": "google"},
                )
            ]
        )

    async def fake_rank_documents(search_results, *, target_documents, crawl_request):
        return Documents(documents=[_make_document("https://example.com/article", 0.9)])

    def fake_clean_documents(clean_request):
        source_document = clean_request.documents.documents[0]
        return CleanDocuments(
            documents=[
                CleanDocument(
                    **source_document.model_dump(),
                    cleaned_markdown=source_document.markdown,
                    original_token_count=2,
                    cleaned_token_count=2,
                    tokens_removed=0,
                    reduction_percentage=0.0,
                    cleaning_latency_ms=0.1,
                    cleaning_steps_applied=["normalize_markdown"],
                )
            ]
        )

    def fake_compress_documents(documents, *, token_budget):
        assert token_budget == 128
        return documents, 12.5

    monkeypatch.setattr(pipeline_module, "search_searxng", fake_search_searxng)
    monkeypatch.setattr(pipeline_module, "rank_documents", fake_rank_documents)
    monkeypatch.setattr(pipeline_module, "clean_documents", fake_clean_documents)
    monkeypatch.setattr(
        pipeline_module, "compress_documents", fake_compress_documents
    )

    request = SearchRequest(
        query="quarry",
        cleaning_level=CleaningLevel.LEVEL_1,
        crawl_websites=True,
        rank_and_score_deterministically=True,
        compress_output=True,
        target_token_budget=128,
        format=SearchFormat.JSON,
    )

    response = asyncio.run(pipeline_module.execute_search_pipeline(request))

    assert response.query == "quarry"
    assert len(response.documents) == 1
    assert response.documents[0].url == "https://example.com/article"
    assert response.timings.compression_latency_ms == 12.5
    assert response.timings.total_request_latency_ms >= 0.0


def test_pipeline_sets_compression_latency_to_zero_when_search_fails(
    monkeypatch,
) -> None:
    async def failing_search_searxng(request: SearchRequest) -> SearchResults:
        raise RuntimeError("SearXNG unavailable")

    monkeypatch.setattr(pipeline_module, "search_searxng", failing_search_searxng)

    response = asyncio.run(
        pipeline_module.execute_search_pipeline(
            SearchRequest(query="quarry", compress_output=True)
        )
    )

    assert response.documents == []
    assert response.timings.search_latency_ms >= 0.0
    assert response.timings.crawl_latency_ms == 0.0
    assert response.timings.cleaning_latency_ms == 0.0
    assert response.timings.compression_latency_ms == 0.0
