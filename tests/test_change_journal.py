"""Trusted Change Journal domain, source, and composition contracts."""

import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.change_journal.models import (  # noqa: E402
    CHANGE_JOURNAL_SCHEMA,
    ChangeEvent,
    ChangeSourceStatus,
    RecoveryCapability,
    stable_event_id,
)
from core.change_journal.service import ChangeJournalService  # noqa: E402
from core.change_journal.sources import (  # noqa: E402
    DNF5HistorySource,
    FlatpakHistorySource,
    RpmOstreeHistorySource,
    SourceResult,
)
from core.execution_policy import classify_command  # noqa: E402
from core.executor.action_result import ActionResult  # noqa: E402


class TestChangeJournalModels(unittest.TestCase):
    def test_recovery_is_closed_and_redacted(self):
        recovery = RecoveryCapability(
            "action_center",
            "dnf5-history-undo",
            {"transaction_id": 7, "password": "secret"},
            "Prepare recovery",
        )

        self.assertEqual(recovery.parameters["transaction_id"], 7)
        self.assertEqual(recovery.parameters["password"], "<masked>")
        self.assertNotIn("command", recovery.to_dict())

    def test_action_center_recovery_requires_registered_id(self):
        with self.assertRaises(ValueError):
            RecoveryCapability("action_center")

    def test_event_redacts_private_facts(self):
        event = ChangeEvent(
            event_id=stable_event_id("loofi_app", "one"),
            source="loofi_app",
            occurred_at=10.0,
            actor_class="user",
            summary="Changed /home/alice/file",
            resources=("/home/alice/file",),
            after_facts={"token": "private", "address": "192.168.1.2"},
        )

        payload = event.to_dict()
        self.assertNotIn("alice", payload["summary"])
        self.assertEqual(payload["after_facts"]["token"], "<masked>")
        self.assertEqual(payload["after_facts"]["address"], "<masked-ip>")


class TestJSONSources(unittest.TestCase):
    @patch("core.change_journal.sources.cached_which", return_value="/usr/bin/dnf5")
    def test_dnf5_source_creates_typed_recovery(self, mock_which):
        facade = MagicMock()
        facade.execute.return_value = ActionResult.ok(
            "ok",
            stdout=json.dumps(
                [
                    {
                        "id": 42,
                        "start_time": 100,
                        "end_time": 120,
                        "user_id": 1000,
                        "status": "Ok",
                        "releasever": "44",
                        "altered_count": 5,
                        "command_line": "dnf5 install token=secret",
                    }
                ]
            ),
        )

        result = DNF5HistorySource(facade=facade, clock=lambda: 200).collect()

        self.assertEqual(result.status.availability, "available")
        self.assertEqual(len(result.events), 1)
        event = result.events[0]
        self.assertEqual(event.recovery.action_id, "dnf5-history-undo")
        self.assertEqual(event.recovery.parameters["transaction_id"], 42)
        self.assertNotIn("command_line", event.to_dict()["after_facts"])
        facade.execute.assert_called_once_with(
            ("dnf5", "history", "list", "--json"),
            timeout=15,
            action_id="change-journal:dnf5",
        )

    @patch("core.change_journal.sources.cached_which", return_value="/usr/bin/rpm-ostree")
    def test_rpm_ostree_recovery_requires_existing_previous_deployment(self, mock_which):
        facade = MagicMock()
        facade.execute.return_value = ActionResult.ok(
            "ok",
            stdout=json.dumps(
                {
                    "deployments": [
                        {"checksum": "current", "booted": True, "timestamp": 200},
                        {"checksum": "previous", "booted": False, "timestamp": 100},
                    ]
                }
            ),
        )

        result = RpmOstreeHistorySource(facade=facade).collect()

        current = next(event for event in result.events if event.state == "booted")
        self.assertEqual(current.recovery.action_id, "rpm-ostree-rollback")
        self.assertEqual(current.recovery.parameters["rollback_deployment"], "previous")

    @patch("core.change_journal.sources.cached_which", return_value="/usr/bin/flatpak")
    def test_flatpak_history_is_manual_guidance_only(self, mock_which):
        facade = MagicMock()
        facade.execute.return_value = ActionResult.ok(
            "ok",
            stdout=json.dumps(
                [
                    {
                        "time": "2026-07-25T10:00:00+00:00",
                        "change": "update",
                        "ref": "app/org.example.App/x86_64/stable",
                        "commit": "new",
                        "old-commit": "old",
                    }
                ]
            ),
        )

        event = FlatpakHistorySource(facade=facade).collect().events[0]

        self.assertEqual(event.recovery.kind, "manual_guidance")
        self.assertIsNone(event.recovery.action_id)

    @patch("core.change_journal.sources.cached_which", return_value=None)
    def test_missing_source_is_unavailable_not_empty_success(self, mock_which):
        result = DNF5HistorySource(facade=MagicMock(), clock=lambda: 100).collect()

        self.assertEqual(result.events, ())
        self.assertEqual(result.status.availability, "unavailable")
        self.assertEqual(result.status.error_code, "tool_unavailable")

    def test_history_commands_are_classified_read_only(self):
        self.assertEqual(
            classify_command("dnf5", ["history", "list", "--json"]),
            "read_only",
        )
        self.assertEqual(
            classify_command("flatpak", ["history", "--json"]),
            "read_only",
        )
        self.assertEqual(
            classify_command("dnf5", ["history", "undo", "8"]),
            "host",
        )


