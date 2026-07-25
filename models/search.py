"""Search request and response models for Quarry."""

from enum import Enum, IntEnum

from pydantic import BaseModel, Field


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


class SearchMetadata(BaseModel):
    """Per-result metadata."""

    tokens_before_compression: int | None = None
    tokens_after_compression: int | None = None
    websites_dropped_percentage: float | None = None
    compression_rate: float | None = None


class SearchResult(BaseModel):
    """A single search result."""

    url: str
    title: str
    content: str
    metadata: SearchMetadata | None = None


class SearchResponse(BaseModel):
    """Search response payload."""

    results: list[SearchResult] = Field(default_factory=list)
