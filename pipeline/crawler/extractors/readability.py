"""Readability fallback extractor for Quarry."""

from __future__ import annotations

import asyncio
from time import perf_counter

from markdownify import markdownify as markdownify_html
from readability import Document as ReadabilityDocument

from pipeline.crawler.extractors.base import BaseExtractor
from pipeline.crawler.extractors.trafilatura import (
    _fallback_title,
    _markdown_to_plain_text,
)
from pipeline.crawler.types import ExtractionResult, RawDocument


async def _extract_with_readability(
    html: str, url: str
) -> tuple[str, str, dict[str, str], str]:
    def _run() -> tuple[str, str, dict[str, str], str]:
        document = ReadabilityDocument(html)
        summary_html = document.summary(html_partial=True) or html
        markdown = markdownify_html(
            summary_html,
            heading_style="ATX",
            bullets="-",
            strip=["span"],
            escape_asterisks=False,
            escape_underscores=False,
        )
        title = document.title() or _fallback_title(url)
        return title, markdown, {"source": "readability"}, summary_html

    return await asyncio.to_thread(_run)


class ReadabilityExtractor(BaseExtractor):
    """Final article fallback using readability-lxml plus deterministic markdown conversion."""

    name = "readability"

    async def extract(
        self, raw_document: RawDocument, html: str | None = None
    ) -> ExtractionResult:
        started = perf_counter()
        source_html = html or raw_document.raw_html
        title, markdown, metadata, summary_html = await _extract_with_readability(
            source_html, raw_document.final_url
        )
        plain_text = _markdown_to_plain_text(markdown)
        duration_ms = (perf_counter() - started) * 1000.0

        return ExtractionResult(
            title=title,
            markdown=markdown,
            plain_text=plain_text,
            metadata=metadata,
            extraction_method=self.name,
            extraction_confidence=0.0,
            extraction_duration_ms=duration_ms,
            extracted_text_size=len(plain_text),
            extracted_markdown_size=len(markdown),
            source_html=summary_html,
        )
