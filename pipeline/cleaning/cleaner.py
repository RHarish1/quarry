"""Deterministic cleaning stage for Quarry."""

from __future__ import annotations

from time import perf_counter

from models.clean_document import CleanDocument, CleanDocuments, CleanRequest
from utils.tokens import count_tokens

from pipeline.cleaning.steps import (
    normalize_markdown,
    remove_advertisement_sections,
    remove_cookie_banner_sections,
    remove_duplicate_headings,
    remove_duplicate_paragraphs,
    remove_empty_sections,
    remove_footer_sections,
    remove_navigation_sections,
    remove_repeated_whitespace,
)


def _apply_cleaning_steps(markdown: str, cleaning_level: int) -> tuple[str, list[str]]:
    """Apply deterministic cleaning steps in sequence."""

    cleaned = normalize_markdown(markdown)
    steps_applied = ["normalize_markdown"]

    if cleaning_level >= 0:
        cleaned = remove_repeated_whitespace(cleaned)
        steps_applied.append("remove_repeated_whitespace")

    if cleaning_level >= 1:
        cleaned = remove_cookie_banner_sections(cleaned)
        cleaned = remove_duplicate_paragraphs(cleaned)
        steps_applied.extend(["remove_cookie_banner_sections", "remove_duplicate_paragraphs"])

    if cleaning_level >= 2:
        cleaned = remove_navigation_sections(cleaned)
        cleaned = remove_footer_sections(cleaned)
        cleaned = remove_advertisement_sections(cleaned)
        cleaned = remove_duplicate_headings(cleaned)
        steps_applied.extend(
            [
                "remove_navigation_sections",
                "remove_footer_sections",
                "remove_advertisement_sections",
                "remove_duplicate_headings",
            ]
        )

    if cleaning_level >= 3:
        cleaned = remove_empty_sections(cleaned)
        steps_applied.append("remove_empty_sections")

    cleaned = remove_repeated_whitespace(cleaned)
    if steps_applied[-1] != "remove_repeated_whitespace":
        steps_applied.append("remove_repeated_whitespace")

    return cleaned.strip(), steps_applied


def clean_documents(clean_request: CleanRequest) -> CleanDocuments:
    """Clean raw documents without mutating the originals."""

    cleaned_documents: list[CleanDocument] = []
    for document in clean_request.documents.documents:
        cleaning_started = perf_counter()
        try:
            cleaned_markdown, steps_applied = _apply_cleaning_steps(
                document.markdown,
                clean_request.cleaning_level,
            )
        except Exception:
            cleaned_markdown = document.markdown
            steps_applied = ["cleaning_failed"]

        original_token_count = count_tokens(document.markdown)
        cleaned_token_count = count_tokens(cleaned_markdown)
        tokens_removed = max(original_token_count - cleaned_token_count, 0)
        reduction_percentage = (
            (tokens_removed / original_token_count) * 100.0 if original_token_count else 0.0
        )

        cleaned_documents.append(
            CleanDocument(
                **document.model_dump(),
                cleaned_markdown=cleaned_markdown,
                original_token_count=original_token_count,
                cleaned_token_count=cleaned_token_count,
                tokens_removed=tokens_removed,
                reduction_percentage=reduction_percentage,
                cleaning_latency_ms=(perf_counter() - cleaning_started) * 1000.0,
                cleaning_steps_applied=steps_applied,
            )
        )

    return CleanDocuments(documents=cleaned_documents)
