"""v25 Proof Activity & Recovery 2.0 contracts."""

from __future__ import annotations

import unittest

from core.change_journal.models import ChangeEvent, ChangeSourceStatus, RecoveryCapability
from core.change_journal.service import ChangeJournalService
from core.change_journal.sources import SourceResult


class _Source:
    source = "action_center"

    def __init__(self):
        self.calls = 0

    def collect(self, *, since=None):
        self.calls += 1
        return SourceResult(
            (
                ChangeEvent(
                    "action-center:event",
                    "action_center",
                    100.0,
                    "user",
                    "Updated Fedora packages",
                    ("package-manager", "pkg:demo"),
                    after_facts={
                        "action_id": "update-fedora-system",
                        "expected": {"package": "demo"},
                        "command": ["must-not-export"],
                    },
                    state="succeeded",
                    recovery=RecoveryCapability("manual_guidance", guidance="Review Action Center."),
                ),
                ChangeEvent(
                    "action-center:event-reboot",
                    "action_center",
                    200.0,
                    "user",
                    "Firmware update staged",
                    ("firmware",),
                    state="awaiting_reboot",
                    reboot_required=True,
                ),
            ),
            ChangeSourceStatus("action_center", "available", 201.0),
        )


class TestV25Activity(unittest.TestCase):
    def setUp(self):
        self.source = _Source()
        self.service = ChangeJournalService(sources=(self.source,), cache_ttl=60)

    def test_filters_are_bounded_and_search_action_or_resource_ids(self):
        result = self.service.snapshot(statuses=("succeeded",), search="pkg:demo")
        self.assertEqual([event.event_id for event in result.events], ["action-center:event"])
        result = self.service.snapshot(reboot_required=True)
        self.assertEqual([event.event_id for event in result.events], ["action-center:event-reboot"])
        result = self.service.snapshot(since=150, until=250)
        self.assertEqual([event.event_id for event in result.events], ["action-center:event-reboot"])

    def test_cached_filter_queries_do_not_collect_again(self):
        self.service.snapshot(search="pkg:demo")
        self.service.snapshot(search="pkg:demo")
        self.assertEqual(self.source.calls, 1)

    def test_exports_are_redacted_and_never_include_command_vectors(self):
        exported_json = self.service.export_event("action-center:event", format="json")
        exported_markdown = self.service.export_event("action-center:event", format="markdown")
        self.assertIn("update-", exported_json)
        self.assertIn("Activity & Recovery event", exported_markdown)
        self.assertNotIn("must-not-export", exported_json)
        self.assertNotIn("command", exported_json)

    def test_unknown_export_is_not_silently_empty(self):
        with self.assertRaises(KeyError):
            self.service.export_event("missing")


if __name__ == "__main__":
    unittest.main()
