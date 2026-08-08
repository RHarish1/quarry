"""Application settings for Quarry."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings container."""

    searxng_base_url: str = field(
        default_factory=lambda: os.getenv("SEARXNG_BASE_URL", "http://localhost:8080")
    )
    searxng_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("SEARXNG_TIMEOUT_SECONDS", "20"))
    )
    crawl_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("CRAWL_TIMEOUT_SECONDS", "30"))
    )
    crawl_max_concurrency: int = field(
        default_factory=lambda: int(os.getenv("CRAWL_MAX_CONCURRENCY", "4"))
    )
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://redis:6379/0")
    )
    user_agent: str = "QuarryBot/0.3"
    http_timeout_seconds: float = 30.0
    http_max_connections: int = 100
    http_max_keepalive_connections: int = 20


settings = Settings()
