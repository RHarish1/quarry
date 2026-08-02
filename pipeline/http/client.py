"""Shared HTTP client for Quarry."""

from __future__ import annotations

import httpx

from config.settings import settings

_client: httpx.AsyncClient | None = None


async def create_http_client() -> None:
    """Create the shared HTTP client."""

    global _client

    if _client is not None:
        return

    _client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            settings.http_timeout_seconds,
        ),
        limits=httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive_connections,
        ),
        follow_redirects=True,
        headers={
            "User-Agent": settings.user_agent,
        },
    )


def get_http_client() -> httpx.AsyncClient:
    """Return the shared HTTP client."""

    if _client is None:
        raise RuntimeError("HTTP client has not been initialized.")

    return _client


async def close_http_client() -> None:
    """Close the shared HTTP client."""

    global _client

    if _client is None:
        return

    await _client.aclose()
    _client = None
