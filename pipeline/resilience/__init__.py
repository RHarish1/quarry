"""Public API for the resilience layer."""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerMetrics,
    CircuitState,
)
from .exceptions import (
    CircuitOpenError,
    OperationCancelledError,
    PermanentError,
    ResilienceError,
    RetryExhaustedError,
    ShutdownInProgressError,
    TransientError,
)
from .policies import (
    CRAWLER_RETRY,
    DEFAULT_RETRY,
    FAST_PROVIDER_BREAKER,
    NO_RETRY,
    REDIS_RETRY,
    SEARCH_PROVIDER_RETRY,
    SLOW_PROVIDER_BREAKER,
)
from .retry import RetryExecutor, RetryPolicy, retry
from .shutdown import ShutdownManager

__all__ = [
    "CRAWLER_RETRY",
    "DEFAULT_RETRY",
    "FAST_PROVIDER_BREAKER",
    "NO_RETRY",
    "REDIS_RETRY",
    "SEARCH_PROVIDER_RETRY",
    "SLOW_PROVIDER_BREAKER",
    "CircuitBreaker",
    "CircuitBreakerMetrics",
    "CircuitOpenError",
    "CircuitState",
    "OperationCancelledError",
    "PermanentError",
    "ResilienceError",
    "RetryExecutor",
    "RetryExhaustedError",
    "RetryPolicy",
    "ShutdownInProgressError",
    "ShutdownManager",
    "TransientError",
    "retry",
]
