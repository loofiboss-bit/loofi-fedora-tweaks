"""Continuity support bundle contracts."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.change_journal.models import (
    ChangeEvent,
    ChangeJournalSnapshot,
    ChangeSourceStatus,
    RecoveryCapability,
)
from core.export.support_bundle import CURRENT_SUPPORT_BUNDLE_VERSION
from core.export.support_bundle_v12 import SupportBundleV12


class TestSupportBundleV12(TestCase):
    @patch(
        "core.export.support_bundle_v11.SupportBundleV11.generate_bundle",
        return_value={"legacy": True},
    )
    @patch("core.change_journal.ChangeJournalService")
    def test_change_journal_is_bounded_redacted_and_inert(
        self,
        service_class,
        _legacy,
    ):
        service_class.return_value.snapshot.return_value = ChangeJournalSnapshot(
            events=(
                ChangeEvent(
                    event_id="dnf5:event",
                    source="dnf5",
                    occurred_at=1.0,
                    actor_class="system",
                    summary="Changed token=private-value",
                    resources=("package:demo",),
                    recovery=RecoveryCapability(
                        kind="action_center",
                        action_id="dnf5-history-undo",
                        parameters={"transaction_id": 7},
                    ),
                ),
            ),
            sources=(ChangeSourceStatus("dnf5", "available", 2.0),),
            generated_at=2.0,
        )

        bundle = SupportBundleV12.generate_bundle()

        self.assertEqual(bundle["support_bundle_version"], 12)
        self.assertEqual(CURRENT_SUPPORT_BUNDLE_VERSION, 12)
        self.assertEqual(bundle["change_journal"]["event_limit"], 50)
        self.assertFalse(bundle["change_journal"]["raw_command_output_included"])
        self.assertFalse(bundle["change_journal"]["recovery_commands_included"])
        self.assertNotIn("private-value", str(bundle))
        service_class.return_value.snapshot.assert_called_once_with(
            limit=50,
            refresh=True,
        )
