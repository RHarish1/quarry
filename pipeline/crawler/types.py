"""Internal crawler data models for Quarry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from models.document import Document


@dataclass(slots=True)
class RawDocument:
    """HTML and transport metadata captured during fetch."""

    original_url: str
    final_url: str
    http_status: int
    response_headers: dict[str, str]
    fetch_timestamp: datetime
    fetch_duration_ms: float
    raw_html: str
    html_size: int
    content_type: str


@dataclass(slots=True)
class ExtractedDocument:
    """Deterministic extraction output produced by the extractor manager."""

    title: str
    markdown: str
    plain_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    extraction_method: str = ""
    extraction_confidence: float = 0.0
    extraction_duration_ms: float = 0.0
    extracted_text_size: int = 0
    extracted_markdown_size: int = 0
    source_html: str | None = None

    def to_document(
        self, raw_document: RawDocument, *, crawl_status: str | None = None
    ) -> Document:
        """Convert an internal extracted document into the downstream raw document model."""

        safe_metadata: dict[str, Any] = {
            "source": "fetched_html",
            "fetch_timestamp": raw_document.fetch_timestamp.isoformat(),
            "fetch_duration_ms": raw_document.fetch_duration_ms,
            "html_size": raw_document.html_size,
            "content_type": raw_document.content_type,
            "extraction_method": self.extraction_method,
            "extraction_confidence": self.extraction_confidence,
            "extraction_duration_ms": self.extraction_duration_ms,
            "extracted_text_size": self.extracted_text_size,
            "extracted_markdown_size": self.extracted_markdown_size,
        }
        if self.metadata:
            safe_metadata.update(self.metadata)

        document_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{raw_document.original_url}|{raw_document.final_url}|{self.title}",
            )
        )

        return Document(
            id=document_id,
            url=raw_document.final_url,
            canonical_url=raw_document.final_url,
            title=self.title,
            markdown=self.markdown,
            html=None,
            metadata=safe_metadata,
            crawl_timestamp=raw_document.fetch_timestamp,
            crawl_latency_ms=raw_document.fetch_duration_ms
            + self.extraction_duration_ms,
            crawl_status=crawl_status or self.extraction_method or "success",
            content_type=raw_document.content_type,
        )


ExtractionResult = ExtractedDocument
