"""Token counting tests for Quarry."""

from utils.tokens import count_tokens


def test_count_tokens_is_deterministic() -> None:
    assert count_tokens("Hello, world!") == 4


def test_count_tokens_handles_empty_text() -> None:
    assert count_tokens("") == 0
