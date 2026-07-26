"""Search request and response models for Quarry."""

from enum import Enum, IntEnum
from typing import Any

from pydantic import BaseModel, Field

from models.clean_document import CleanDocument


class CleaningLevel(IntEnum):
    """Cleaning intensity levels."""

    LEVEL_0 = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


class FlexibleFormatting(str, Enum):
    """Flexible output formatting options."""

    CONTENT_ONLY = "content_only"
    DEFAULT_WITH_METADATA = "default_with_metadata"
    URL_TITLE_ONLY = "url_title_only"
    URL_TITLE_CONTENT = "url_title_content"


class TimeRange(str, Enum):
    """Supported time range filters."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class SearchFormat(str, Enum):
    """Supported response/output formats."""

    JSON = "json"
    CSV = "csv"
    CSS = "css"
    RSS = "rss"


class SearchRequest(BaseModel):
    """Search request payload."""

    query: str
    cleaning_level: CleaningLevel = CleaningLevel.LEVEL_0
    crawl_websites: bool = False
    enable_caching: bool = False
    compress_output_using_headroom: bool = False
    flexible_formatting: FlexibleFormatting = FlexibleFormatting.DEFAULT_WITH_METADATA
    enhance_query: bool = False
    rank_and_score_deterministically: bool = False
    time_range: TimeRange | None = None
    language: str | None = None
    engines: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    format: SearchFormat = SearchFormat.JSON


class SearchResult(BaseModel):
    """Search provider result."""

    url: str
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResults(BaseModel):
    """Collection of search provider results."""

    results: list[SearchResult] = Field(default_factory=list)


class CrawlRequest(BaseModel):
    """Crawler stage input."""

    search_results: SearchResults
    crawl_websites: bool = False
    enable_caching: bool = False
    timeout_seconds: float = 30.0
    max_concurrency: int = 4


class SearchTimings(BaseModel):
    """Search pipeline timings."""

    search_latency_ms: float
    crawl_latency_ms: float
    cleaning_latency_ms: float
    total_request_latency_ms: float


class SearchResponse(BaseModel):
    """Search response payload."""

    query: str
    timings: SearchTimings
    documents: list[CleanDocument] = Field(default_factory=list)
