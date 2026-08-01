"""Trafilatura-based deterministic extractor."""

from __future__ import annotations

import asyncio
import re
from time import perf_counter
from urllib.parse import urlparse

from trafilatura import extract as trafilatura_extract
from trafilatura.metadata import extract_metadata

from pipeline.crawler.extractors.base import BaseExtractor
from pipeline.crawler.types import ExtractionResult, RawDocument


def _markdown_to_plain_text(markdown: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\-\*\+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
    return re.sub(r"\s+", " ", text).strip()


def _fallback_title(url: str) -> str:
    parsed = urlparse(url)
    tail = parsed.path.rstrip("/").split("/")[-1]
    if tail:
        return tail.replace("-", " ").replace("_", " ").strip().title()

    return parsed.netloc or url


async def _extract_with_trafilatura(
    html: str, url: str
) -> tuple[str, str, dict[str, str]]:
    def _run() -> tuple[str, str, dict[str, str]]:
        markdown = (
            trafilatura_extract(
                html,
                url=url,
                output_format="markdown",
                include_links=True,
                include_tables=True,
                include_formatting=True,
                include_comments=False,
                deduplicate=True,
                favor_precision=True,
                no_fallback=False,
            )
            or ""
        )

        metadata = extract_metadata(html, default_url=url)
        title = getattr(metadata, "title", None) or _fallback_title(url)
        extra_metadata = {
            "sitename": getattr(metadata, "sitename", None) or "",
            "author": getattr(metadata, "author", None) or "",
            "url": getattr(metadata, "url", None) or url,
        }

        return (
            title,
            markdown,
            {key: value for key, value in extra_metadata.items() if value},
        )

    return await asyncio.to_thread(_run)


class TrafilaturaExtractor(BaseExtractor):
    """Primary extractor that relies on Trafilatura over raw fetched HTML."""

    name = "trafilatura"

    async def extract(
        self, raw_document: RawDocument, html: str | None = None
    ) -> ExtractionResult:
        started = perf_counter()
        source_html = html or raw_document.raw_html
        title, markdown, metadata = await _extract_with_trafilatura(
            source_html, raw_document.final_url
        )
        plain_text = _markdown_to_plain_text(markdown)
        duration_ms = (perf_counter() - started) * 1000.0

        return ExtractionResult(
            title=title,
            markdown=markdown,
            plain_text=plain_text,
            metadata={**metadata, "source": self.name},
            extraction_method=self.name,
            extraction_confidence=0.0,
            extraction_duration_ms=duration_ms,
            extracted_text_size=len(plain_text),
            extracted_markdown_size=len(markdown),
            source_html=source_html,
        )
