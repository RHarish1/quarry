"""Deterministic document compression for Quarry."""

from __future__ import annotations

import logging
from time import perf_counter

from models.clean_document import CleanDocument, CleanDocuments

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_BUDGET = 2048
CHARS_PER_TOKEN = 4


def compress_documents(
    documents: CleanDocuments,
    *,
    token_budget: int | None = None,
) -> tuple[CleanDocuments, float]:
    """Compress a collection of cleaned documents."""

    started = perf_counter()
    effective_token_budget = token_budget or DEFAULT_TOKEN_BUDGET

    compressed_documents = [
        _compress_document(document, effective_token_budget)
        for document in documents.documents
    ]

    latency_ms = (perf_counter() - started) * 1000.0

    logger.info(
        "Compressed %d documents in %.2f ms",
        len(compressed_documents),
        latency_ms,
    )

    return CleanDocuments(documents=compressed_documents), latency_ms


def _compress_document(
    document: CleanDocument,
    token_budget: int,
) -> CleanDocument:
    """Compress a single cleaned document."""

    text = document.cleaned_markdown

    paragraphs = _split_paragraphs(text)
    paragraphs = _remove_duplicate_paragraphs(paragraphs)
    paragraphs = _remove_low_information(paragraphs)

    compressed = _truncate_to_budget(
        paragraphs,
        token_budget,
    )

    compressed_tokens = _estimate_tokens(compressed)
    original_tokens = _estimate_tokens(text)

    return document.model_copy(
        update={
            "cleaned_markdown": compressed,
            "cleaned_token_count": compressed_tokens,
            "tokens_removed": max(
                0,
                original_tokens - compressed_tokens,
            ),
            "reduction_percentage": (
                (max(0, original_tokens - compressed_tokens) / original_tokens) * 100
                if original_tokens
                else 0.0
            ),
            "cleaning_steps_applied": (
                document.cleaning_steps_applied + ["deterministic_compression"]
            ),
        }
    )


def _split_paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]


def _remove_duplicate_paragraphs(
    paragraphs: list[str],
) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []

    for paragraph in paragraphs:
        key = paragraph.casefold()

        if key in seen:
            continue

        seen.add(key)
        output.append(paragraph)

    return output


def _remove_low_information(
    paragraphs: list[str],
) -> list[str]:
    output: list[str] = []

    for paragraph in paragraphs:
        lower = paragraph.lower()

        if "cookie" in lower:
            continue

        if "privacy policy" in lower:
            continue

        if "accept all" in lower:
            continue

        if "advertisement" in lower:
            continue

        if len(paragraph) < 30:
            continue

        output.append(paragraph)

    return output


def _truncate_to_budget(
    paragraphs: list[str],
    token_budget: int,
) -> str:
    output: list[str] = []

    tokens = 0

    for paragraph in paragraphs:
        estimate = _estimate_tokens(paragraph)

        if tokens + estimate > token_budget:
            break

        output.append(paragraph)
        tokens += estimate

    return "\n\n".join(output)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)
