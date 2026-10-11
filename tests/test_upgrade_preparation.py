"""Deterministic Companion preparation observations and unknown boundaries."""
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from core.executor.action_result import ActionResult
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType
from services.software.upgrade_preparation import UpgradePreparationService
from services.software.upgrade_checklist import (
    SCHEMA_ID,
    SCHEMA_VERSION,
    UpgradePreparationChecklist,
    UpgradePreparationChecklistStore,
    UnsupportedFutureChecklistSchema,
)


def profile():
    return PlatformProfile("fedora", int(FEDORA_RELEASE_POLICY.stable_release) - 1, "kde", "KDE", "x86_64",
                           DesktopEnvironment.KDE, SessionType.WAYLAND, DeploymentBackend.DNF5, False,
                           package_manager_command="dnf5")


def results(required=False):
    return [ActionResult(True, "", 0), ActionResult(True, "", 0, stdout='[{"id":"fedora","is_enabled":true}]'),
            ActionResult(not required, "", int(required), stdout=json.dumps([{
                "type": "reboot", "reboot_required": required, "packages": ["kernel"] if required else [],
            }]))]


class TestUpgradePreparation(unittest.TestCase):
    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_healthy_local_observations(self, disk):
        disk.return_value = Mock(free=123, total=456)
        runtime = Mock()
        runtime.execute_read_only.side_effect = results()
        report = UpgradePreparationService(profile=profile(), runtime=runtime).prepare()
        self.assertEqual(report.state, "completed")
        self.assertEqual(report.target_state, "stable")
        self.assertEqual(report.reboot["state"], "not_required")
        self.assertEqual(report.disks[0]["free_bytes"], 123)
        for call in runtime.execute_read_only.call_args_list:
            self.assertIn("--cacheonly", call.args[0])
            self.assertLessEqual(call.kwargs["timeout"], 8)
        self.assertIn("do not predict", report.limitation)

    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_reboot_exit_one_with_valid_hint(self, disk):
        runtime = Mock()
        runtime.execute_read_only.side_effect = results(True)
        report = UpgradePreparationService(profile=profile(), runtime=runtime).prepare()
        self.assertEqual(report.reboot["state"], "required")
        self.assertEqual(report.reboot["packages"], ["kernel"])

    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_malformed_reboot_never_false(self, disk):
        runtime = Mock()
        runtime.execute_read_only.side_effect = results()[:2] + [ActionResult(True, "", 0, stdout='{}')]
        report = UpgradePreparationService(profile=profile(), runtime=runtime).prepare()
        self.assertEqual(report.reboot["state"], "unknown")
        self.assertEqual(report.state, "partial")

    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_inconsistent_reboot_never_false(self, disk):
        runtime = Mock()
        runtime.execute_read_only.side_effect = results()[:2] + [ActionResult(False, "", 1, stdout=json.dumps([{
            "type": "reboot", "reboot_required": False, "packages": [],
        }]))]
        self.assertEqual(UpgradePreparationService(profile=profile(), runtime=runtime).prepare().reboot["state"], "unknown")

    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_atomic_never_probes_dnf(self, disk):
        runtime = Mock()
        host = replace(profile(), deployment_backend=DeploymentBackend.RPM_OSTREE, is_atomic=True)
        report = UpgradePreparationService(profile=host, runtime=runtime).prepare()
        runtime.execute_read_only.assert_not_called()
        self.assertEqual(report.state, "partial")
        self.assertEqual(report.reboot["state"], "unknown")

    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_release_labels(self, disk):
        runtime = Mock()
        runtime.execute_read_only.side_effect = lambda *a, **k: ActionResult(False, "", 127)
        host = replace(profile(), fedora_version=int(FEDORA_RELEASE_POLICY.stable_release))
        service = UpgradePreparationService(profile=host, runtime=runtime)
        self.assertEqual(service.prepare().target_state, "current_release")
        self.assertEqual(service.prepare(FEDORA_RELEASE_POLICY.preview_target).target_state, "preview")
        self.assertEqual(service.prepare("invalid").target_state, "invalid")
        service.profile = replace(host, fedora_version=int(FEDORA_RELEASE_POLICY.preview_release))
        self.assertEqual(service.prepare().target_state, "downgrade")

    @patch("services.software.upgrade_preparation.shutil.disk_usage", side_effect=OSError)
    def test_disk_missing_and_commands_failed_are_unknown(self, disk):
        runtime = Mock()
        runtime.execute_read_only.return_value = ActionResult(False, "", -1)
        report = UpgradePreparationService(profile=profile(), runtime=runtime).prepare()
        self.assertEqual(report.package_database["state"], "unknown")
        self.assertIsNone(report.package_database["healthy"])
        self.assertEqual(report.sources["state"], "unknown")
        self.assertEqual(report.disks[0]["state"], "unknown")

    def test_cancel_before_collection(self):
        from services.software.update_overview import OverviewCancelled
        service = UpgradePreparationService(profile=profile(), runtime=Mock())
        service.cancel()
        with self.assertRaises(OverviewCancelled):
            service.prepare()


class TestPreparationCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_manual_card_without_automatic_collection(self):
        from ui.upgrade_preparation import UpgradePreparationCard
        service = Mock()
        card = UpgradePreparationCard(service=service)
        service.prepare.assert_not_called()
        self.assertFalse(card.backup_files.isChecked())
        self.assertFalse(card.backup_recovery.isChecked())
        self.assertFalse(card.busy)
        card.cleanup()

    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_async_result_renders_and_shutdown_stops(self, disk):
        import time
        from ui.upgrade_preparation import UpgradePreparationCard
        disk.return_value = Mock(free=123, total=456)
        runtime = Mock()
        runtime.execute_read_only.side_effect = results(True)
        service = UpgradePreparationService(profile=profile(), runtime=runtime)
        with tempfile.TemporaryDirectory() as directory:
            store = UpgradePreparationChecklistStore(path=Path(directory) / "checklist.json")
            card = UpgradePreparationCard(service=service, checklist_store=store)
            card.backup_files.setChecked(True)
            card.backup_recovery.setChecked(True)
            card.check()
            deadline = time.monotonic() + 2
            while card.busy and time.monotonic() < deadline:
                self.app.processEvents()
            self.assertFalse(card.busy)
            self.assertIsNotNone(card.report)
            self.assertIn("Reboot recommended", card.details.text())
            self.assertIn("kernel", card.details.text())
            self.assertTrue(card.cleanup())
            saved = store.read().checklist
            self.assertTrue(saved.backup_files_confirmed)
            self.assertTrue(saved.backup_recovery_confirmed)
            self.assertEqual(saved.observation_target, FEDORA_RELEASE_POLICY.stable_target)
            self.assertEqual(saved.observation_state, "completed")

    def test_saved_checklist_resumes_confirmations_and_marks_other_target_stale(self):
        from ui.upgrade_preparation import UpgradePreparationCard
        from services.software.upgrade_preparation import UpgradePreparationReport

        with tempfile.TemporaryDirectory() as directory:
            store = UpgradePreparationChecklistStore(path=Path(directory) / "checklist.json")
            now = datetime.now(timezone.utc).isoformat()
            store.save(UpgradePreparationChecklist(
                target=FEDORA_RELEASE_POLICY.stable_target,
                updated_at=now,
                observation_target=FEDORA_RELEASE_POLICY.stable_target,
                observation_checked_at=now,
                observation_state="completed",
                third_party_source_ids=("rpmfusion-free",),
                backup_files_confirmed_at=now,
            ))
            card = UpgradePreparationCard(service=Mock(), checklist_store=store)
            self.assertTrue(card.backup_files.isChecked())
            self.assertFalse(card.backup_recovery.isChecked())
            self.assertIn("Saved observations for", card.checklist_status.text())
            card.target.setCurrentIndex(card.target.count() - 1)
            self.assertIn("stale", card.checklist_status.text().casefold())
            self.assertTrue(store.read().checklist.backup_files_confirmed)

            report = UpgradePreparationReport(
                FEDORA_RELEASE_POLICY.preview_target, "preview", profile().to_dict(), {}, now,
                {"state": "observed", "healthy": True},
                {"state": "observed", "third_party_source_ids": ["example-repo"]},
                (), {"state": "not_required"}, state="completed",
            )
            card._completed(report)
            updated = store.read().checklist
            self.assertTrue(updated.backup_files_confirmed)
            self.assertEqual(updated.observation_target, FEDORA_RELEASE_POLICY.preview_target)
            self.assertEqual(updated.third_party_source_ids, ("example-repo",))
            card.cleanup()

    def test_update_page_focuses_preparation(self):
        from ui.update_workflow import UpdateWorkflowPage
        page = UpdateWorkflowPage(service=Mock())
        self.assertTrue(page.focus_task("update:prepare-upgrade"))
        self.assertFalse(page.busy)
        page.request_stop()
        page.cleanup()


