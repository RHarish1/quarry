"""Recall helpers for the ranking pipeline."""

from __future__ import annotations

from typing_extensions import deprecated

from models.search import SearchResult


@deprecated("Doesn't work well in async")
def needs_recall(
    *,
    accepted: int,
    requested: int,
    remaining: int,
) -> bool:
    """
    Determine whether another recall iteration is required.

    Recall is needed if:
    - We still need more accepted documents.
    - There are remaining search candidates.
    """

    return accepted < requested and remaining > 0


@deprecated("Not required in async")
def select_recall_candidates(
    candidates: list[SearchResult],
    *,
    start: int,
    count: int,
) -> list[SearchResult]:
    """
    Select the next batch of candidates to crawl.

    Example
    -------
    candidates = [0,1,2,3,4,5]
    start = 2
    count = 2

    Returns:
        [2,3]
    """

    if start >= len(candidates):
        return []

    end = min(start + count, len(candidates))
    return candidates[start:end]


@deprecated("Not required in async")
def remaining_candidates(
    candidates: list[SearchResult],
    *,
    current_index: int,
) -> int:
    """
    Return the number of candidates that have not yet been processed.
    """

    return max(0, len(candidates) - current_index)


@deprecated("Not required in async")
def exhausted(
    candidates: list[SearchResult],
    *,
    current_index: int,
) -> bool:
    """
    Return True if there are no more candidates available.
    """

    return current_index >= len(candidates)
