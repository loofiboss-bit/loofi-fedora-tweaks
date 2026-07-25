"""Activity & Recovery UI contracts."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.change_journal.models import (
    ChangeEvent,
    ChangeJournalSnapshot,
    ChangeSourceStatus,
    RecoveryCapability,
)
from core.product_catalog import catalog_entry, validate_product_catalog
from ui.activity_recovery_tab import ActivityRecoveryTab


def _snapshot(*, recovery: RecoveryCapability) -> ChangeJournalSnapshot:
    event = ChangeEvent(
        event_id="dnf5:event-1",
        source="dnf5",
        occurred_at=100.0,
        actor_class="system",
        summary="Installed demo package",
        resources=("package:demo-1.0-1.x86_64",),
        state="succeeded",
        recovery=recovery,
    )
    return ChangeJournalSnapshot(
        events=(event,),
        sources=(
            ChangeSourceStatus("dnf5", "available", 101.0),
            ChangeSourceStatus("fwupd", "unavailable", 101.0, "tool_missing"),
        ),
        generated_at=101.0,
    )


class TestActivityRecoveryTab(unittest.TestCase):
    def test_route_is_catalog_owned_and_standard(self):
        entry = catalog_entry("activity")

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.plugin.module, "ui.activity_recovery_tab")
        self.assertEqual(entry.destination.id, "system")
        self.assertFalse(entry.placement.advanced_only)
        self.assertEqual(validate_product_catalog(), [])

    def test_initial_state_does_not_collect_sources(self):
        service = SimpleNamespace(snapshot=unittest.mock.MagicMock())

        tab = ActivityRecoveryTab(journal_service=service)

        service.snapshot.assert_not_called()
        self.assertFalse(tab.table.isVisible())
        self.assertFalse(tab.refresh_button.isEnabled())
        tab.close()

    def test_action_center_recovery_handoff_contains_closed_metadata(self):
        tab = ActivityRecoveryTab(journal_service=SimpleNamespace())
        requests: list[tuple[str, dict[str, object]]] = []
        tab.actionCenterRequested.connect(
            lambda action_id, parameters: requests.append(
                (action_id, dict(parameters))
            )
        )
        tab._loaded(
            _snapshot(
                recovery=RecoveryCapability(
                    kind="action_center",
                    action_id="dnf5-history-undo",
                    parameters={"transaction_id": 42},
                    guidance="Review the exact transaction.",
                )
            )
        )

        self.assertEqual(tab.table.rowCount(), 1)
        self.assertIn("Possibly related", tab.related_label.text())
        self.assertTrue(tab.review_button.isVisibleTo(tab))
        tab._review_recovery()
        self.assertEqual(
            requests,
            [("dnf5-history-undo", {"transaction_id": 42})],
        )
        tab.close()

    def test_manual_guidance_never_exposes_recovery_button(self):
        tab = ActivityRecoveryTab(journal_service=SimpleNamespace())
        tab._loaded(
            _snapshot(
                recovery=RecoveryCapability(
                    kind="manual_guidance",
                    guidance="Use the vendor documentation.",
                )
            )
        )

        self.assertFalse(tab.review_button.isVisible())
        self.assertEqual(tab.recovery_guidance.text(), "Use the vendor documentation.")
        tab.close()
