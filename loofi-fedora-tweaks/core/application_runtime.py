"""Process-owned lifecycle registry for the graphical application."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ShutdownCallback = Callable[[float], None]


@dataclass(frozen=True)
class ShutdownFailure:
    """One resource that could not be cleanly stopped."""

    resource_id: str
    error: str


class ApplicationRuntime:
    """Own teardown callbacks and run them once within one shared deadline."""

    def __init__(self, shutdown_timeout: float = 5.0) -> None:
        if shutdown_timeout < 0:
            raise ValueError("shutdown_timeout must be non-negative")
        self._shutdown_timeout = float(shutdown_timeout)
        self._lock = threading.RLock()
        self._resources: dict[str, ShutdownCallback] = {}
        self._shutdown_started = False
        self._shutdown_complete = False
        self._failures: tuple[ShutdownFailure, ...] = ()

    def register(self, resource_id: str, callback: ShutdownCallback) -> None:
        """Register one uniquely named callback while the runtime is active."""
        if not resource_id:
            raise ValueError("resource_id cannot be empty")
        if not callable(callback):
            raise TypeError("callback must be callable")
        with self._lock:
            if self._shutdown_started:
                raise RuntimeError("application runtime is shutting down")
            if resource_id in self._resources:
                raise ValueError(f"resource already registered: {resource_id}")
            self._resources[resource_id] = callback

    def unregister(self, resource_id: str) -> bool:
        """Remove a callback without running it."""
        with self._lock:
            return self._resources.pop(resource_id, None) is not None

    def resource_ids(self) -> tuple[str, ...]:
        """Return registered resource IDs in registration order."""
        with self._lock:
            return tuple(self._resources)

    @property
    def is_shutdown(self) -> bool:
        with self._lock:
            return self._shutdown_complete

    @property
    def failures(self) -> tuple[ShutdownFailure, ...]:
        with self._lock:
            return self._failures

    def shutdown(self, timeout: float | None = None) -> tuple[ShutdownFailure, ...]:
        """Stop resources in reverse registration order exactly once."""
        with self._lock:
            if self._shutdown_started:
                return self._failures
            self._shutdown_started = True
            resources = tuple(reversed(tuple(self._resources.items())))
            self._resources.clear()

        budget = self._shutdown_timeout if timeout is None else max(0.0, float(timeout))
        deadline = time.monotonic() + budget
        failures: list[ShutdownFailure] = []
        for resource_id, callback in resources:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                callback(remaining)
            except Exception as exc:
                logger.warning("Runtime cleanup failed for %s: %s", resource_id, exc)
                failures.append(ShutdownFailure(resource_id, str(exc)))

        with self._lock:
            self._failures = tuple(failures)
            self._shutdown_complete = True
            return self._failures
