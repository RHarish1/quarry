"""Generic async circuit breaker."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when the circuit is open."""


@dataclass(slots=True)
class CircuitBreakerMetrics:
    """Runtime metrics."""

    opened_count: int = 0
    success_count: int = 0
    failure_count: int = 0


class CircuitBreaker:
    """
    Generic async circuit breaker.

    Create one instance per dependency.

    Examples
    --------
    searxng_breaker
    crawler_breaker
    redis_breaker
    brave_breaker
    """

    def __init__(
        self,
        *,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.failure_count = 0
        self.last_failure_time = 0.0

        self.state = CircuitState.CLOSED

        self.metrics = CircuitBreakerMetrics()

        # Ensures only one HALF_OPEN request.
        self._half_open_lock = asyncio.Lock()

    async def execute(
        self,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Execute an operation through the circuit breaker."""

        if self.state is CircuitState.OPEN:
            if not self._recovery_timeout_elapsed():
                raise CircuitOpenError(f"Circuit '{self.name}' is OPEN.")

            if self._half_open_lock.locked():
                raise CircuitOpenError(f"Circuit '{self.name}' is HALF_OPEN.")

            self.state = CircuitState.HALF_OPEN

        if self.state is CircuitState.HALF_OPEN:
            return await self._execute_half_open(operation)

        return await self._execute_closed(operation)

    async def _execute_closed(
        self,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Execute while circuit is closed."""

        try:
            result = await operation()

        except Exception:
            self._record_failure()
            raise

        self._record_success()
        return result

    async def _execute_half_open(
        self,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Allow exactly one probe request."""

        if self._half_open_lock.locked():
            raise CircuitOpenError(f"Circuit '{self.name}' is HALF_OPEN.")

        async with self._half_open_lock:
            try:
                result = await operation()

            except Exception:
                self._trip_open()
                raise

            self._reset()
            return result

    def _record_success(self) -> None:
        """Record a successful request."""

        self.metrics.success_count += 1
        self.failure_count = 0

    def _record_failure(self) -> None:
        """Record a failed request."""

        self.metrics.failure_count += 1

        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        logger.warning(
            "Circuit '%s' failure (%d/%d)",
            self.name,
            self.failure_count,
            self.failure_threshold,
        )

        if self.failure_count >= self.failure_threshold:
            self._trip_open()

    def _trip_open(self) -> None:
        """Transition to OPEN."""

        self.state = CircuitState.OPEN
        self.last_failure_time = time.monotonic()

        self.metrics.opened_count += 1

        logger.error("Circuit '%s' OPENED", self.name)

    def _reset(self) -> None:
        """Transition to CLOSED."""

        self.state = CircuitState.CLOSED
        self.failure_count = 0

        logger.info("Circuit '%s' CLOSED", self.name)

    def _recovery_timeout_elapsed(self) -> bool:
        """Check whether recovery timeout has expired."""

        return (time.monotonic() - self.last_failure_time) >= self.recovery_timeout

    @property
    def current_state(self) -> str:
        """Expose current state for metrics."""

        return self.state.value
