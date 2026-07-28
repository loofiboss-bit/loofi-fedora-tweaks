"""Tests for the process-owned application runtime."""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock

from core.application_runtime import ApplicationRuntime, ShutdownResource


class TestApplicationRuntime(unittest.TestCase):
    def test_shutdown_is_lifo_and_idempotent(self) -> None:
        calls: list[tuple[str, float]] = []
        runtime = ApplicationRuntime(shutdown_timeout=1.0)

        def record_wait(name: str, remaining: float) -> bool:
            calls.append((name, remaining))
            return True

        runtime.register(
            "event-bus",
            ShutdownResource(
                request_stop=lambda: calls.append(("request:event-bus", 0.0)),
                wait_for_stop=lambda remaining: record_wait("wait:event-bus", remaining),
            ),
        )
        runtime.register(
            "window",
            ShutdownResource(
                request_stop=lambda: calls.append(("request:window", 0.0)),
                wait_for_stop=lambda remaining: record_wait("wait:window", remaining),
            ),
        )

        self.assertEqual(runtime.resource_ids(), ("event-bus", "window"))
        self.assertEqual(runtime.shutdown(), ())
        self.assertEqual(runtime.shutdown(), ())
        self.assertEqual(
            [name for name, _remaining in calls],
            ["request:window", "request:event-bus", "wait:window", "wait:event-bus"],
        )
        self.assertTrue(runtime.is_shutdown)

    def test_unregister_prevents_cleanup(self) -> None:
        callback = MagicMock()
        runtime = ApplicationRuntime()
        runtime.register("optional", ShutdownResource(callback, MagicMock(return_value=True)))

        self.assertTrue(runtime.unregister("optional"))
        self.assertFalse(runtime.unregister("optional"))
        runtime.shutdown()
        callback.assert_not_called()

    def test_shutdown_records_failure_and_continues(self) -> None:
        completed = MagicMock()
        runtime = ApplicationRuntime()
        runtime.register("completed", ShutdownResource(completed, MagicMock(return_value=True)))
        runtime.register(
            "broken",
            ShutdownResource(MagicMock(side_effect=RuntimeError("boom")), MagicMock(return_value=True)),
        )

        failures = runtime.shutdown()

        self.assertEqual(tuple(failure.resource_id for failure in failures), ("broken",))
        completed.assert_called_once()

    def test_wait_failure_is_recorded_and_later_waits_continue(self) -> None:
        completed_wait = MagicMock(return_value=True)
        runtime = ApplicationRuntime()
        runtime.register("completed", ShutdownResource(lambda: None, completed_wait))
        runtime.register(
            "broken",
            ShutdownResource(
                lambda: None,
                MagicMock(side_effect=RuntimeError("wait failed")),
            ),
        )

        failures = runtime.shutdown()

        self.assertEqual(tuple(failure.resource_id for failure in failures), ("broken",))
        self.assertEqual(failures[0].error, "wait failed")
        completed_wait.assert_called_once()

    def test_registration_is_closed_after_shutdown_starts(self) -> None:
        runtime = ApplicationRuntime()
        runtime.shutdown()

        with self.assertRaises(RuntimeError):
            runtime.register("late", ShutdownResource(lambda: None, lambda _remaining: True))

    def test_rejects_invalid_registration(self) -> None:
        runtime = ApplicationRuntime()
        with self.assertRaises(ValueError):
            runtime.register("", ShutdownResource(lambda: None, lambda _remaining: True))
        with self.assertRaises(TypeError):
            runtime.register("invalid", None)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            runtime.register(
                "invalid-hooks",
                ShutdownResource(None, lambda _remaining: True),  # type: ignore[arg-type]
            )
        runtime.register("duplicate", ShutdownResource(lambda: None, lambda _remaining: True))
        with self.assertRaises(ValueError):
            runtime.register("duplicate", ShutdownResource(lambda: None, lambda _remaining: True))

    def test_blocking_wait_cannot_overrun_shared_deadline(self) -> None:
        release = threading.Event()
        runtime = ApplicationRuntime(shutdown_timeout=0.02)
        runtime.register(
            "blocked",
            ShutdownResource(lambda: None, lambda _remaining: release.wait(1.0)),
        )

        started = time.monotonic()
        failures = runtime.shutdown()
        elapsed = time.monotonic() - started
        release.set()

        self.assertLess(elapsed, 0.2)
        self.assertEqual(tuple(failure.resource_id for failure in failures), ("blocked",))
        self.assertIn("deadline", failures[0].error)

    def test_blocking_request_does_not_prevent_later_stop_or_overrun(self) -> None:
        release = threading.Event()
        later_requested = threading.Event()
        runtime = ApplicationRuntime(shutdown_timeout=0.2)

        def blocking_request() -> None:
            release.wait(1.0)

        runtime.register(
            "later",
            ShutdownResource(later_requested.set, lambda _remaining: True),
        )
        runtime.register(
            "blocked",
            ShutdownResource(blocking_request, lambda _remaining: True),
        )

        started = time.monotonic()
        failures = runtime.shutdown()
        elapsed = time.monotonic() - started
        release.set()

        self.assertTrue(later_requested.is_set())
        self.assertLess(elapsed, 0.4)
        self.assertEqual(tuple(failure.resource_id for failure in failures), ("blocked",))
        self.assertIn("stop request", failures[0].error)

    def test_every_stop_is_requested_before_slow_wait(self) -> None:
        calls: list[str] = []
        runtime = ApplicationRuntime(shutdown_timeout=0.1)

        def record_wait(name: str) -> bool:
            calls.append(name)
            return True

        runtime.register(
            "first",
            ShutdownResource(
                lambda: calls.append("request:first"),
                lambda _remaining: record_wait("wait:first"),
            ),
        )
        runtime.register(
            "second",
            ShutdownResource(
                lambda: calls.append("request:second"),
                lambda _remaining: record_wait("wait:second"),
            ),
        )

        self.assertEqual(runtime.shutdown(), ())
        self.assertEqual(
            calls,
            ["request:second", "request:first", "wait:second", "wait:first"],
        )


if __name__ == "__main__":
    unittest.main()
