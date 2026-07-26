"""Cleaned document models for Quarry."""

from pydantic import BaseModel, Field

from models.document import Document, Documents


class CleanDocument(Document):
    """Deterministically cleaned document that preserves the raw document fields."""

    cleaned_markdown: str
    original_token_count: int
    cleaned_token_count: int
    tokens_removed: int
    reduction_percentage: float
    cleaning_latency_ms: float
    cleaning_steps_applied: list[str] = Field(default_factory=list)


class CleanDocuments(BaseModel):
    """Collection of cleaned documents."""

    documents: list[CleanDocument] = Field(default_factory=list)


class CleanRequest(BaseModel):
    """Cleaning stage input."""

    documents: Documents
    cleaning_level: int = 0
