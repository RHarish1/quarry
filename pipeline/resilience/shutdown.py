"""Application shutdown and lifecycle manager."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


CleanupCallback = Callable[[], Awaitable[None]]


class ShutdownManager:
    """
    Central application lifecycle manager.

    Responsibilities
    ----------------
    - Track cleanup callbacks
    - Track background tasks
    - Coordinate graceful shutdown
    """

    def __init__(self) -> None:
        self._cleanup_callbacks: list[CleanupCallback] = []
        self._tasks: set[asyncio.Task] = set()

        self._shutdown = False
        self._lock = asyncio.Lock()

    @property
    def is_shutting_down(self) -> bool:
        """Whether shutdown has started."""

        return self._shutdown

    def register_cleanup(
        self,
        callback: CleanupCallback,
    ) -> None:
        """Register an async cleanup callback."""

        self._cleanup_callbacks.append(callback)

    def register_task(
        self,
        task: asyncio.Task,
    ) -> asyncio.Task:
        """
        Register a background task.

        The task is automatically removed when finished.
        """

        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        return task

    async def shutdown(self) -> None:
        """Perform graceful application shutdown."""

        async with self._lock:
            if self._shutdown:
                return

            self._shutdown = True

            logger.info("Starting graceful shutdown...")

            await self._cancel_tasks()
            await self._run_cleanup()

            logger.info("Shutdown complete.")

    async def _cancel_tasks(self) -> None:
        """Cancel all registered background tasks."""

        if not self._tasks:
            return

        logger.info(
            "Cancelling %d background task(s)...",
            len(self._tasks),
        )

        for task in self._tasks:
            task.cancel()

        results = await asyncio.gather(
            *self._tasks,
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, asyncio.CancelledError):
                continue

            if isinstance(result, Exception):
                logger.exception(
                    "Background task exited with exception.",
                    exc_info=result,
                )

    async def _run_cleanup(self) -> None:
        """Run all registered cleanup callbacks."""

        logger.info(
            "Running %d cleanup callback(s)...",
            len(self._cleanup_callbacks),
        )

        for cleanup in reversed(self._cleanup_callbacks):
            try:
                await cleanup()

            except Exception:
                logger.exception("Cleanup callback failed.")
