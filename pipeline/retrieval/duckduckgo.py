"""DuckDuckGo Search integration for Quarry."""

import asyncio
import logging

from duckduckgo_search import DDGS

from models.search import SearchResult, SearchResults

logger = logging.getLogger(__name__)


def _run_ddgs_sync(query: str, count: int) -> list[dict]:
    """Synchronous wrapper for the DDGS library."""
    # We use backend="lite" or "html" because they are much more stable than the API backend
    return DDGS().text(query, max_results=count, backend="lite")


async def search_duckduckgo(query: str, count: int = 10) -> SearchResults:
    """Execute a search against DuckDuckGo asynchronously."""
    results = []

    try:
        # Offload the blocking synchronous call to a background thread
        raw_results = await asyncio.to_thread(_run_ddgs_sync, query, count)

        for r in raw_results:
            results.append(
                SearchResult(
                    url=r.get("href", ""),
                    title=r.get("title", ""),
                    content=r.get("body", ""),
                    metadata={
                        "source": "duckduckgo",
                    },
                )
            )
    except Exception as e:  # noqa
        logger.warning(f"DuckDuckGo search failed (possibly rate limited): {e}")

    return SearchResults(results=results)
