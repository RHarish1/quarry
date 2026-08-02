"""Reusable async retry mechanism with exponential backoff."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class RetryPolicy:
    """Configuration for retry execution."""

    max_retries: int = 3

    base_delay: float = 0.5
    max_delay: float = 8.0
    backoff_multiplier: float = 2.0

    jitter: float = 0.25

    retry_status_codes: set[int] = field(
        default_factory=lambda: {
            408,
            429,
            500,
            502,
            503,
            504,
        }
    )

    retry_exceptions: tuple[type[Exception], ...] = (
        TimeoutError,
        asyncio.TimeoutError,
        ConnectionError,
    )


class RetryExecutor:
    """Executes async operations using exponential backoff."""

    def __init__(self, policy: RetryPolicy) -> None:
        self.policy = policy

    async def execute(
        self,
        operation: Callable[[], Awaitable[Any]],
        *,
        provider: str = "unknown",
    ) -> Any:
        """
        Execute an async operation with retries.

        Parameters
        ----------
        operation:
            Async callable returning the desired result.

        provider:
            Human-readable provider name for logging.
        """

        attempts = self.policy.max_retries + 1

        for attempt in range(attempts):
            try:
                return await operation()

            except Exception as exc:
                is_last_attempt = attempt == self.policy.max_retries

                if (
                    is_last_attempt
                    or not self.should_retry_exception(exc)
                    or not self.should_retry_status_code(exc)
                ):
                    raise

                delay = self.calculate_backoff(attempt)

                logger.warning(
                    "Retry %d/%d | Provider=%s | Delay=%.0fms | Reason=%s",
                    attempt + 1,
                    attempts,
                    provider,
                    delay * 1000,
                    exc.__class__.__name__,
                )

                await asyncio.sleep(delay)

        raise RuntimeError("Retry executor exited unexpectedly.")

    def calculate_backoff(self, attempt: int) -> float:
        """Compute exponential backoff with jitter."""

        delay = self.policy.base_delay * (self.policy.backoff_multiplier**attempt)

        delay = min(delay, self.policy.max_delay)

        if self.policy.jitter > 0:
            delay += random.uniform(0, self.policy.jitter)

        return delay

    def should_retry_exception(self, exc: Exception) -> bool:
        """Return True if this exception type is retryable."""

        return isinstance(exc, self.policy.retry_exceptions)

    def should_retry_status_code(self, exc: Exception) -> bool:
        """
        Return True if the exception's status code is retryable.

        Works with libraries exposing `.status_code`
        (HTTPX, requests wrappers, etc.).
        """

        status_code = getattr(exc, "status_code", None)

        if status_code is None:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)

        if status_code is None:
            return True

        return status_code in self.policy.retry_status_codes


_DEFAULT_EXECUTOR = RetryExecutor(RetryPolicy())


async def retry(
    operation: Callable[[], Awaitable[Any]],
    *,
    provider: str = "unknown",
    policy: RetryPolicy | None = None,
) -> Any:
    """
    Convenience wrapper.

    Example
    -------
    result = await retry(
        lambda: provider.search(request),
        provider="SearXNG",
    )
    """

    executor = _DEFAULT_EXECUTOR if policy is None else RetryExecutor(policy)
    return await executor.execute(operation, provider=provider)
