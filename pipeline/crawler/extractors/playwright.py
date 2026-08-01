"""Playwright-rendered Trafilatura extractor."""

from __future__ import annotations

from time import perf_counter

from playwright.async_api import async_playwright

from pipeline.crawler.extractors.base import BaseExtractor
from pipeline.crawler.extractors.trafilatura import _extract_with_trafilatura, _markdown_to_plain_text
from pipeline.crawler.types import ExtractionResult, RawDocument


async def _render_html(url: str, timeout_seconds: float) -> str:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 1200})
            await page.goto(url, wait_until="networkidle", timeout=int(timeout_seconds * 1000))
            await page.wait_for_load_state("networkidle", timeout=int(timeout_seconds * 1000))
            return await page.content()
        finally:
            await browser.close()


class PlaywrightTrafilaturaExtractor(BaseExtractor):
    """Fallback extractor that renders JavaScript before running Trafilatura."""

    name = "playwright_trafilatura"

    async def extract(self, raw_document: RawDocument, html: str | None = None) -> ExtractionResult:
        started = perf_counter()
        try:
            rendered_html = await _render_html(raw_document.final_url, timeout_seconds=max(raw_document.fetch_duration_ms / 1000.0, 30.0))
            title, markdown, metadata = await _extract_with_trafilatura(rendered_html, raw_document.final_url)
            source_html = rendered_html
        except Exception as exc:
            rendered_html = html or raw_document.raw_html
            title, markdown, metadata = await _extract_with_trafilatura(rendered_html, raw_document.final_url)
            metadata = {**metadata, "render_error": str(exc)}
            source_html = rendered_html

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