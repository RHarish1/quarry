"""Reusable resilience policies."""

from __future__ import annotations

import asyncio

from .circuit_breaker import CircuitBreaker
from .retry import RetryPolicy

# ============================================================================
# Retry Policies
# ============================================================================

DEFAULT_RETRY = RetryPolicy()

SEARCH_PROVIDER_RETRY = RetryPolicy(
    max_retries=3,
    base_delay=0.25,
    max_delay=2.0,
    backoff_multiplier=2.0,
    jitter=0.2,
    retry_exceptions=(
        TimeoutError,
        asyncio.TimeoutError,
        ConnectionError,
    ),
)

CRAWLER_RETRY = RetryPolicy(
    max_retries=2,
    base_delay=0.5,
    max_delay=4.0,
    backoff_multiplier=2.0,
    jitter=0.3,
    retry_exceptions=(
        TimeoutError,
        asyncio.TimeoutError,
        ConnectionError,
    ),
)

REDIS_RETRY = RetryPolicy(
    max_retries=2,
    base_delay=0.1,
    max_delay=1.0,
    backoff_multiplier=2.0,
    jitter=0.05,
    retry_exceptions=(
        TimeoutError,
        ConnectionError,
    ),
)

NO_RETRY = RetryPolicy(
    max_retries=0,
)


# ============================================================================
# Circuit Breakers
# ============================================================================

DEFAULT_BREAKER = CircuitBreaker(
    name="default",
)

FAST_PROVIDER_BREAKER = CircuitBreaker(
    name="fast-provider",
    failure_threshold=5,
    recovery_timeout=20,
)

SLOW_PROVIDER_BREAKER = CircuitBreaker(
    name="slow-provider",
    failure_threshold=3,
    recovery_timeout=60,
)

CRAWLER_BREAKER = CircuitBreaker(
    name="crawler",
    failure_threshold=4,
    recovery_timeout=30,
)

REDIS_BREAKER = CircuitBreaker(
    name="redis",
    failure_threshold=5,
    recovery_timeout=15,
)
