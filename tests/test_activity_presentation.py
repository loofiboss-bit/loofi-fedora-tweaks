"""PyQt-free Activity & Recovery presentation-state contracts."""

from __future__ import annotations

import unittest

from core.change_journal.models import (
    ChangeEvent,
    ChangeJournalSnapshot,
    ChangeSourceStatus,
    RecoveryCapability,
)
from core.change_journal.presentation import (
    error_state,
    initial_state,
    loading_state,
    selected_state,
    snapshot_state,
)


def _event(recovery: RecoveryCapability | None = None) -> ChangeEvent:
    return ChangeEvent(
        "event-1",
        "loofi_app",
        10.0,
        "user",
        "Changed a setting",
        recovery=recovery or RecoveryCapability(),
    )


class TestActivityPresentationState(unittest.TestCase):
    def test_initial_loading_and_error_hide_unsupported_details(self):
        self.assertTrue(initial_state().empty_visible)
        self.assertFalse(loading_state().table_visible)
        self.assertFalse(error_state("failed", has_snapshot=False).refresh_enabled)

    def test_snapshot_states_cover_empty_partial_truncated_and_loaded(self):
        available = ChangeSourceStatus("loofi_app", "available", 11.0)
        unavailable = ChangeSourceStatus(
            "fwupd",
            "unavailable",
            11.0,
            "tool_missing",
        )

        empty = snapshot_state(ChangeJournalSnapshot((), (available,), 11.0))
        partial = snapshot_state(
            ChangeJournalSnapshot((_event(),), (available, unavailable), 11.0)
        )
        truncated = snapshot_state(
            ChangeJournalSnapshot((_event(),), (available,), 11.0, truncated=True)
        )
        loaded = snapshot_state(
            ChangeJournalSnapshot((_event(),), (available,), 11.0)
        )

        self.assertEqual(
            (empty.state, partial.state, truncated.state, loaded.state),
            ("empty", "partial", "truncated", "loaded"),
        )
        self.assertFalse(empty.table_visible)
        self.assertTrue(partial.table_visible)

    def test_selection_distinguishes_recoverable_manual_and_inert(self):
        recoverable = selected_state(
            _event(RecoveryCapability("action_center", "dnf5-history-undo"))
        )
        manual = selected_state(
            _event(RecoveryCapability("manual_guidance", guidance="Review docs."))
        )
        inert = selected_state(_event())

        self.assertEqual(recoverable.state, "recoverable")
        self.assertTrue(recoverable.recovery_review_visible)
        self.assertEqual(manual.state, "manual-only")
        self.assertEqual(inert.state, "selected")


if __name__ == "__main__":
    unittest.main()
