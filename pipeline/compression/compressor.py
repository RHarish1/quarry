"""Deterministic document compression for Quarry."""

from __future__ import annotations

import logging
import re
from time import perf_counter

from models.clean_document import CleanDocument, CleanDocuments
from utils.tokens import count_tokens

logger = logging.getLogger(__name__)


LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")
IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\([^)]+\)")

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

    # 1. Prune high-density link blocks (hidden nav menus)
    paragraphs = _remove_low_information(paragraphs)

    # 2. Minify remaining markdown (strip URLs, keep text)
    paragraphs = _minify_markdown(paragraphs)

    compressed = _truncate_to_budget(
        paragraphs,
        token_budget,
    )

    compressed_tokens = count_tokens(compressed)
    original_tokens = count_tokens(text)

    return document.model_copy(
        update={
            "cleaned_markdown": compressed,
            "cleaned_token_count": compressed_tokens,
            "tokens_removed": max(0, original_tokens - compressed_tokens),
            "reduction_percentage": (
                (max(0, original_tokens - compressed_tokens) / original_tokens) * 100
                if original_tokens
                else 0.0
            ),
            "cleaning_steps_applied": (
                document.cleaning_steps_applied
                + ["deterministic_compression", "markdown_minification"]
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


def _remove_low_information(paragraphs: list[str]) -> list[str]:
    """Remove hidden nav menus and uselessly short paragraphs."""
    output: list[str] = []

    for paragraph in paragraphs:
        # Skip very short paragraphs unless they are list items or headings
        if len(paragraph) < 30 and not paragraph.startswith(("#", "-", "*")):
            continue

        # Heuristic: If a paragraph is more than 40% hyperlink text,
        # it is almost certainly a navigation menu or tag cloud. Drop it.
        link_chars = sum(len(m.group(0)) for m in LINK_PATTERN.finditer(paragraph))
        if len(paragraph) > 0 and (link_chars / len(paragraph)) > 0.4:
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
        estimate = count_tokens(paragraph)

        if tokens + estimate > token_budget:
            break

        output.append(paragraph)
        tokens += estimate

    return "\n\n".join(output)


def _estimate_tokens(text: str) -> int:
    """Estimate tokens using the shared regex tokenizer."""
    return max(1, count_tokens(text))


def _minify_markdown(paragraphs: list[str]) -> list[str]:
    """Flatten images to alt-text and links to standard text to save massive tokens."""
    output = []
    for p in paragraphs:
        # ![Alt Text](https://long-url.com/img.png) -> Alt Text
        p = IMAGE_PATTERN.sub(r"\1", p)
        # [Click Here](https://long-url.com/a/b/c) -> Click Here
        p = LINK_PATTERN.sub(r"\1", p)
        output.append(p)
    return output
