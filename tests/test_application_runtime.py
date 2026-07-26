"""Tests for the process-owned application runtime."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from core.application_runtime import ApplicationRuntime


class TestApplicationRuntime(unittest.TestCase):
    def test_shutdown_is_lifo_and_idempotent(self) -> None:
        calls: list[tuple[str, float]] = []
        runtime = ApplicationRuntime(shutdown_timeout=1.0)
        runtime.register("event-bus", lambda remaining: calls.append(("event-bus", remaining)))
        runtime.register("window", lambda remaining: calls.append(("window", remaining)))

        self.assertEqual(runtime.resource_ids(), ("event-bus", "window"))
        self.assertEqual(runtime.shutdown(), ())
        self.assertEqual(runtime.shutdown(), ())
        self.assertEqual([name for name, _remaining in calls], ["window", "event-bus"])
        self.assertTrue(runtime.is_shutdown)

    def test_unregister_prevents_cleanup(self) -> None:
        callback = MagicMock()
        runtime = ApplicationRuntime()
        runtime.register("optional", callback)

        self.assertTrue(runtime.unregister("optional"))
        self.assertFalse(runtime.unregister("optional"))
        runtime.shutdown()
        callback.assert_not_called()

    def test_shutdown_records_failure_and_continues(self) -> None:
        completed = MagicMock()
        runtime = ApplicationRuntime()
        runtime.register("completed", completed)
        runtime.register("broken", MagicMock(side_effect=RuntimeError("boom")))

        failures = runtime.shutdown()

        self.assertEqual(tuple(failure.resource_id for failure in failures), ("broken",))
        completed.assert_called_once()

    def test_registration_is_closed_after_shutdown_starts(self) -> None:
        runtime = ApplicationRuntime()
        runtime.shutdown()

        with self.assertRaises(RuntimeError):
            runtime.register("late", lambda _remaining: None)

    def test_rejects_invalid_registration(self) -> None:
        runtime = ApplicationRuntime()
        with self.assertRaises(ValueError):
            runtime.register("", lambda _remaining: None)
        with self.assertRaises(TypeError):
            runtime.register("invalid", None)  # type: ignore[arg-type]
        runtime.register("duplicate", lambda _remaining: None)
        with self.assertRaises(ValueError):
            runtime.register("duplicate", lambda _remaining: None)


if __name__ == "__main__":
    unittest.main()
