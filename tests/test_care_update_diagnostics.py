"""Care diagnostics preserve source ownership and never retry updates."""

import argparse
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cli.commands.update_commands import handle_updates
from core.executor.action_result import ActionResult
from core.troubleshooting.lifecycle import CancellationSignal, new_session
from core.troubleshooting.service import DefaultEvidenceCollector
from services.software.update_diagnostics import SOURCE_PROFILES, UpdateDiagnosticsService, collect_update_health
from services.software.update_overview import UpdateOverviewSnapshot, UpdateSourceResult


class UpdateDiagnosticsTests(unittest.TestCase):
    def test_shared_service_selects_exact_profile_and_run(self):
        backend = Mock()
        service = UpdateDiagnosticsService(backend)
        for source, profile in SOURCE_PROFILES.items():
            service.diagnose(source, run_id="run-123")
            backend.run.assert_called_with(profile, parameters={"run_id": "run-123"})
        with self.assertRaises(ValueError):
            service.diagnose("other")

    @patch("core.troubleshooting.service.adapt_action_center")
    @patch("core.actions.stores.ActionRunStore")
    @patch("core.actions.stores.ActionPlanStore")
    def test_exact_run_is_not_limited_to_recent_25(self, plans_cls, runs_cls, adapt):
        chosen = SimpleNamespace(run_id="run-older", plan_id="plan-old", action_id="update-flatpaks")
        runs_cls.return_value.list_read_only.return_value = [chosen] + [
            SimpleNamespace(run_id=f"run-{i}", plan_id="x", action_id="update-fedora-system") for i in range(30)
        ]
        plans_cls.return_value.list_read_only.return_value = []
        session = new_session("flatpak_updates_failed", "traditional", started_at=1, parameters={"run_id": "run-older"})
        DefaultEvidenceCollector(clock=lambda: 2)._action_center(session, 1)
        runs_cls.return_value.list_read_only.assert_called_once_with(limit=None)
        self.assertEqual(adapt.call_args.args[1], [chosen])

    @patch("core.actions.stores.ActionRunStore")
    @patch("core.actions.stores.ActionPlanStore")
    def test_wrong_source_run_is_unavailable(self, plans_cls, runs_cls):
        runs_cls.return_value.list_read_only.return_value = [SimpleNamespace(run_id="run-123", action_id="update-fedora-system")]
        plans_cls.return_value.list_read_only.return_value = []
        session = new_session("flatpak_updates_failed", "traditional", started_at=1, parameters={"run_id": "run-123"})
        evidence = DefaultEvidenceCollector(clock=lambda: 2)._action_center(session, 1)
        self.assertEqual(evidence.result.state, "unavailable")
        self.assertEqual(evidence.result.reason_code, "requested-update-run-unavailable")

    @patch("services.software.update_diagnostics.shutil.which", return_value=None)
    def test_missing_optional_tool_is_explicit(self, _which):
        session = new_session("flatpak_updates_failed", "traditional", started_at=1)
        evidence = collect_update_health(DefaultEvidenceCollector(clock=lambda: 2), "flatpak-update-health", session, 1, CancellationSignal())
        self.assertEqual(evidence.result.state, "unavailable")
        self.assertEqual(evidence.result.reason_code, "update-tool-missing")

    @patch("services.software.update_diagnostics._DiagnosticRuntime")
    @patch("services.software.update_diagnostics.shutil.which", return_value="/usr/bin/flatpak")
    def test_user_app_can_use_public_system_runtime_without_private_output(self, _which, runtime_cls):
        runtime_cls.return_value.execute_read_only.side_effect = [
            ActionResult(True, "", 0, stdout="org.example.App/x86_64/stable\torg.example.Platform/x86_64/stable\tuser\norg.example.Platform/x86_64/stable\t\tsystem\n"),
            ActionResult(True, "", 0, stdout="private-remote\tuser\n"),
        ]
        session = new_session("flatpak_updates_failed", "traditional", started_at=1)
        evidence = collect_update_health(DefaultEvidenceCollector(clock=lambda: 2), "flatpak-update-health", session, 1, CancellationSignal())
        facts = evidence.result.to_dict()["facts"]
        self.assertEqual(facts["missing_runtime_count"], 0)
        self.assertEqual(facts["error_code"], "")
        self.assertNotIn("private-remote", str(evidence.result.to_dict()))
        self.assertEqual(runtime_cls.call_args.kwargs["output_limit"], 1024 * 1024)
        self.assertLessEqual(runtime_cls.return_value.execute_read_only.call_args.kwargs["timeout"], 15)

    @patch("services.software.update_diagnostics._DiagnosticRuntime")
    @patch("services.software.update_diagnostics.shutil.which", return_value="/usr/bin/flatpak")
    def test_runtime_scope_fallback_and_actual_missing(self, _which, runtime_cls):
        for installation, runtime_installation, missing in (("user", "work", 0), ("work", "system", 0), ("system", "user", 1), ("user", None, 1)):
            with self.subTest(installation=installation, runtime_installation=runtime_installation):
                inventory = f"org.example.App/x86_64/stable\torg.example.Platform/x86_64/stable\t{installation}\n"
                if runtime_installation:
                    inventory += f"org.example.Platform/x86_64/stable\t\t{runtime_installation}\n"
                runtime_cls.return_value.execute_read_only.side_effect = [
                    ActionResult(True, "", 0, stdout=inventory), ActionResult(True, "", 0, stdout="flathub\tuser\n"),
                ]
                session = new_session("flatpak_updates_failed", "traditional", started_at=1)
                evidence = collect_update_health(DefaultEvidenceCollector(clock=lambda: 2), "flatpak-update-health", session, 1, CancellationSignal())
                self.assertEqual(evidence.result.to_dict()["facts"]["missing_runtime_count"], missing)

    @patch("services.software.update_diagnostics._DiagnosticRuntime")
    @patch("services.software.update_diagnostics.shutil.which", return_value="/usr/bin/flatpak")
    def test_malformed_success_outputs_remain_partial(self, _which, runtime_cls):
        for source, source_id, profile, outputs in (
            ("flatpak", "flatpak-update-health", "flatpak_updates_failed", ("malformed", "flathub\tuser\n")),
            ("flatpak", "flatpak-update-health", "flatpak_updates_failed", ("", "invalid-remote")),
            ("firmware", "firmware-update-health", "firmware_updates_failed", ("active", '{"Devices": "invalid"}')),
            ("firmware", "firmware-update-health", "firmware_updates_failed", ("unknown-state", '{"Devices": []}')),
        ):
            with self.subTest(source=source, outputs=outputs):
                runtime_cls.return_value.execute_read_only.side_effect = [ActionResult(True, "", 0, stdout=output) for output in outputs]
                session = new_session(profile, "traditional", started_at=1)
                evidence = collect_update_health(DefaultEvidenceCollector(clock=lambda: 2), source_id, session, 1, CancellationSignal())
                self.assertEqual(evidence.result.state, "partial")
                self.assertTrue(evidence.result.reason_code)
                self.assertTrue(evidence.result.to_dict()["facts"]["error_code"])

    @patch("services.software.update_diagnostics._DiagnosticRuntime")
    @patch("services.software.update_diagnostics.shutil.which", return_value="/usr/bin/fwupdmgr")
    def test_firmware_reads_only_service_and_devices(self, _which, runtime_cls):
        runtime_cls.return_value.execute_read_only.side_effect = [
            ActionResult(True, "", 0, stdout="active\n"),
            ActionResult(True, "", 0, stdout='{"Devices": [{"Serial": "private"}]}'),
        ]
        session = new_session("firmware_updates_failed", "traditional", started_at=1)
        evidence = collect_update_health(DefaultEvidenceCollector(clock=lambda: 2), "firmware-update-health", session, 1, CancellationSignal())
        self.assertEqual(evidence.result.to_dict()["facts"]["device_count"], 1)
        self.assertNotIn("private", str(evidence.result.to_dict()))
        vectors = [call.args[0] for call in runtime_cls.return_value.execute_read_only.call_args_list]
        self.assertEqual(vectors, [("systemctl", "is-active", "fwupd.service"), ("fwupdmgr", "get-devices", "--json")])

    @patch("services.software.update_diagnostics.UpdateDiagnosticsService")
    def test_cli_diagnose_uses_same_service_and_session_contract(self, service_cls):
        session = Mock(state="completed")
        session.to_dict.return_value = {"profile_id": "firmware_updates_failed", "profile_parameters": {"run_id": "run-exact"}}
        service_cls.return_value.diagnose.return_value = SimpleNamespace(session=session, persistence_reason_code="")
        output = Mock()
        code = handle_updates(argparse.Namespace(action="diagnose", source="firmware", run_id="run-exact"), True, output, Mock(), Mock(), Mock())
        self.assertEqual(code, 0)
        service_cls.return_value.diagnose.assert_called_once_with("firmware", run_id="run-exact")
        self.assertEqual(output.call_args.args[0]["profile_id"], "firmware_updates_failed")
        self.assertEqual(output.call_args.args[0]["profile_parameters"], {"run_id": "run-exact"})

    @patch("services.software.update_overview.UpdateOverviewService")
    def test_cli_check_reports_source_failure_instead_of_up_to_date(self, service_cls):
        service_cls.return_value.check.return_value = UpdateOverviewSnapshot(sources=(
            UpdateSourceResult("system", "error", error_code="check-failed"),
            UpdateSourceResult("flatpak", "up_to_date"), UpdateSourceResult("firmware", "missing_tool"),
        ))
        output, print_fn = Mock(), Mock()
        code = handle_updates(argparse.Namespace(action="check"), True, output, print_fn, Mock(), Mock())
        self.assertEqual(code, 1)
        self.assertFalse(output.call_args.args[0]["success"])
        self.assertEqual(output.call_args.args[0]["sources"][0]["status"], "error")


class UpdateDiagnosisUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_diagnose_button_emits_source_and_exact_run(self):
        from core.tasks import UpdateSourceState
        from ui.update_workflow import UpdateWorkflowPage

        page = UpdateWorkflowPage(service=Mock())
        self.addCleanup(page.close)
        receiver = Mock()
        page.diagnosisRequested.connect(receiver)
        page.set_source(UpdateSourceState("flatpak", "verification_failed", run_id="run-exact"))
        self.assertFalse(page._diagnose_buttons["flatpak"].isHidden())
        self.assertTrue(page._diagnose_buttons["system"].isHidden())
        page._diagnose_buttons["flatpak"].click()
        receiver.assert_called_once_with("flatpak", "run-exact")
        page.service.check.assert_not_called()

    def test_health_selection_preserves_exact_context_without_starting(self):
        from ui.troubleshoot_widget import TroubleshootWidget

        history = Mock()
        history.latest.return_value = (None, "")
        factory = Mock()
        page = TroubleshootWidget(history=history, worker_factory=factory)
        self.addCleanup(page.close)
        self.assertTrue(page.preselect_update_diagnosis("firmware", "run-exact"))
        self.assertEqual(page.selected_profile_id(), "firmware_updates_failed")
        factory.assert_not_called()
        page.start_session()
        factory.assert_called_once_with("firmware_updates_failed", {"run_id": "run-exact"}, page)
        page._worker = None
        page.update_source_selector.setCurrentIndex(1)
        self.assertEqual(page._update_run_id, "")
        self.assertEqual(page.selected_profile_id(), "flatpak_updates_failed")

    def test_main_window_routes_exact_context_to_health(self):
        from ui.main_window_utility import MainWindowUtilityMixin

        health = Mock()
        window = SimpleNamespace(
            switch_to_route=Mock(return_value=True), _sidebar_index={"utility_fix": "entry"},
            _real_widget_for_entry=Mock(return_value=health),
        )
        MainWindowUtilityMixin._open_update_diagnosis(window, "flatpak", "run-exact")
        window.switch_to_route.assert_called_once_with("health")
        health.preselect_update_diagnosis.assert_called_once_with("flatpak", "run-exact")

    def test_storage_link_is_visible_only_for_storage_symptom(self):
        from ui.troubleshoot_widget import TroubleshootWidget

        history = Mock()
        history.latest.return_value = (None, "")
        page = TroubleshootWidget(history=history, worker_factory=Mock())
        self.addCleanup(page.close)
        receiver = Mock()
        page.routeRequested.connect(receiver)
        self.assertTrue(page.unused_runtimes_link.isHidden())
        page.profile_selector.setCurrentIndex(page.profile_selector.findData("storage_full"))
        self.assertFalse(page.unused_runtimes_link.isHidden())
        page.unused_runtimes_link.click()
        receiver.assert_called_once_with("software:apps", {"section": "unused-runtimes"})
        page.worker_factory.assert_not_called()

    def test_apps_runtime_navigation_validates_known_scope_without_probe(self):
        from PyQt6.QtWidgets import QComboBox
        from ui.main_window_utility import MainWindowUtilityMixin

        installations, view = QComboBox(), QComboBox()
        installations.addItems(["user", "system", "work"])
        view.addItem("Available", "available")
        view.addItem("Installed", "installed")
        insights = SimpleNamespace(installation=installations, inspect_button=Mock(), inspect=Mock(), discover_installations=Mock())
        page = SimpleNamespace(installed_card=SimpleNamespace(insights=insights), view_filter=view, body_scroll=Mock())
        window = SimpleNamespace(switch_to_route=Mock(return_value=True), _sidebar_index={"utility_install": "entry"}, _real_widget_for_entry=Mock(return_value=page))
        self.assertTrue(MainWindowUtilityMixin._open_apps_unused_runtimes(window, {"section": "unused-runtimes", "installation": "work"}))
        self.assertEqual(installations.currentText(), "work")
        self.assertEqual(view.currentData(), "installed")
        insights.inspect_button.setFocus.assert_called_once()
        insights.inspect.assert_not_called()
        insights.discover_installations.assert_not_called()
        self.assertFalse(MainWindowUtilityMixin._open_apps_unused_runtimes(window, {"section": "unused-runtimes", "installation": "/tmp/private"}))
        self.assertFalse(MainWindowUtilityMixin._open_apps_unused_runtimes(window, {"section": "unused-runtimes", "installation": "unknown"}))
        self.assertEqual(installations.currentText(), "work")
