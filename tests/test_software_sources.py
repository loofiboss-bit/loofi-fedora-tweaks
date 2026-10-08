"""Configured DNF sources remain complete, read-only and display-safe."""

import json
import subprocess
import time
import unittest
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication

from cli.commands.update_commands import handle_updates
from cli.parser import build_parser
from services.software.source_status import DnfRepository, DnfSourceSnapshot, SoftwareSourceStatusService, SourceState, SourceStatusReason
from ui.software_sources import SoftwareSourcesWidget


class SourceSnapshotTests(unittest.TestCase):
    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/dnf5")
    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.source_status.subprocess.run")
    def test_all_sources_names_and_disabled_configuration_share_badge_observation(self, run, _manager, _which):
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps([
            {"id": "z-private", "name": "Private", "is_enabled": False},
            {"id": "rpmfusion-free-updates", "name": "RPM Fusion", "is_enabled": True},
        ]), "")
        service = SoftwareSourceStatusService()
        snapshot = service.sources_snapshot()
        self.assertTrue(snapshot.success)
        self.assertTrue(snapshot.observed_at.endswith("+00:00"))
        self.assertEqual([repo.source_id for repo in snapshot.repositories], ["rpmfusion-free-updates", "z-private"])
        self.assertFalse(snapshot.repositories[1].enabled)
        self.assertEqual(service.badges_from_sources(snapshot)[0].state, SourceState.ENABLED)
        run.assert_called_once()

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/dnf5")
    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.source_status.subprocess.run")
    def test_incomplete_and_duplicate_records_are_unknown_not_empty_success(self, run, _manager, _which):
        cases = [
            [{"id": "fedora", "is_enabled": True}],
            [{"id": "fedora", "name": "Fedora", "is_enabled": "true"}],
            [{"id": value, "name": "Fedora", "is_enabled": True} for value in ("Fedora", "fedora")],
            {}, [None],
        ]
        for records in cases:
            with self.subTest(records=records):
                run.return_value = subprocess.CompletedProcess([], 0, json.dumps(records), "")
                snapshot = SoftwareSourceStatusService().sources_snapshot()
                self.assertFalse(snapshot.success)
                self.assertEqual(snapshot.reason, SourceStatusReason.INVALID_RESPONSE)
                self.assertFalse(snapshot.repositories)

    @patch("services.software.source_status.SoftwareSourceStatusService._flatpak_status")
    @patch("services.software.source_status.SoftwareSourceStatusService.sources_snapshot")
    def test_combined_observation_derives_badges_from_one_dnf_query(self, read, flatpak):
        from services.software.source_status import SourceScope, SourceStatus
        snapshot = DnfSourceSnapshot("now", (DnfRepository("rpmfusion-free", "Free", True),))
        read.return_value = snapshot
        flatpak.side_effect = lambda scope: SourceStatus("flathub", scope, SourceState.DISABLED)
        observation, statuses = SoftwareSourceStatusService().combined_snapshot()
        self.assertIs(observation, snapshot)
        self.assertEqual(statuses[0].state, SourceState.ENABLED)
        self.assertEqual([item.scope for item in statuses[-2:]], [SourceScope.SYSTEM, SourceScope.USER])
        read.assert_called_once_with()

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/dnf5")
    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.source_status.subprocess.run")
    def test_duplicate_json_fields_are_unknown(self, run, _manager, _which):
        run.return_value = subprocess.CompletedProcess([], 0, '[{"id":"fedora","name":"Fedora","is_enabled":true,"is_enabled":false}]', "")
        snapshot = SoftwareSourceStatusService().sources_snapshot()
        self.assertFalse(snapshot.success)
        self.assertEqual(snapshot.reason, SourceStatusReason.INVALID_RESPONSE)
        self.assertFalse(snapshot.repositories)

    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_upgrade_preparation_still_accepts_id_enabled_without_name(self, disk):
        from core.executor.action_result import ActionResult
        from core.fedora_release_policy import FEDORA_RELEASE_POLICY
        from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType
        from services.software.upgrade_preparation import UpgradePreparationService

        disk.return_value = Mock(free=123, total=456)
        profile = PlatformProfile("fedora", int(FEDORA_RELEASE_POLICY.stable_release) - 1, "kde", "KDE", "x86_64",
                                  DesktopEnvironment.KDE, SessionType.WAYLAND, DeploymentBackend.DNF5, False,
                                  package_manager_command="dnf5")
        runtime = Mock()
        runtime.execute_read_only.side_effect = [
            ActionResult(True, "", 0),
            ActionResult(True, "", 0, stdout='[{"id":"rpmfusion-free","is_enabled":true}]'),
            ActionResult(True, "", 0, stdout='[{"type":"reboot","reboot_required":false,"packages":[]}]'),
        ]
        report = UpgradePreparationService(profile=profile, runtime=runtime).prepare()
        self.assertEqual(report.sources["state"], "observed")
        self.assertEqual(report.sources["enabled_count"], 1)
        self.assertEqual(report.sources["known_sources"]["rpmfusion-free"], "enabled")

    def test_export_masks_private_repository_fields(self):
        snapshot = DnfSourceSnapshot("now", (DnfRepository("https://user:secret@example.test/feed", "token=confidential /home/alice/repo", True),))
        payload = json.dumps(snapshot.to_dict())
        self.assertNotIn("secret@", payload)
        self.assertNotIn("confidential", payload)
        self.assertNotIn("alice", payload)

    @patch("services.software.source_status.SoftwareSourceStatusService.sources_snapshot")
    def test_cli_text_and_json_use_same_payload_and_failure_exit(self, read):
        snapshot = DnfSourceSnapshot("now", (DnfRepository("fedora", "Fedora", True),))
        read.return_value = snapshot
        output, print_fn = Mock(), Mock()
        args = build_parser().parse_args(["--json", "updates", "sources"])
        self.assertEqual(handle_updates(args, True, output, print_fn, Mock(), Mock()), 0)
        output.assert_called_once_with(snapshot.to_dict())
        self.assertEqual(handle_updates(args, False, output, print_fn, Mock(), Mock()), 0)
        self.assertIn("fedora: Fedora (Enabled)", print_fn.call_args.args[0])
        read.return_value = DnfSourceSnapshot("now", reason=SourceStatusReason.TIMEOUT)
        self.assertEqual(handle_updates(SimpleNamespace(action="sources"), True, output, print_fn, Mock(), Mock()), 1)
        self.assertEqual(output.call_args.args[0]["reason"], "timeout")


class SourcesWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.service = Mock()
        self.widget = SoftwareSourcesWidget(self.service)
        self.addCleanup(self.widget.deleteLater)

    def pump_until(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.001)
        self.assertTrue(predicate())

    def test_search_covers_id_name_and_state_and_preserves_observation(self):
        snapshot = DnfSourceSnapshot("now", (DnfRepository("fedora", "Fedora Linux", True), DnfRepository("private", "Example", False)))
        emitted = Mock()
        self.widget.snapshotChanged.connect(emitted)
        self.widget.set_snapshot(snapshot)
        self.widget.search.setText("disabled")
        self.assertTrue(self.widget.table.topLevelItem(0).isHidden())
        self.assertFalse(self.widget.table.topLevelItem(1).isHidden())
        emitted.assert_called_once_with(snapshot)
        self.service.sources_snapshot.assert_not_called()

    def test_unknown_clears_previously_successful_results(self):
        self.widget.set_snapshot(DnfSourceSnapshot("old", (DnfRepository("fedora", "Fedora", True),)))
        self.widget.set_snapshot(DnfSourceSnapshot("now", reason=SourceStatusReason.INVALID_RESPONSE))
        self.assertEqual(self.widget.table.topLevelItemCount(), 0)
        self.assertIn("Unknown", self.widget.status.text())
        self.assertIn("invalid", self.widget.status.text())

    def test_refresh_is_async_single_flight_and_reenabled(self):
        entered, release = Event(), Event()
        def read():
            entered.set()
            release.wait(2)
            return DnfSourceSnapshot("now")
        self.service.sources_snapshot.side_effect = read
        self.widget.refresh()
        self.pump_until(entered.is_set)
        self.widget.refresh()
        self.assertEqual(self.service.sources_snapshot.call_count, 1)
        self.assertFalse(self.widget.refresh_button.isEnabled())
        release.set()
        self.pump_until(lambda: not self.widget._adapter.busy)
        self.assertTrue(self.widget.refresh_button.isEnabled())
        self.assertTrue(self.widget.snapshot.success)
