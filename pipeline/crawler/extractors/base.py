"""Base extractor contract for Quarry."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pipeline.crawler.types import ExtractionResult, RawDocument


class BaseExtractor(ABC):
    """Common async extractor interface."""

    name: str

    @abstractmethod
    async def extract(self, raw_document: RawDocument, html: str | None = None) -> ExtractionResult:
        """Extract structured content from the supplied HTML."""
