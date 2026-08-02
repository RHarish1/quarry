"""Search request and response models for Quarry."""

from enum import Enum, IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from models.clean_document import CleanDocument
from pipeline.ranking.constants import DEFAULT_TARGET_DOCUMENTS


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
    """Controls retrieval, optional crawling/ranking, cleaning, and compression."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "GPT-5",
                    "crawl_websites": True,
                    "rank_and_score_deterministically": True,
                    "target_documents": 5,
                    "cleaning_level": 2,
                    "compress_output": True,
                    "target_token_budget": 1024,
                    "enable_caching": True,
                    "engines": ["google"],
                    "language": "en",
                    "categories": [],
                    "time_range": "day",
                }
            ]
        }
    )

    query: str = Field(
        ..., min_length=1, description="Text sent to SearXNG to find candidate URLs."
    )
    cleaning_level: CleaningLevel = Field(
        default=CleaningLevel.LEVEL_0,
        description="Cleaning intensity: 0 normalizes whitespace; 1 removes consent/duplicates; 2 also removes navigation, footer, ads, and duplicate headings; 3 also removes empty sections.",
    )
    crawl_websites: bool = Field(
        default=False,
        description="Fetch candidate URLs and extract page content. When false, Quarry returns SearXNG snippets without fetching pages.",
    )
    enable_caching: bool = Field(
        default=False,
        description="Read and write the Redis response cache. Non-empty completed responses expire after one hour.",
    )
    compress_output: bool = Field(
        default=False,
        description="Run deterministic paragraph-level compression after cleaning.",
    )
    target_documents: int = Field(
        default=DEFAULT_TARGET_DOCUMENTS,
        ge=1,
        description="Maximum number of accepted documents when deterministic ranking is enabled.",
    )
    enhance_query: bool = Field(
        default=False,
        description="Normalize Unicode, quotes, case, punctuation, whitespace, and consecutive duplicate tokens before retrieval.",
    )
    rank_and_score_deterministically: bool = Field(
        default=False,
        description="Filter candidates and crawl them in batches until target_documents quality-qualified documents are found. Has an effect only when crawl_websites is true.",
    )
    time_range: TimeRange | None = Field(
        default=None, description="Optional SearXNG recency filter."
    )
    language: str | None = Field(
        default=None, description="Optional language passed to SearXNG."
    )
    engines: list[str] = Field(
        default_factory=list,
        description="Optional SearXNG engine names. The order does not affect caching.",
    )
    categories: list[str] = Field(
        default_factory=list,
        description="Optional SearXNG category names. The order does not affect caching.",
    )
    target_token_budget: int | None = Field(
        default=None,
        ge=1,
        description="Positive per-document compression budget. Used only when compress_output is true; defaults to 2048 when omitted.",
    )


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
    """Measured latencies for the stages that ran, in milliseconds."""

    search_latency_ms: float = Field(
        description="SearXNG request and result-normalization time."
    )
    crawl_latency_ms: float = Field(
        description="Candidate crawling/extraction time, including ranking when enabled."
    )
    cleaning_latency_ms: float = Field(
        description="Deterministic document-cleaning time."
    )
    compression_latency_ms: float = Field(
        default=0.0,
        description="Deterministic compression time; zero when compression did not run.",
    )
    total_request_latency_ms: float = Field(
        description="Wall-clock pipeline time from retrieval through optional compression."
    )


class SearchResponse(BaseModel):
    """Normalized search result and timing information."""

    request_id: str
    query: str
    timings: SearchTimings
    documents: list[CleanDocument] = Field(default_factory=list)