class _FakeSource:
    def __init__(self, source, events, availability="available"):
        self.source = source
        self.events = tuple(events)
        self.availability = availability
        self.calls = 0

    def collect(self, *, since=None):
        self.calls += 1
        events = tuple(
            event
            for event in self.events
            if since is None or event.occurred_at >= since
        )
        return SourceResult(
            events,
            ChangeSourceStatus(self.source, self.availability, 100.0),
        )


class TestChangeJournalService(unittest.TestCase):
    def test_snapshot_is_sorted_bounded_and_correlated(self):
        package_event = ChangeEvent(
            stable_event_id("dnf5", "1"),
            "dnf5",
            200.0,
            "user",
            "Package change",
            ("package-manager",),
        )
        action_event = ChangeEvent(
            stable_event_id("action_center", "1"),
            "action_center",
            190.0,
            "user",
            "Reviewed change",
            ("package-manager",),
        )
        source_a = _FakeSource("dnf5", [package_event])
        source_b = _FakeSource("action_center", [action_event])
        service = ChangeJournalService(
            sources=[source_a, source_b],
            clock=lambda: 300.0,
            cache_ttl=30,
        )

        snapshot = service.snapshot(limit=1)

        self.assertEqual(snapshot.schema, CHANGE_JOURNAL_SCHEMA)
        self.assertTrue(snapshot.truncated)
        self.assertEqual(snapshot.events[0].event_id, package_event.event_id)
        self.assertEqual(snapshot.events[0].correlation_ids, (action_event.event_id,))
        self.assertEqual(source_a.calls, 1)
        self.assertIs(service.snapshot(limit=1), snapshot)

    def test_partial_source_is_preserved_in_snapshot(self):
        source = _FakeSource("fwupd", [], availability="partial")
        snapshot = ChangeJournalService(
            sources=[source],
            clock=lambda: 300.0,
        ).snapshot()

        self.assertEqual(snapshot.events, ())
        self.assertEqual(snapshot.sources[0].availability, "partial")

    def test_source_filter_and_since_are_forwarded(self):
        source_a = _FakeSource("dnf5", [])
        source_b = _FakeSource("flatpak", [])
        service = ChangeJournalService(
            sources=[source_a, source_b],
            clock=lambda: 300.0,
        )

        service.snapshot(since=250.0, sources=["dnf5"])

        self.assertEqual(source_a.calls, 1)
        self.assertEqual(source_b.calls, 0)


if __name__ == "__main__":
    unittest.main()
