"""Application settings for Quarry."""

from dataclasses import dataclass, field
import os


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings container."""

    searxng_base_url: str = field(
        default_factory=lambda: os.getenv("SEARXNG_BASE_URL", "http://searxng:8080")
    )
    searxng_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("SEARXNG_TIMEOUT_SECONDS", "20"))
    )


settings = Settings()
