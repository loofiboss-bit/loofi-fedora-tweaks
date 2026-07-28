"""Process-owned lifecycle registry for the graphical application."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

RequestStop = Callable[[], None]
WaitForStop = Callable[[float], bool]


@dataclass(frozen=True)
class ShutdownResource:
    """Two-phase shutdown hooks for one process-owned resource."""

    request_stop: RequestStop
    wait_for_stop: WaitForStop


@dataclass(frozen=True)
class ShutdownFailure:
    """One resource that could not be cleanly stopped."""

    resource_id: str
    error: str


class ApplicationRuntime:
    """Request teardown once, then wait within one shared deadline."""

    def __init__(self, shutdown_timeout: float = 5.0) -> None:
        if shutdown_timeout < 0:
            raise ValueError("shutdown_timeout must be non-negative")
        self._shutdown_timeout = float(shutdown_timeout)
        self._lock = threading.RLock()
        self._resources: dict[str, ShutdownResource] = {}
        self._shutdown_started = False
        self._shutdown_complete = False
        self._failures: tuple[ShutdownFailure, ...] = ()

    def register(self, resource_id: str, resource: ShutdownResource) -> None:
        """Register one uniquely named two-phase resource while active."""
        if not resource_id:
            raise ValueError("resource_id cannot be empty")
        if not isinstance(resource, ShutdownResource):
            raise TypeError("resource must be a ShutdownResource")
        if not callable(resource.request_stop) or not callable(resource.wait_for_stop):
            raise TypeError("shutdown resource hooks must be callable")
        with self._lock:
            if self._shutdown_started:
                raise RuntimeError("application runtime is shutting down")
            if resource_id in self._resources:
                raise ValueError(f"resource already registered: {resource_id}")
            self._resources[resource_id] = resource

    def unregister(self, resource_id: str) -> bool:
        """Remove a resource without stopping it."""
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
        """Request every stop, then wait in LIFO order against one deadline."""
        with self._lock:
            if self._shutdown_started:
                return self._failures
            self._shutdown_started = True
            resources = tuple(reversed(tuple(self._resources.items())))
            self._resources.clear()

        budget = self._shutdown_timeout if timeout is None else max(0.0, float(timeout))
        started_at = time.monotonic()
        deadline = started_at + budget
        # Stop requests are required to be immediate. Cap their collection at
        # half of the shared budget so one broken request cannot consume the
        # time needed to wait for resources that accepted their stop signal.
        request_deadline = started_at + (budget / 2.0)
        failure_by_resource = self._request_all_bounded(resources, request_deadline)

        for resource_id, resource in resources:
            if resource_id in failure_by_resource:
                continue
            error = self._invoke_bounded(resource.wait_for_stop, deadline)
            if error is not None:
                logger.warning("Runtime shutdown wait failed for %s: %s", resource_id, error)
                failure_by_resource[resource_id] = ShutdownFailure(resource_id, error)

        failures = tuple(
            failure_by_resource[resource_id]
            for resource_id, _resource in resources
            if resource_id in failure_by_resource
        )

        with self._lock:
            self._failures = failures
            self._shutdown_complete = True
            return self._failures

    @staticmethod
    def _request_all_bounded(
        resources: tuple[tuple[str, ShutdownResource], ...],
        deadline: float,
    ) -> dict[str, ShutdownFailure]:
        """Start every stop request before collecting results by the deadline."""
        outcomes: dict[str, dict[str, Any]] = {}
        finished: dict[str, threading.Event] = {}

        def invoke(
            resource_id: str,
            request_stop: RequestStop,
            predecessor_entered: threading.Event | None,
            entered: threading.Event,
        ) -> None:
            if predecessor_entered is not None:
                predecessor_entered.wait()
            entered.set()
            try:
                request_stop()
            except Exception as exc:
                outcomes[resource_id]["error"] = exc
            finally:
                outcomes[resource_id]["finished_at"] = time.monotonic()
                finished[resource_id].set()

        predecessor_entered: threading.Event | None = None
        for resource_id, resource in resources:
            outcomes[resource_id] = {}
            finished[resource_id] = threading.Event()
            entered = threading.Event()
            requester = threading.Thread(
                target=invoke,
                args=(resource_id, resource.request_stop, predecessor_entered, entered),
                name=f"ApplicationRuntimeRequest-{resource_id}",
                daemon=True,
            )
            requester.start()
            predecessor_entered = entered

        failures: dict[str, ShutdownFailure] = {}
        for resource_id, _resource in resources:
            remaining = max(0.0, deadline - time.monotonic())
            finished[resource_id].wait(remaining)
            finished_at = outcomes[resource_id].get("finished_at")
            if finished_at is None or finished_at > deadline:
                error = "stop request exceeded bounded request phase"
            else:
                exception = outcomes[resource_id].get("error")
                error = str(exception) if exception is not None else ""
            if error:
                logger.warning("Runtime stop request failed for %s: %s", resource_id, error)
                failures[resource_id] = ShutdownFailure(resource_id, error)
        return failures

    @staticmethod
    def _invoke_bounded(wait_for_stop: WaitForStop, deadline: float) -> str | None:
        """Run a resource wait without allowing it to overrun the deadline."""
        timeout = max(0.0, deadline - time.monotonic())
        if timeout <= 0:
            return "shutdown deadline expired"

        finished = threading.Event()
        outcome: dict[str, Any] = {}

        def invoke() -> None:
            try:
                outcome["stopped"] = wait_for_stop(timeout)
            except Exception as exc:
                outcome["error"] = exc
            finally:
                outcome["finished_at"] = time.monotonic()
                finished.set()

        waiter = threading.Thread(
            target=invoke,
            name="ApplicationRuntimeWait",
            daemon=True,
        )
        waiter.start()
        if not finished.wait(max(0.0, deadline - time.monotonic())):
            return "shutdown deadline expired"
        finished_at = outcome.get("finished_at")
        if finished_at is not None and finished_at > deadline:
            return "shutdown deadline expired"
        error = outcome.get("error")
        if error is not None:
            return str(error)
        if outcome.get("stopped") is not True:
            return "resource did not stop before the deadline"
        return None
