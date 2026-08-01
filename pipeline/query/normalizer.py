"""Deterministic query normalization for Quarry.

This module performs lightweight preprocessing to improve search quality
without using an LLM.

Pipeline:
Raw Query
    ↓
Unicode normalization
    ↓
Whitespace cleanup
    ↓
Quote normalization
    ↓
Case normalization
    ↓
Punctuation cleanup
    ↓
Duplicate token removal
    ↓
Final normalized query
"""

from __future__ import annotations

import re
import unicodedata

from models.search import SearchRequest

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s\-\"']")
_DUPLICATE_SPACE_RE = re.compile(r"\s{2,}")


def _normalize_unicode(text: str) -> str:
    """Normalize unicode characters."""
    return unicodedata.normalize("NFKC", text)


def _normalize_quotes(text: str) -> str:
    """Convert smart quotes to standard quotes."""
    return text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")


def _normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _remove_unnecessary_punctuation(text: str) -> str:
    """Remove punctuation that rarely helps search."""
    return _PUNCT_RE.sub(" ", text)


def _deduplicate_tokens(text: str) -> str:
    """Remove repeated consecutive tokens.

    Example:
        python python async crawler
        ->
        python async crawler
    """
    output: list[str] = []

    previous = None
    for token in text.split():
        if token != previous:
            output.append(token)
        previous = token

    return " ".join(output)


def normalize_query(request: SearchRequest) -> SearchRequest:
    query = request.query
    """Normalize a search query.

    Examples
    --------
    >>> normalize_query("  What   is   HTTP??? ")
    'what is http'

    >>> normalize_query("Python Python asyncio")
    'python asyncio'
    """
    query = _normalize_unicode(query)
    query = _normalize_quotes(query)

    query = query.lower()

    query = _remove_unnecessary_punctuation(query)

    query = _normalize_whitespace(query)

    query = _deduplicate_tokens(query)

    query = _DUPLICATE_SPACE_RE.sub(" ", query).strip()

    return request.model_copy(update={"query": query})
