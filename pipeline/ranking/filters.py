"""Deterministic candidate filtering before crawling."""

from __future__ import annotations

from urllib.parse import urlparse

from models.search import SearchResult

from .constants import BLOCKED_DOMAINS, BLOCKED_FILE_EXTENSIONS, BLOCKED_PATH_KEYWORDS


def _normalize_url(url: str) -> str:
    """Normalize URL for duplicate detection."""
    parsed = urlparse(url)

    hostname = parsed.netloc.lower()
    hostname = hostname.removeprefix("www.")

    path = parsed.path.rstrip("/")

    return f"{parsed.scheme.lower()}://{hostname}{path}"


def _is_http(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def _has_blocked_extension(path: str) -> bool:
    path = path.lower()
    return any(path.endswith(ext) for ext in BLOCKED_FILE_EXTENSIONS)


def _is_blocked_domain(hostname: str) -> bool:
    hostname = hostname.lower()

    hostname = hostname.removeprefix("www.")

    return any(
        hostname == domain.removeprefix("www.")
        or hostname.endswith("." + domain.removeprefix("www."))
        for domain in BLOCKED_DOMAINS
    )


def _has_blocked_path(path: str) -> bool:
    path = path.lower()
    return any(keyword in path for keyword in BLOCKED_PATH_KEYWORDS)


def filter_candidates(
    candidates: list[SearchResult],
) -> list[SearchResult]:
    """
    Remove obviously poor crawl candidates.

    This filter should be conservative.
    Anything that *might* contain useful content should survive.
    """

    filtered: list[SearchResult] = []
    seen: set[str] = set()

    for candidate in candidates:
        if not _is_http(candidate.url):
            continue

        parsed = urlparse(candidate.url)

        if _is_blocked_domain(parsed.netloc):
            continue

        if _has_blocked_extension(parsed.path):
            continue

        if _has_blocked_path(parsed.path):
            continue

        normalized = _normalize_url(candidate.url)

        if normalized in seen:
            continue

        seen.add(normalized)
        filtered.append(candidate)

    return filtered
