"""Quality filtering helpers for the ranking pipeline."""

from __future__ import annotations

from .models import RankedCandidate


def filter_quality(
    candidates: list[RankedCandidate],
    minimum_score: float,
) -> list[RankedCandidate]:
    """
    Remove candidates below the minimum quality threshold.
    """

    return [
        candidate
        for candidate in candidates
        if candidate.quality_score >= minimum_score
    ]


def sort_by_quality(
    candidates: list[RankedCandidate],
) -> list[RankedCandidate]:
    """
    Sort candidates from highest quality to lowest.
    """

    return sorted(
        candidates,
        key=lambda candidate: candidate.quality_score,
        reverse=True,
    )
