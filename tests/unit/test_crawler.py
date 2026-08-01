"""Crawler stage tests for Quarry."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from models.search import CrawlRequest, SearchResult, SearchResults
from pipeline.crawler import crawler as crawler_module
from pipeline.crawler.extractors.base import BaseExtractor
from pipeline.crawler.manager import ExtractorManager
from pipeline.crawler.quality import ExtractionQualityThresholds, score_extraction
from pipeline.crawler.types import ExtractedDocument, RawDocument


@dataclass(slots=True)
class FakeExtractor(BaseExtractor):
    name: str
    markdown: str
    title: str
    method: str

    async def extract(
        self, raw_document: RawDocument, html: str | None = None
    ) -> ExtractedDocument:
        plain_text = self.markdown.replace("#", "").replace("-", " ").strip()
        return ExtractedDocument(
            title=self.title,
            markdown=self.markdown,
            plain_text=plain_text,
            metadata={"source": self.method},
            extraction_method=self.method,
            extraction_confidence=0.0,
            extraction_duration_ms=1.0,
            extracted_text_size=len(plain_text),
            extracted_markdown_size=len(self.markdown),
            source_html=html or raw_document.raw_html,
        )


def _article_raw_document() -> RawDocument:
    html = """
    <html>
      <head><title>Article Title</title></head>
      <body>
        <main>
          <article>
            <h1>Article Title</h1>
            <p>This is a sufficiently long body paragraph with many meaningful words for extraction quality.</p>
            <p>This second paragraph adds more content and keeps the article-like structure intact.</p>
            <p>The third paragraph ensures the content has enough paragraph density for scoring.</p>
            <p>The fourth paragraph pushes the total text size over the acceptance threshold.</p>
          </article>
        </main>
      </body>
    </html>
    """.strip()

    return RawDocument(
        original_url="https://example.com/article",
        final_url="https://example.com/article",
        http_status=200,
        response_headers={"content-type": "text/html; charset=utf-8"},
        fetch_timestamp=datetime.now(UTC),
        fetch_duration_ms=12.0,
        raw_html=html,
        html_size=len(html.encode("utf-8")),
        content_type="text/html",
    )


def test_quality_accepts_article_like_content() -> None:
    raw_document = _article_raw_document()
    thresholds = ExtractionQualityThresholds(
        minimum_character_count=300,
        minimum_word_count=40,
        minimum_score=0.67,
    )
    extracted_document = ExtractedDocument(
        title="Article Title",
        markdown=(
            "# Article Title\n\n"
            "This is a sufficiently long body paragraph with many meaningful words for extraction quality.\n\n"
            "This second paragraph adds more content and keeps the article-like structure intact.\n\n"
            "The third paragraph ensures the content has enough paragraph density for scoring.\n\n"
            "The fourth paragraph pushes the total text size over the acceptance threshold."
        ),
        plain_text=(
            "Article Title This is a sufficiently long body paragraph with many meaningful words for extraction quality. "
            "This second paragraph adds more content and keeps the article-like structure intact. "
            "The third paragraph ensures the content has enough paragraph density for scoring. "
            "The fourth paragraph pushes the total text size over the acceptance threshold."
        ),
        extraction_method="trafilatura",
        extraction_confidence=0.0,
        extracted_text_size=360,
        extracted_markdown_size=360,
        source_html=raw_document.raw_html,
    )

    quality = score_extraction(raw_document, extracted_document, thresholds)

    assert quality.title_present is True
    assert quality.accepted is True
    assert quality.score >= thresholds.minimum_score


def test_extractor_manager_falls_back_to_later_extractor() -> None:
    raw_document = _article_raw_document()
    thresholds = ExtractionQualityThresholds(
        minimum_character_count=300,
        minimum_word_count=40,
        minimum_score=0.67,
    )
    manager = ExtractorManager(
        extractors=[
            FakeExtractor(
                name="primary", markdown="# nav", title="Nav", method="trafilatura"
            ),
            FakeExtractor(
                name="fallback",
                markdown=(
                    "# Article Title\n\n"
                    "This is a sufficiently long body paragraph with many meaningful words for extraction quality.\n\n"
                    "This second paragraph adds more content and keeps the article-like structure intact.\n\n"
                    "The third paragraph ensures the content has enough paragraph density for scoring.\n\n"
                    "The fourth paragraph pushes the total text size over the acceptance threshold."
                ),
                title="Article Title",
                method="readability",
            ),
        ],
        thresholds=thresholds,
    )

    extracted_document = asyncio.run(manager.extract(raw_document))

    assert extracted_document.extraction_method == "readability"
    assert extracted_document.title == "Article Title"
    assert extracted_document.extraction_confidence >= thresholds.minimum_score


def test_crawler_preserves_internal_html_only(monkeypatch) -> None:
    raw_document = _article_raw_document()

    async def fake_fetch_raw_document(search_result, timeout_seconds):
        return raw_document

    class FakeManager:
        async def extract(self, raw_document: RawDocument) -> ExtractedDocument:
            return ExtractedDocument(
                title="Article Title",
                markdown="# Article Title\n\nBody paragraph with enough content to pass the cleaner.",
                plain_text="Article Title Body paragraph with enough content to pass the cleaner.",
                metadata={"source": "fake"},
                extraction_method="fake",
                extraction_confidence=0.91,
                extraction_duration_ms=3.0,
                extracted_text_size=72,
                extracted_markdown_size=72,
                source_html=raw_document.raw_html,
            )

    monkeypatch.setattr(crawler_module, "fetch_raw_document", fake_fetch_raw_document)
    monkeypatch.setattr(crawler_module, "ExtractorManager", lambda: FakeManager())

    crawl_request = CrawlRequest(
        search_results=SearchResults(
            results=[
                SearchResult(
                    url="https://example.com/good",
                    title="Good",
                    content="Snippet",
                    metadata={"engine": "google"},
                ),
                SearchResult(
                    url="https://example.com/missing",
                    title="Missing",
                    content="Snippet",
                    metadata={"engine": "google"},
                ),
            ]
        ),
        crawl_websites=True,
        enable_caching=False,
        timeout_seconds=1.0,
        max_concurrency=2,
    )

    documents = asyncio.run(crawler_module.crawl_documents(crawl_request))

    assert len(documents.documents) == 1
    document = documents.documents[0]
    assert document.html is None
    assert document.title == "Article Title"
    assert document.markdown.startswith("# Article Title")
    assert document.metadata["extraction_method"] == "fake"
    assert document.crawl_status == "fake"