class TestPreparationCli(unittest.TestCase):
    @patch("services.software.upgrade_preparation.UpgradePreparationService")
    def test_cli_uses_same_report(self, service_cls):
        from argparse import Namespace
        from cli.commands.update_commands import handle_updates
        report = Mock(state="partial")
        report.to_dict.return_value = {"schema": "loofi.upgrade-preparation/v1", "state": "partial"}
        service_cls.return_value.prepare.return_value = report
        output = Mock()
        result = handle_updates(Namespace(action="prepare-upgrade", target=FEDORA_RELEASE_POLICY.preview_target),
                                True, output, Mock(), Mock(), Mock())
        self.assertEqual(result, 1)
        service_cls.return_value.prepare.assert_called_once_with(FEDORA_RELEASE_POLICY.preview_target)
        output.assert_called_once_with(report.to_dict.return_value)


class TestPreparationSourceBoundaries(unittest.TestCase):
    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_known_sources_and_disabled_state(self, disk):
        disk.return_value = Mock(free=1, total=2)
        runtime = Mock()
        observations = results()
        observations[1] = ActionResult(True, "", 0, stdout=json.dumps([
            {"id": "fedora", "is_enabled": True},
            {"id": "updates", "is_enabled": True},
            {"id": "rpmfusion-free", "is_enabled": True},
            {"id": "rpmfusion-nonfree", "is_enabled": False},
            {"id": "copr:copr.fedorainfracloud.org:example:tool", "is_enabled": True},
        ]))
        runtime.execute_read_only.side_effect = observations
        sources = UpgradePreparationService(profile=profile(), runtime=runtime).prepare().sources
        self.assertEqual(sources["enabled_count"], 4)
        self.assertEqual(sources["known_sources"]["rpmfusion-free"], "enabled")
        self.assertEqual(sources["known_sources"]["rpmfusion-nonfree"], "disabled")
        self.assertEqual(
            sources["third_party_source_ids"],
            ["copr:copr.fedorainfracloud.org:example:tool", "rpmfusion-free", "rpmfusion-nonfree"],
        )

    @patch("services.software.upgrade_preparation.shutil.disk_usage")
    def test_duplicate_and_nonboolean_sources_unknown(self, disk):
        disk.return_value = Mock(free=1, total=2)
        for rows in ([{"id": "fedora", "is_enabled": 1}],
                     [{"id": "fedora", "is_enabled": True}, {"id": "FEDORA", "is_enabled": False}]):
            runtime = Mock()
            runtime.execute_read_only.side_effect = [ActionResult(False, "", 1),
                                                     ActionResult(True, "", 0, stdout=json.dumps(rows)), results()[2]]
            report = UpgradePreparationService(profile=profile(), runtime=runtime).prepare()
            self.assertEqual(report.sources["state"], "unknown")
            self.assertNotIn("enabled_count", report.sources)
            self.assertIsNone(report.package_database["healthy"])
            self.assertEqual(report.package_database["reason"], "local_check_failed")


class TestUpgradePreparationChecklist(unittest.TestCase):
    def test_round_trip_and_observation_freshness_do_not_clear_user_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = UpgradePreparationChecklistStore(path=Path(directory) / "checklist.json")
            checked = datetime(2026, 10, 1, tzinfo=timezone.utc)
            checklist = UpgradePreparationChecklist(
                target=FEDORA_RELEASE_POLICY.stable_target,
                updated_at=checked.isoformat(),
                observation_target=FEDORA_RELEASE_POLICY.stable_target,
                observation_checked_at=checked.isoformat(),
                observation_state="completed",
                third_party_source_ids=("rpmfusion-free",),
                backup_files_confirmed_at=checked.isoformat(),
            )
            store.save(checklist)
            saved = store.read()
            self.assertTrue(saved.writable)
            self.assertEqual(saved.checklist, checklist)
            self.assertTrue(saved.checklist.observations_are_stale(
                selected_target=checklist.target, now=checked + timedelta(days=8)))
            self.assertTrue(saved.checklist.backup_files_confirmed)
            self.assertFalse(saved.checklist.observations_are_stale(
                selected_target=checklist.target, now=checked + timedelta(days=6)))
            self.assertTrue(saved.checklist.observations_are_stale(
                selected_target=checklist.target, now=checked - timedelta(minutes=1)))

    def test_future_schema_is_never_overwritten_and_malformed_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checklist.json"
            path.write_text(json.dumps({"schema_id": SCHEMA_ID, "schema_version": SCHEMA_VERSION + 1}), encoding="utf-8")
            store = UpgradePreparationChecklistStore(path=path)
            snapshot = store.read()
            self.assertFalse(snapshot.writable)
            with self.assertRaises(UnsupportedFutureChecklistSchema):
                store.save(UpgradePreparationChecklist())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], SCHEMA_VERSION + 1)
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "malformed"):
                store.read()
