"""FastAPI search route integration tests for Quarry."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from api.app import app
from api.middleware import DEFAULT_RATE_LIMIT
from models.clean_document import CleanDocument, CleanDocuments
from models.document import Document, Documents
from models.search import SearchResult, SearchResults
from pipeline import pipeline as pipeline_module


def test_search_endpoint_returns_documents(monkeypatch) -> None:
    async def fake_search_searxng(request):
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

    async def fake_crawl_documents(crawl_request):
        return Documents(
            documents=[
                Document(
                    id="doc-1",
                    url="https://example.com/article",
                    canonical_url="https://example.com/article",
                    title="Example",
                    markdown="# Example\n\nBody",
                    html="<html></html>",
                    metadata={"engine": "google"},
                    crawl_timestamp=datetime.now(UTC),
                    crawl_latency_ms=10.0,
                    crawl_status="success",
                    content_type="text/html",
                )
            ]
        )

    def fake_clean_documents(clean_request):
        return CleanDocuments(
            documents=[
                CleanDocument(
                    id="doc-1",
                    url="https://example.com/article",
                    canonical_url="https://example.com/article",
                    title="Example",
                    markdown="# Example\n\nBody",
                    html="<html></html>",
                    metadata={"engine": "google"},
                    crawl_timestamp=datetime.now(UTC),
                    crawl_latency_ms=10.0,
                    crawl_status="success",
                    content_type="text/html",
                    cleaned_markdown="# Example\n\nBody",
                    original_token_count=4,
                    cleaned_token_count=4,
                    tokens_removed=0,
                    reduction_percentage=0.0,
                    cleaning_latency_ms=2.0,
                    cleaning_steps_applied=["normalize_markdown"],
                )
            ]
        )

    monkeypatch.setattr(pipeline_module, "search_searxng", fake_search_searxng)
    monkeypatch.setattr(pipeline_module, "crawl_documents", fake_crawl_documents)
    monkeypatch.setattr(pipeline_module, "clean_documents", fake_clean_documents)

    app.dependency_overrides[DEFAULT_RATE_LIMIT.dependency] = lambda: None
    try:
        client = TestClient(app)
        response = client.post(
            "/search",
            json={
                "query": "quarry",
                "cleaning_level": 1,
                "crawl_websites": True,
                "enable_caching": False,
                "compress_output": False,
                "enhance_query": False,
                "rank_and_score_deterministically": False,
                "time_range": "day",
                "language": "en",
                "engines": ["google"],
                "categories": ["general"],
                "format": "json",
            },
        )
    finally:
        app.dependency_overrides.pop(DEFAULT_RATE_LIMIT.dependency, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "quarry"
    assert payload["documents"][0]["url"] == "https://example.com/article"
    assert payload["documents"][0]["cleaned_markdown"] == "# Example\n\nBody"
    assert "timings" in payload
    assert payload["timings"]["compression_latency_ms"] == 0.0
    assert payload["timings"]["total_request_latency_ms"] >= 0
