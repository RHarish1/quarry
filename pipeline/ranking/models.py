"""Internal models for the ranking pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from models.document import Document
from models.search import SearchResult


@dataclass(slots=True)
class RankedCandidate:
    """A crawled document with its quality score."""

    search_result: SearchResult
    document: Document
    quality_score: float


@dataclass(slots=True)
class RejectedCandidate:
    """A candidate rejected during ranking."""

    search_result: SearchResult
    reason: str


@dataclass(slots=True)
class RankingResult:
    """Output of the ranking pipeline."""

    accepted: list[RankedCandidate] = field(default_factory=list)
    rejected: list[RejectedCandidate] = field(default_factory=list)
