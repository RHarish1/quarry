"""Raw document models for Quarry."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Raw crawled content preserved before deterministic cleaning."""

    id: str
    url: str
    canonical_url: str
    title: str
    markdown: str
    html: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    crawl_timestamp: datetime
    crawl_latency_ms: float
    crawl_status: str
    content_type: str


class Documents(BaseModel):
    """Collection of raw documents."""

    documents: list[Document] = Field(default_factory=list)
