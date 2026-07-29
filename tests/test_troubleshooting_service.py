"""Explicit Compass runtime orchestration tests."""

from __future__ import annotations

import unittest

from core.troubleshooting.adapters import adapt_structured_source
from core.troubleshooting.lifecycle import CancellationSignal
from core.troubleshooting.service import TroubleshootingService
from core.troubleshooting.storage import SessionStoreSnapshot


class _Store:
    def __init__(self, sessions=(), *, reason_code="", save_error=None):
        self.sessions = tuple(sessions)
        self.reason_code = reason_code
        self.save_error = save_error
        self.saved = []
        self.read_calls = 0

    def read(self):
        self.read_calls += 1
        return SessionStoreSnapshot(
            self.sessions,
            1,
            not bool(self.reason_code),
            self.reason_code,
        )

    def save(self, session):
        if self.save_error:
            raise self.save_error
        self.saved.append(session)


class _Collector:
    def __init__(self, *, cancel_after_first=False):
        self.calls = []
        self.cancel_after_first = cancel_after_first

    def collect(
        self,
        source_id,
        session,
        *,
        started_at,
        cancellation,
    ):
        self.calls.append(source_id)
        if self.cancel_after_first:
            cancellation.cancel()
            state = "cancelled"
            reason_code = "session-cancelled"
            message = "Cancelled by the test."
        else:
            state = "empty"
            reason_code = ""
            message = ""
        return adapt_structured_source(
            profile_id=session.profile_id,
            variant=session.variant,
            source_id=source_id,
            state=state,
            started_at=started_at,
            completed_at=started_at,
            reason_code=reason_code,
            message=message,
        )


class TestTroubleshootingService(unittest.TestCase):
    def test_construction_does_not_collect_read_or_write(self):
        collector = _Collector()
        store = _Store()

        TroubleshootingService(
            collector=collector,
            store=store,
            variant_resolver=lambda: "traditional",
        )

        self.assertEqual(collector.calls, [])
        self.assertEqual(store.read_calls, 0)
        self.assertEqual(store.saved, [])

    def test_explicit_run_uses_exact_profile_sources_and_persists_terminal_result(self):
        collector = _Collector()
        store = _Store()
        progress = []
        service = TroubleshootingService(
            collector=collector,
            store=store,
            variant_resolver=lambda: "traditional",
        )

        outcome = service.run(
            "network_problem",
            progress_callback=progress.append,
        )

        self.assertEqual(
            collector.calls,
            ["network-state", "dns-state", "change-journal"],
        )
        self.assertEqual(outcome.session.state, "completed")
        self.assertEqual(len(store.saved), 1)
        self.assertEqual(
            tuple(result.source_id for result in outcome.session.source_results),
            ("change-journal", "dns-state", "network-state"),
        )
        self.assertEqual(progress[-1].percentage, 100)

    def test_cancellation_marks_unfinished_sources_and_keeps_terminal_history(self):
        collector = _Collector(cancel_after_first=True)
        store = _Store()
        service = TroubleshootingService(
            collector=collector,
            store=store,
            variant_resolver=lambda: "traditional",
        )

        outcome = service.run(
            "network_problem",
            cancellation=CancellationSignal(),
        )

        self.assertEqual(collector.calls, ["network-state"])
        self.assertEqual(outcome.session.state, "cancelled")
        self.assertEqual(
            outcome.session.cancelled_sources,
            ("change-journal", "dns-state", "network-state"),
        )
        self.assertEqual(store.saved, [outcome.session])

    def test_previous_compatible_session_produces_follow_up_comparison(self):
        first_store = _Store()
        first = TroubleshootingService(
            collector=_Collector(),
            store=first_store,
            variant_resolver=lambda: "traditional",
        ).run("network_problem").session
        second_store = _Store((first,))
        outcome = TroubleshootingService(
            collector=_Collector(),
            store=second_store,
            variant_resolver=lambda: "traditional",
        ).run("network_problem")

        self.assertIsNotNone(outcome.comparison)
        self.assertTrue(outcome.comparison.comparable)
        self.assertEqual(outcome.comparison.before_session_id, first.session_id)
        self.assertEqual(outcome.comparison.after_session_id, outcome.session.session_id)

    def test_future_or_unwritable_store_never_blocks_the_in_memory_result(self):
        store = _Store(
            reason_code="future-schema-read-only",
            save_error=ValueError("future schema"),
        )
        outcome = TroubleshootingService(
            collector=_Collector(),
            store=store,
            variant_resolver=lambda: "traditional",
        ).run("network_problem")

        self.assertEqual(outcome.session.state, "completed")
        self.assertEqual(
            outcome.persistence_reason_code,
            "future-schema-read-only",
        )
        self.assertEqual(store.saved, [])


if __name__ == "__main__":
    unittest.main()
