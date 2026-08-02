"""Exceptions used by the resilience layer."""

from __future__ import annotations


class ResilienceError(Exception):
    """Base exception for all resilience-related errors."""


# ============================================================================
# Retry
# ============================================================================


class RetryExhaustedError(ResilienceError):
    """Raised when all retry attempts have been exhausted."""


class TransientError(ResilienceError):
    """
    Temporary failure that is safe to retry.

    Examples
    --------
    - Network timeout
    - Connection reset
    - HTTP 503
    - Rate limiting
    """


class PermanentError(ResilienceError):
    """
    Non-retryable failure.

    Examples
    --------
    - HTTP 400
    - Authentication failure
    - Invalid request
    """


# ============================================================================
# Circuit Breaker
# ============================================================================


class CircuitOpenError(ResilienceError):
    """Raised when a circuit breaker rejects an operation."""


# ============================================================================
# Shutdown
# ============================================================================


class ShutdownInProgressError(ResilienceError):
    """Raised when the application is shutting down."""


class OperationCancelledError(ResilienceError):
    """Raised when an operation is cancelled during shutdown."""
