from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from models.search import SearchResult, SearchResults

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
    user_agent: str = "QuarryBot/1.0",
) -> bool:
    parsed = urlparse(url)
    host = f"{parsed.scheme}://{parsed.netloc}"

    if host not in _cache:
        robots_url = urljoin(host, "/robots.txt")

        parser = RobotFileParser()

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(robots_url)

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
