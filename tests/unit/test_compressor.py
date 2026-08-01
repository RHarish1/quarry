"""Tests for deterministic document compression."""

from datetime import UTC, datetime

from models.clean_document import CleanDocument, CleanDocuments
from pipeline.compression.compressor import compress_documents


def _document(markdown: str) -> CleanDocument:
    return CleanDocument(
        id="document-1",
        url="https://example.com/article",
        canonical_url="https://example.com/article",
        title="Example",
        markdown=markdown,
        html=None,
        metadata={},
        crawl_timestamp=datetime.now(UTC),
        crawl_latency_ms=0.0,
        crawl_status="success",
        content_type="text/html",
        cleaned_markdown=markdown,
        original_token_count=100,
        cleaned_token_count=100,
        tokens_removed=0,
        reduction_percentage=0.0,
        cleaning_latency_ms=0.0,
        cleaning_steps_applied=["normalize_markdown"],
    )


def test_compression_uses_requested_budget_and_records_the_step() -> None:
    markdown = (
        "First paragraph contains enough detail to be retained.\n\n"
        "Second paragraph contains enough detail to exceed the budget."
    )

    documents, latency_ms = compress_documents(
        CleanDocuments(documents=[_document(markdown)]), token_budget=13
    )

    compressed = documents.documents[0]
    assert latency_ms >= 0.0
    assert compressed.cleaned_markdown == "First paragraph contains enough detail to be retained."
    assert compressed.cleaned_token_count <= 13
    assert compressed.tokens_removed > 0
    assert compressed.cleaning_steps_applied[-1] == "deterministic_compression"


def test_compression_uses_the_default_budget_when_none_is_supplied() -> None:
    documents, latency_ms = compress_documents(
        CleanDocuments(documents=[_document("A sufficiently long paragraph for compression.")])
    )

    assert latency_ms >= 0.0
    assert documents.documents[0].cleaned_markdown
