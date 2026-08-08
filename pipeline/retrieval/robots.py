from __future__ import annotations

import asyncio
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
    # Create a list of coroutines to run concurrently
    tasks = [can_fetch(result.url) for result in candidates]

    # Run them all at once
    fetch_results = await asyncio.gather(*tasks, return_exceptions=True)

    filtered: list[SearchResult] = []
    for result, can_be_fetched in zip(candidates, fetch_results):
        if isinstance(can_be_fetched, Exception) or not can_be_fetched:
            logger.info("Skipping %s (robots.txt or error)", result.url)
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

            async def _fetch_robots():
                return await client.get(robots_url)

            async def _retry_fetch():
                return await retry(
                    _fetch_robots,
                    provider="robots.txt",
                    policy=DEFAULT_RETRY,
                )

            response = await ROBOTS_BREAKER.execute(_retry_fetch)

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
