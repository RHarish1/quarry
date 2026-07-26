"""Token counting helpers for Quarry."""

from __future__ import annotations

import re

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def count_tokens(text: str) -> int:
    """Count deterministic text tokens using a lightweight regex tokenizer."""

    if not text:
        return 0

    return len(TOKEN_PATTERN.findall(text))
