"""Compass session state, cancellation, and timeout matrix."""

from __future__ import annotations

import unittest

from core.troubleshooting.lifecycle import (
    CancellationSignal,
    finalize_session,
    new_session,
    start_session,
)
from core.troubleshooting.models import SourceResult
from core.troubleshooting.profiles import require_profile


class TestTroubleshootingLifecycle(unittest.TestCase):
    SESSION_ID = "12345678-1234-5678-9234-567812345678"

    def _running(self):
        return start_session(
            new_session(
                "network_problem",
                "traditional",
                started_at=1.0,
                session_id=self.SESSION_ID,
            ),
            started_at=2.0,
        )

    def _completed(self, source_id: str) -> SourceResult:
        budget = require_profile("network_problem").budget_for(
            source_id,
            "traditional",
        )
        self.assertIsNotNone(budget)
        return SourceResult.completed(
            source_id,
            started_at=2.0,
            completed_at=3.0,
            timeout_seconds=budget.timeout_seconds,
            facts={"status": "available"},
        )

    def _failed(self, source_id: str) -> SourceResult:
        budget = require_profile("network_problem").budget_for(
            source_id,
            "traditional",
        )
        self.assertIsNotNone(budget)
        return SourceResult(
            source_id,
            "failed",
            2.0,
            3.0,
            budget.timeout_seconds,
            reason_code="collector-failed",
            message="The bounded collector failed.",
        )

    def test_success_requires_every_variant_applicable_source(self):
        result = finalize_session(
            self._running(),
            completed_at=4.0,
            source_results=(
                self._completed("network-state"),
                self._completed("dns-state"),
                self._completed("change-journal"),
            ),
        )

        self.assertEqual(result.state, "completed")
        self.assertEqual(len(result.completed_sources), 3)

    def test_partial_preserves_unavailable_and_failed_sources(self):
        result = finalize_session(
            self._running(),
            completed_at=4.0,
            source_results=(
                self._completed("network-state"),
                SourceResult.unavailable(
                    "dns-state",
                    at=3.0,
                    timeout_seconds=5.0,
                    reason_code="networkmanager-unavailable",
                    message="NetworkManager state is unavailable.",
                ),
                self._failed("change-journal"),
            ),
        )

        self.assertEqual(result.state, "partial")
        self.assertEqual(result.unavailable_sources, ("dns-state",))
        self.assertEqual(result.failed_sources, ("change-journal",))

    def test_missing_sources_become_explicitly_unavailable(self):
        result = finalize_session(
            self._running(),
            completed_at=4.0,
            source_results=(),
        )

        self.assertEqual(result.state, "partial")
        self.assertEqual(
            result.unavailable_sources,
            ("change-journal", "dns-state", "network-state"),
        )

    def test_timeout_is_bounded_and_never_becomes_all_clear(self):
        timed_out = SourceResult(
            "network-state",
            "timed_out",
            2.0,
            7.0,
            5.0,
            reason_code="source-timeout",
            message="Network state collection reached its timeout.",
        )
        result = finalize_session(
            self._running(),
            completed_at=7.0,
            source_results=(timed_out, self._completed("dns-state")),
        )

        self.assertEqual(result.state, "partial")
        self.assertEqual(result.timed_out_sources, ("network-state",))

    def test_all_collector_failures_produce_failed_session(self):
        result = finalize_session(
            self._running(),
            completed_at=4.0,
            source_results=(
                self._failed("network-state"),
                self._failed("dns-state"),
                self._failed("change-journal"),
            ),
        )

        self.assertEqual(result.state, "failed")

    def test_cancellation_signal_and_session_cancellation_are_cooperative(self):
        signal = CancellationSignal()
        self.assertFalse(signal.is_cancelled())
        signal.cancel()
        self.assertTrue(signal.is_cancelled())
        self.assertTrue(signal.wait(0.0))

        result = finalize_session(
            self._running(),
            completed_at=4.0,
            source_results=(self._completed("network-state"),),
            cancellation_requested=signal.is_cancelled(),
        )

        self.assertEqual(result.state, "cancelled")
        self.assertEqual(
            tuple(
                item.source_id
                for item in result.source_results
                if item.state == "cancelled"
            ),
            ("change-journal", "dns-state"),
        )

    def test_malformed_transition_and_unknown_source_fail_closed(self):
        queued = new_session(
            "network_problem",
            "traditional",
            started_at=1.0,
            session_id=self.SESSION_ID,
        )
        with self.assertRaisesRegex(ValueError, "running"):
            finalize_session(
                queued,
                completed_at=2.0,
                source_results=(),
            )
        unknown = SourceResult.completed(
            "network-scan",
            started_at=2.0,
            completed_at=3.0,
            timeout_seconds=5.0,
            facts={},
        )
        with self.assertRaisesRegex(ValueError, "outside"):
            finalize_session(
                self._running(),
                completed_at=4.0,
                source_results=(unknown,),
            )


if __name__ == "__main__":
    unittest.main()
