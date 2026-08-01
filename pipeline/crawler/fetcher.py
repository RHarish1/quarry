"""Fetch raw HTML for Quarry crawling."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter

import httpx

from models.search import SearchResult
from pipeline.crawler.types import RawDocument


async def fetch_raw_document(
    search_result: SearchResult,
    *,
    timeout_seconds: float,
) -> RawDocument:
    """Fetch a URL and keep the raw HTML plus response metadata in memory."""

    started = perf_counter()
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout_seconds,
        headers={"User-Agent": "Quarry/1.0"},
    ) as client:
        response = await client.get(
            search_result.url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            },
        )

    fetch_duration_ms = (perf_counter() - started) * 1000.0
    raw_html = response.text
    response_headers = {key.lower(): value for key, value in response.headers.items()}
    content_type = (
        response_headers.get("content-type", "text/html").split(";", 1)[0].strip()
    )

    return RawDocument(
        original_url=search_result.url,
        final_url=str(response.url),
        http_status=response.status_code,
        response_headers=response_headers,
        fetch_timestamp=datetime.now(UTC),
        fetch_duration_ms=fetch_duration_ms,
        raw_html=raw_html,
        html_size=len(raw_html.encode("utf-8")),
        content_type=content_type,
    )
