from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from config.settings import settings
from models.search import SearchResult, SearchResults
from pipeline.http import get_http_client
from pipeline.resilience import (
    DEFAULT_RETRY,
    FAST_PROVIDER_BREAKER,
    CircuitBreaker,
    retry,
)

ROBOTS_BREAKER = CircuitBreaker(
    name="robots",
    failure_threshold=FAST_PROVIDER_BREAKER.failure_threshold,
    recovery_timeout=FAST_PROVIDER_BREAKER.recovery_timeout,
)
_cache: dict[str, RobotFileParser] = {}
logger = logging.getLogger(__name__)


async def can_crawl(candidates: list[SearchResult]) -> SearchResults:
    filtered: list[SearchResult] = []

    for result in candidates:
        if not await can_fetch(result.url):
            logger.info("Skipping %s (robots.txt)", result.url)
            continue

        filtered.append(result)

    return SearchResults(results=filtered)


async def can_fetch(
    url: str,
    user_agent: str = settings.user_agent,
) -> bool:
    parsed = urlparse(url)
    host = f"{parsed.scheme}://{parsed.netloc}"

    if host not in _cache:
        robots_url = urljoin(host, "/robots.txt")

        parser = RobotFileParser()

        try:
            client = get_http_client()
            response = await ROBOTS_BREAKER.execute(
                lambda: retry(
                    lambda: client.get(robots_url),
                    provider="robots.txt",
                    policy=DEFAULT_RETRY,
                )
            )

            if response.status_code == 404:
                return True

            if response.status_code >= 400:
                return False

            parser.parse(response.text.splitlines())
            _cache[host] = parser

        except Exception as ex:  # noqa
            logger.exception("Failed to fetch robots.txt")
            return False

    return _cache[host].can_fetch(user_agent, url)
