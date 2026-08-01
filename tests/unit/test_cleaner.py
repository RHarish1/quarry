"""Deterministic cleaner tests for Quarry."""

from datetime import UTC, datetime

from models.clean_document import CleanRequest
from models.document import Document, Documents
from pipeline.cleaning.cleaner import clean_documents


def test_cleaner_removes_duplicates_and_boilerplate() -> None:
    document = Document(
        id="doc-1",
        url="https://example.com/article",
        canonical_url="https://example.com/article",
        title="Example",
        markdown=(
            "# Example\n\n"
            "Paragraph one.\n\n"
            "Paragraph one.\n\n"
            "## Navigation\n\n"
            "Home\n\n"
            "```python\nprint('keep me')\n```\n\n"
            "## Example\n\n"
            "Final paragraph.\n\n"
            "Cookie banner accept all"
        ),
        html="<html></html>",
        metadata={"source": "fixture"},
        crawl_timestamp=datetime.now(UTC),
        crawl_latency_ms=12.5,
        crawl_status="success",
        content_type="text/html",
    )

    cleaned_documents = clean_documents(
        CleanRequest(documents=Documents(documents=[document]), cleaning_level=3)
    )

    assert len(cleaned_documents.documents) == 1
    cleaned_document = cleaned_documents.documents[0]
    assert "Cookie banner" not in cleaned_document.cleaned_markdown
    assert cleaned_document.cleaned_markdown.count("Paragraph one.") == 1
    assert "```python" in cleaned_document.cleaned_markdown
    assert cleaned_document.original_token_count >= cleaned_document.cleaned_token_count
    assert cleaned_document.tokens_removed >= 0
    assert cleaned_document.reduction_percentage >= 0
    assert "remove_duplicate_paragraphs" in cleaned_document.cleaning_steps_applied
