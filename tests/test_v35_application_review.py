"""Real Qt worker integration for separately approved application transactions."""
from __future__ import annotations

import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from core.actions.assurance import _preflight_application, _render_application_evidence, _verify_application
from core.actions.contracts import PolicyDecision
from core.catalog_models import FedoraVariant
from core.tasks.applications import ApplicationCatalog, ApplicationContext
from services.software.flatpak_installation import preview_from_facts
from services.software.flatpak_updates import update_digest
from ui.main_window_utility import MainWindowUtilityMixin
from ui.operation_worker import OperationControllerQtAdapter

APP = "app/org.example.Editor/x86_64/stable"
RUNTIME = "runtime/org.example.Platform/x86_64/stable"
COMMIT = "a" * 64
DEPENDENCY_COMMIT = "c" * 64


def install_facts():
    candidate = {"installation": "user", "ref": APP, "origin": "private", "installed_commit": "", "expected_commit": COMMIT,
                 "name": "Editor", "installed_version": "", "available_version": ""}
    operations = [{**candidate, "operation": "install", "selected": True},
                  {**candidate, "ref": RUNTIME, "expected_commit": DEPENDENCY_COMMIT, "operation": "install", "selected": False}]
    sources = "b" * 64
    return {"available": True, "evidence_version": 1, "installation": "user", "remote": "private", "ref": APP,
            "candidates": [candidate], "operations": operations, "source_digest": sources,
            "digest": update_digest("user", [candidate], operations, sources)}


class ReviewHost(MainWindowUtilityMixin, QWidget):
    """Real shared mixin/adapter wiring without the unrelated application shell."""
    def __init__(self, controller):
        QWidget.__init__(self)
        self._utility_operation_controller = controller
        self._utility_operation_adapter = None
        self.adapters = []
        self.notices = []
        self._record_global_operation_result = Mock()

    def _new_utility_operation_adapter(self, **_kwargs):
        adapter = OperationControllerQtAdapter(parent=self)
        self._utility_operation_adapter = adapter
        self.adapters.append(adapter)
        adapter.stopped.connect(lambda: self._utility_operation_adapter_stopped(adapter))
        return adapter

    def _set_utility_notice(self, _page, kind, title, message):
        self.notices.append((kind, title, message))

    def _set_review_notice(self, page, kind, title, message):
        self._set_utility_notice(page, kind, title, message)


class TestApplicationQueueIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.controller = Mock()
        self.tickets = []
        self.lifecycle = []

        def prepare(action, parameters):
            self.lifecycle.append(("prepare", parameters["package_id"]))
            ticket = SimpleNamespace(blocked=False, preview=("helper install-apply",), plan=SimpleNamespace(
                action_id=action, parameters=parameters, policy_decision=PolicyDecision(True, "ready", "Ready", facts={"flatpak_installation": install_facts()}),
                recovery_guidance="Review Activity.", risk_level="low", rollback_supported=False,
            ))
            self.tickets.append(ticket)
            return ticket

        def confirm(ticket, **_kwargs):
            self.lifecycle.append(("confirm", ticket.plan.parameters["package_id"]))
            return SimpleNamespace(status="prepared", ticket=ticket)

        def run(prepared):
            self.lifecycle.append(("run", prepared.ticket.plan.parameters["package_id"]))
            return SimpleNamespace(status="verifying", ticket=prepared.ticket)

        def verify(running):
            self.lifecycle.append(("verify", running.ticket.plan.parameters["package_id"]))
            return SimpleNamespace(status="succeeded", success=True, message="Verified", recovery_guidance="", plan_id="plan", run_id="run", correlation_id="correlation", data={})

        self.controller.prepare.side_effect = prepare
        self.controller.confirm.side_effect = confirm
        self.controller.run.side_effect = run
        self.controller.verify.side_effect = verify
        self.host = ReviewHost(self.controller)
        self.page = SimpleNamespace(set_results=Mock(), refresh_installed_applications=Mock())
        self.selection = ApplicationCatalog().build_selection(["firefox", "vlc"], context=ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"})))

    def tearDown(self):
        adapter = self.host._utility_operation_adapter
        if adapter is not None:
            adapter.close(2000)
        self.app.processEvents()
        self.host.deleteLater()
        self.app.processEvents()

    def wait_until(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            QTest.qWait(5)
        self.assertTrue(predicate(), "Qt worker workflow did not reach its terminal state")

    @patch("ui.confirm_dialog.ReviewedActionDialog")
    def test_same_ticket_is_confirmed_dependencies_visible_and_next_waits_for_verification(self, dialog_type):
        dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
        dialog_type.return_value.accepts_no_rollback = False
        self.assertTrue(self.host._start_utility_bundle(self.page, self.selection))
        self.wait_until(lambda: self.page.set_results.called and self.host._utility_operation_adapter is None)
        self.assertEqual(self.lifecycle, [(phase, app) for app in ("org.mozilla.firefox", "org.videolan.VLC") for phase in ("prepare", "confirm", "run", "verify")])
        for call, ticket in zip(self.controller.confirm.call_args_list, self.tickets):
            self.assertIs(call.args[0], ticket)
        for call in dialog_type.call_args_list:
            scope = call.args[2]
            self.assertIn(APP, scope)
            self.assertIn(RUNTIME, scope)
            self.assertIn(DEPENDENCY_COMMIT, scope)
            self.assertIn("private", scope)
        self.controller.execute_bundle.assert_not_called()
        self.assertTrue(self.page.set_results.call_args.args[0].success)
        self.assertEqual(self.page.refresh_installed_applications.call_count, 2)

    @patch("ui.confirm_dialog.ReviewedActionDialog")
    def test_declined_first_transaction_stops_queue_without_running(self, dialog_type):
        dialog_type.return_value.exec.return_value = QDialog.DialogCode.Rejected
        self.assertTrue(self.host._start_utility_bundle(self.page, self.selection))
        self.wait_until(lambda: self.page.set_results.called and self.host._utility_operation_adapter is None)
        self.assertEqual(self.controller.prepare.call_count, 1)
        self.controller.confirm.assert_not_called()
        self.controller.run.assert_not_called()
        self.assertTrue(all(item.skipped for item in self.page.set_results.call_args.args[0].items))

    @patch("ui.confirm_dialog.ReviewedActionDialog")
    def test_prepare_failure_stops_queue_and_releases_qthread(self, dialog_type):
        self.controller.prepare.side_effect = ValueError("metadata unavailable")
        self.assertTrue(self.host._start_utility_bundle(self.page, self.selection))
        self.wait_until(lambda: self.page.set_results.called and self.host._utility_operation_adapter is None)
        self.assertEqual(self.controller.prepare.call_count, 1)
        self.controller.confirm.assert_not_called()
        dialog_type.assert_not_called()
        self.assertIsNone(self.host._application_review_state)

    @patch("ui.operation_worker.OperationWorker._run_operation", return_value=("cancelled", None))
    def test_prepare_worker_cancellation_stops_queue(self, _operation):
        self.assertTrue(self.host._start_utility_bundle(self.page, self.selection))
        self.wait_until(lambda: self.host._utility_operation_adapter is None)
        self.assertIsNone(self.host._application_review_state)
        self.assertTrue(self.page.set_results.called)
        self.controller.confirm.assert_not_called()

    @patch("ui.confirm_dialog.ReviewedActionDialog")
    def test_setup_progress_write_failure_before_review_stops_queue(self, dialog_type):
        self.page.on_application_review_started = Mock(return_value=False)

        self.assertFalse(self.host._start_utility_bundle(self.page, self.selection))
        self.assertTrue(self.page.set_results.called)
        self.wait_until(lambda: self.page.set_results.called and self.host._utility_operation_adapter is None)

        self.controller.prepare.assert_not_called()
        self.controller.confirm.assert_not_called()
        dialog_type.assert_not_called()

    @patch("ui.confirm_dialog.ReviewedActionDialog")
    def test_setup_plan_reference_write_failure_prevents_approval(self, dialog_type):
        dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
        self.page.on_setup_action_prepared = Mock(return_value=False)

        self.assertTrue(self.host._start_utility_bundle(self.page, self.selection))
        self.wait_until(lambda: self.page.set_results.called and self.host._utility_operation_adapter is None)

        self.assertEqual(self.controller.prepare.call_count, 1)
        self.controller.confirm.assert_not_called()
        self.controller.run.assert_not_called()
        dialog_type.assert_not_called()

    @patch("ui.confirm_dialog.ReviewedActionDialog")
    def test_mutation_is_not_started_until_review_worker_stops(self, dialog_type):
        dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
        dialog_type.return_value.accepts_no_rollback = False
        review_adapter = SimpleNamespace(stopped=Mock())
        ticket = self.controller.prepare("install-application", {"source": "flatpak", "package_id": APP})
        self.host._show_health_review(self.page, ticket, review_adapter)
        self.controller.confirm.assert_not_called()
        review_adapter.stopped.connect.assert_called_once()


class TestFlatpakAssuranceIntegration(unittest.TestCase):
    def test_full_ref_preflight_and_render_preserve_reviewed_dependency_digest(self):
        parameters = {"source": "flatpak", "package_id": APP, "installation": "user", "remote": "private"}
        runtime = Mock()
        runtime.execute_read_only.return_value = SimpleNamespace(success=True, stdout=json.dumps(install_facts()))
        decision = _preflight_application(parameters, runtime, installing=True)
        self.assertTrue(decision.allowed)
        snapshot = preview_from_facts(decision.facts["flatpak_installation"])
        self.assertEqual(len(snapshot.operations), 2)
        vector = _render_application_evidence(parameters, runtime, decision, installing=True)
        self.assertEqual(vector, snapshot.apply_vector())
        self.assertEqual(runtime.execute_read_only.call_count, 1)
        self.assertIn("install-preview", runtime.execute_read_only.call_args.args[0])

    def test_legacy_install_plan_never_verifies_from_exit_code(self):
        plan = SimpleNamespace(parameters={"source": "flatpak", "package_id": APP}, policy_decision=PolicyDecision(True, "legacy", "Legacy"))
        result = _verify_application(SimpleNamespace(), plan, Mock(), installing=True)
        self.assertEqual(result.state, "failed")

    def test_verifier_reads_every_exact_installed_commit_including_dependency(self):
        from core.actions.contracts import ActionPlan
        facts = install_facts()
        plan = ActionPlan(plan_id="plan", target="44", digest="d" * 64, preview=[], risk_level="low", privileged=False, confirmation_policy="explicit", recovery_guidance="Review", rollback_supported=False,
                          action_id="install-application", parameters={"source": "flatpak", "package_id": APP},
                          policy_decision=PolicyDecision(True, "ready", "Ready", facts={"flatpak_installation": facts}))
        runtime = Mock()
        runtime.execute_read_only.side_effect = lambda vector, **_kw: SimpleNamespace(success=True, stdout=json.dumps({"available": True, "installation": "user", "ref": vector[5], "commit": COMMIT if vector[5] == APP else DEPENDENCY_COMMIT, "origin": "private"}))
        result = _verify_application(SimpleNamespace(), plan, runtime, installing=True)
        self.assertEqual(result.state, "succeeded")
        self.assertEqual({call.args[0][5] for call in runtime.execute_read_only.call_args_list}, {APP, RUNTIME})
