"""v30 lifecycle regression coverage for the shared operation controller."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from PyQt6.QtCore import QEvent, QEventLoop, QObject, QThread, QTimer, Qt
from PyQt6.QtWidgets import QApplication

from core.actions import ActionCatalog, ActionCenterOrchestrator, ActionPlanStore, ActionRunStore
from core.actions.bundles import ActionBundle
from core.actions.contracts import ActionDefinition, PolicyDecision, VerificationDecision
from core.actions.operation_controller import (
    OperationController,
    OperationControllerError,
    OperationEvent,
    OperationNotPreparedError,
    OperationOutcome,
)
from core.executor.action_result import ActionResult
from ui.main_window_interactions import MainWindowInteractionMixin
from ui.operation_worker import OperationControllerQtAdapter, OperationWorker


class _Runtime:
    def __init__(self) -> None:
        self.boot = "boot-a"
        self.allowed = True
        self.verifier = None

    def is_atomic(self) -> bool:
        return False

    def package_manager(self) -> str:
        return "dnf5"

    def fedora_version(self) -> str:
        return "44"

    def package_manager_busy(self) -> bool:
        return False

    def boot_id(self) -> str:
        return self.boot


class _ControllerFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.runtime = _Runtime()
        self.facade = MagicMock()
        self.facade.execute.return_value = ActionResult.ok("executed", exit_code=0)
        self.definition = ActionDefinition(
            id="controller-test",
            capability_id="test.controller",
            title="Controller test",
            description="Exercise the shared operation boundary.",
            parameter_schema={},
            risk_level="low",
            privileged=False,
            confirmation_policy="explicit",
            recovery_guidance="Review the saved operation result before continuing.",
            rollback_supported=True,
            command_renderer=lambda _parameters, _runtime: ["dnf5", "clean", "all"],
            preflight_checker=lambda _parameters, runtime: PolicyDecision(
                runtime.allowed,
                "preflight_ok" if runtime.allowed else "tool_missing",
                "Ready." if runtime.allowed else "Required tool is unavailable.",
            ),
            verifier=lambda run, plan, runtime: runtime.verifier(run, plan, runtime)
            if runtime.verifier
            else VerificationDecision.succeeded("Verified."),
            supported_variants=frozenset({"traditional"}),
            affected_resources=("packages:test",),
        )
        self.ids = iter(f"operation-{index}" for index in range(1000))
        self.orchestrator = ActionCenterOrchestrator(
            facade=self.facade,
            catalog=ActionCatalog([self.definition]),
            plan_store=ActionPlanStore(root / "plans.json"),
            run_store=ActionRunStore(root / "runs.jsonl"),
            lease_path=root / "lease",
            runtime=self.runtime,
            id_factory=lambda: next(self.ids),
        )
        self.controller = OperationController(orchestrator=self.orchestrator, facade=self.facade)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _success_executor(self, command, **kwargs):
        self.assertEqual(command, ("dnf5", "clean", "all"))
        self.assertEqual(kwargs["authority"], "action_center")
        return ActionResult.ok("executed", exit_code=0, action_id="controller-test")


class TestOperationControllerLifecycle(_ControllerFixture):
    def test_prepare_and_confirmation_do_not_execute_before_explicit_acceptance(self) -> None:
        ticket = self.controller.prepare("controller-test")
        self.assertTrue(ticket.confirmation_required)
        self.assertEqual(ticket.phase, "prepare")
        self.assertEqual(ticket.preview, ("dnf5", "clean", "all"))
        self.assertEqual(ticket.to_dict()["events"][0]["phase"], "prepare")

        declined = self.controller.confirm(ticket.plan)
        self.assertEqual(declined.status, "confirmation_required")
        self.assertTrue(declined.awaiting_confirmation)
        self.assertFalse(declined.terminal)
        self.assertEqual(declined.data["reason_code"], "confirmation_required")
        self.facade.execute.assert_not_called()

        accepted = self.controller.confirm(declined, confirmed=True)
        self.assertEqual(accepted.status, "prepared")
        self.assertIsNotNone(accepted.prepared)
        self.assertEqual(accepted.to_dict()["schema"], "loofi.operation-outcome/v1")
        reviewed = accepted.with_event(OperationEvent("verify", "verifying", "Checking."))
        self.assertEqual(reviewed.events[-1].phase, "verify")
        self.assertEqual(OperationEvent("prepare", "prepared", "Ready.", data={"count": 1}).to_dict()["data"], {"count": 1})
        self.controller.complete(
            accepted,
            ActionResult.fail("Test ended before execution.", exit_code=1, action_id="controller-test"),
        )

    def test_confirmation_revalidates_stale_plan_and_reports_new_block(self) -> None:
        ticket = self.controller.prepare("controller-test")
        self.runtime.allowed = False

        outcome = self.controller.confirm(ticket, confirmed=True)

        self.assertEqual(outcome.status, "blocked")
        self.assertEqual(outcome.data["reason_code"], "system_drift")
        self.assertTrue(outcome.terminal)

    def test_confirmation_handles_policy_and_storage_failures(self) -> None:
        self.runtime.allowed = False
        blocked_ticket = self.controller.prepare("controller-test")
        self.assertTrue(blocked_ticket.blocked)
        self.assertEqual(self.controller.confirm(blocked_ticket, confirmed=True).status, "blocked")

        self.runtime.allowed = True
        ticket = self.controller.prepare("controller-test")
        with patch.object(self.orchestrator, "prepare_run", side_effect=OSError("lease store unavailable")):
            outcome = self.controller.confirm(ticket, confirmed=True)
        self.assertEqual(outcome.status, "blocked")
        self.assertIn("lease store unavailable", outcome.message)

    def test_medium_risk_action_requires_explicit_no_rollback_acceptance(self) -> None:
        self.orchestrator.catalog = ActionCatalog(
            [replace(self.definition, risk_level="medium", rollback_supported=False)]
        )
        ticket = self.controller.prepare("controller-test")

        declined = self.controller.confirm(ticket, confirmed=True)
        self.assertEqual(declined.status, "confirmation_required")
        self.assertEqual(declined.data["reason_code"], "no_rollback_acceptance_required")

        accepted = self.controller.confirm(ticket, confirmed=True, accept_no_rollback=True)
        self.assertEqual(accepted.status, "prepared")
        self.controller.complete(
            accepted,
            ActionResult.fail("Test ended before execution.", exit_code=1, action_id="controller-test"),
        )

    def test_event_sink_errors_never_change_the_operation_result(self) -> None:
        controller = OperationController(
            orchestrator=self.orchestrator,
            facade=self.facade,
            event_sink=lambda _event: (_ for _ in ()).throw(RuntimeError("closed presentation sink")),
        )

        outcome = controller.execute("controller-test", confirmed=True, executor=self._success_executor)

        self.assertEqual(outcome.status, "succeeded")
        self.assertEqual(controller.last_event.status, "succeeded")

    def test_full_run_records_execution_and_verification(self) -> None:
        outcome = self.controller.execute(
            "controller-test",
            confirmed=True,
            executor=self._success_executor,
        )

        self.assertEqual(outcome.status, "succeeded")
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.run.state, "succeeded")
        self.assertEqual(outcome.run.verification_attempts, 1)
        self.assertEqual(outcome.data["execution_result"]["message"], "executed")

    def test_timeout_exception_is_saved_as_failed_run_with_recovery_guidance(self) -> None:
        outcome = self.controller.execute(
            "controller-test",
            confirmed=True,
            executor=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                subprocess.TimeoutExpired(["dnf5", "clean", "all"], 1)
            ),
        )

        self.assertEqual(outcome.status, "failed")
        self.assertTrue(outcome.recovery_required)
        self.assertEqual(outcome.run.state, "failed")
        self.assertIn("timed out", outcome.result.message.casefold())
        self.assertEqual(self.orchestrator.get_run(outcome.run_id).state, "failed")

    def test_malformed_executor_response_fails_closed_and_is_durable(self) -> None:
        outcome = self.controller.execute(
            "controller-test",
            confirmed=True,
            executor=lambda *_args, **_kwargs: {"success": True},
        )

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.run.state, "failed")
        self.assertFalse(outcome.result.success)
        self.assertIn("invalid result", outcome.result.message.casefold())

    def test_preflight_missing_tool_blocks_without_creating_a_run(self) -> None:
        self.runtime.allowed = False
        outcome = self.controller.execute("controller-test", confirmed=True, executor=self._success_executor)

        self.assertEqual(outcome.status, "blocked")
        self.assertEqual(outcome.data["reason_code"], "tool_missing")
        self.assertEqual(self.orchestrator.run_store.list(), [])

    def test_unknown_action_and_unprepared_run_return_typed_failures(self) -> None:
        blocked = self.controller.execute("missing-action", confirmed=True, executor=self._success_executor)
        self.assertEqual(blocked.status, "blocked")
        self.assertEqual(blocked.data["reason_code"], "manual_only")

        with self.assertRaises(OperationNotPreparedError):
            self.controller.run(self.controller.prepare("controller-test"))

        with self.assertRaises(OperationControllerError):
            self.controller.verify("")

    def test_verification_failure_is_saved_and_never_reported_as_success(self) -> None:
        self.runtime.verifier = lambda *_args: (_ for _ in ()).throw(ValueError("malformed verifier response"))
        outcome = self.controller.execute(
            "controller-test",
            confirmed=True,
            executor=self._success_executor,
        )

        saved = self.orchestrator.get_run(outcome.run_id)
        self.assertEqual(outcome.status, "verification_failed")
        self.assertEqual(outcome.run.state, "verification_failed")
        self.assertEqual(saved.state, "verification_failed")
        self.assertIn("malformed verifier response", saved.verification_result["message"])

    def test_reboot_verification_waits_then_resumes_saved_run(self) -> None:
        self.runtime.verifier = lambda run, _plan, runtime: (
            VerificationDecision.awaiting_reboot("Reboot before verification can finish.", expected_boot="boot-b")
            if runtime.boot == run.execution_boot_id
            else VerificationDecision.succeeded("New boot verified.")
        )
        running = self.controller.execute(
            "controller-test",
            confirmed=True,
            executor=self._success_executor,
            auto_verify=False,
        )
        waiting = self.controller.verify(running)
        self.assertEqual(waiting.status, "awaiting_reboot")
        self.assertTrue(waiting.needs_reboot)
        self.assertEqual(self.orchestrator.get_run(waiting.run_id).state, "awaiting_reboot")

        self.runtime.boot = "boot-b"
        resumed = self.controller.verify(waiting.run_id)
        self.assertEqual(resumed.status, "succeeded")
        self.assertEqual(resumed.run.verification_attempts, 2)

    def test_recovery_interrupts_saved_work_without_retry_or_rollback(self) -> None:
        verifying = self.controller.execute(
            "controller-test",
            confirmed=True,
            executor=self._success_executor,
            auto_verify=False,
        )
        outcome = self.controller.recover(verifying, reason="window-shutdown-requested")

        self.assertEqual(outcome.status, "recovery_required")
        self.assertEqual(self.orchestrator.get_run(verifying.run_id).state, "interrupted")
        self.assertEqual(outcome.data["automatic_action"], "none")
        self.assertEqual(outcome.data["reason"], "window-shutdown-requested")
        saved = self.orchestrator.get_run(verifying.run_id)
        self.assertEqual(self.controller.recover(saved).status, "recovery_required")
        self.assertEqual(self.controller.recover(saved.run_id).status, "recovery_required")

    def test_recovery_requires_a_saved_run_identifier(self) -> None:
        with self.assertRaises(OperationControllerError):
            self.controller.recover("")

    def test_failed_run_commit_reports_the_saved_nonterminal_state(self) -> None:
        ticket = self.controller.prepare("controller-test")
        prepared = self.controller.confirm(ticket, confirmed=True)
        assert prepared.prepared is not None

        def fail_after_releasing(run_id, _result):
            self.orchestrator._release_lease(run_id)
            raise OSError("state store unavailable")

        with patch.object(self.orchestrator, "complete_run", side_effect=fail_after_releasing):
            outcome = self.controller.run(prepared, executor=self._success_executor)

        self.assertEqual(self.orchestrator.get_run(prepared.run_id).state, "running")
        self.assertEqual(outcome.status, "running")
        self.assertIn("saved run remains running", outcome.message)

    def test_complete_never_reports_failure_when_success_state_was_already_saved(self) -> None:
        prepared = self.controller.confirm(self.controller.prepare("controller-test"), confirmed=True)
        assert prepared.prepared is not None
        complete_run = self.orchestrator.complete_run

        def save_then_lose_ack(run_id, result):
            complete_run(run_id, result)
            raise OSError("acknowledgement lost after durable save")

        with patch.object(self.orchestrator, "complete_run", side_effect=save_then_lose_ack):
            outcome = self.controller.complete(
                prepared,
                ActionResult.ok("saved successfully", exit_code=0, action_id="controller-test"),
            )

        self.assertEqual(self.orchestrator.get_run(prepared.run_id).state, "verifying")
        self.assertEqual(outcome.status, "verifying")
        self.assertIn("saved run remains verifying", outcome.message)

    def test_verification_storage_failure_preserves_saved_verifying_state(self) -> None:
        self.runtime.verifier = lambda *_args: (_ for _ in ()).throw(RuntimeError("verifier unavailable"))
        running = self.controller.execute(
            "controller-test",
            confirmed=True,
            executor=self._success_executor,
            auto_verify=False,
        )
        with patch.object(self.orchestrator, "complete_verification", side_effect=OSError("verification store read-only")):
            outcome = self.controller.verify(running)

        self.assertEqual(self.orchestrator.get_run(running.run_id).state, "verifying")
        self.assertEqual(outcome.status, "verifying")
        self.assertIn("saved run remains verifying", outcome.message)

    def test_complete_path_and_unreadable_saved_state_are_reported_truthfully(self) -> None:
        prepared = self.controller.confirm(self.controller.prepare("controller-test"), confirmed=True)
        result = ActionResult.ok("worker completed", exit_code=0, action_id="controller-test")
        completed = self.controller.complete(prepared, result)
        self.assertEqual(completed.status, "verifying")
        self.assertEqual(completed.run.state, "verifying")

        next_prepared = self.controller.confirm(self.controller.prepare("controller-test"), confirmed=True)
        assert next_prepared.prepared is not None
        self.orchestrator._release_lease(next_prepared.run_id)
        with patch.object(self.orchestrator, "get_run", side_effect=OSError("state file unreadable")):
            outcome = self.controller.complete(next_prepared, result)
        self.assertEqual(outcome.status, "interrupted")
        self.assertIn("could not be confirmed", outcome.message)


class TestOperationControllerBundles(_ControllerFixture):
    def test_install_batch_keeps_each_item_result_and_continues_after_timeout(self) -> None:
        bundle = ActionBundle.applications(("controller-test", "controller-test", "controller-test"))
        executed: list[str] = []

        def execute_item(item):
            executed.append(item.item_id)
            if item.position == 1:
                raise subprocess.TimeoutExpired(["dnf5", "install"], 5)
            return ActionResult.ok(f"item {item.position} verified")

        outcome = self.controller.execute_bundle(bundle, item_executor=execute_item)

        self.assertEqual(executed, ["item-1", "item-2", "item-3"])
        self.assertEqual(outcome.status, "partial_failure")
        self.assertEqual([item.status for item in outcome.items], ["succeeded", "failed", "succeeded"])
        self.assertIn("timed out", outcome.items[1].message.casefold())

    def test_tune_profile_stops_at_failure_and_marks_remaining_items_skipped(self) -> None:
        bundle = ActionBundle.tune_profile(("controller-test", "controller-test", "controller-test"))
        executed: list[int] = []

        def execute_item(item):
            executed.append(item.position)
            if item.position == 1:
                return ActionResult.fail("Profile step failed", exit_code=2)
            return ActionResult.ok("Profile step verified")

        outcome = self.controller.execute_bundle(bundle, item_executor=execute_item)

        self.assertEqual(executed, [0, 1])
        self.assertEqual(outcome.status, "partial_failure")
        self.assertEqual([item.status for item in outcome.items], ["succeeded", "failed", "skipped"])
        self.assertTrue(outcome.items[2].skipped)

    def test_unknown_bundle_action_is_blocked_before_item_execution(self) -> None:
        bundle = ActionBundle.tune_profile(("not-in-catalog",))
        called: list[bool] = []

        outcome = self.controller.execute_bundle(bundle, item_executor=lambda _item: called.append(True))

        self.assertEqual(outcome.status, "blocked")
        self.assertEqual(called, [])

    def test_invalid_bundle_executor_response_becomes_item_failure(self) -> None:
        bundle = ActionBundle.applications(("controller-test",))
        outcome = self.controller.execute_bundle(bundle, item_executor=lambda _item: object())
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.items[0].status, "failed")
        self.assertIn("invalid result", outcome.items[0].message.casefold())

    def test_bundle_outcome_accepts_typed_operation_results_and_all_success(self) -> None:
        bundle = ActionBundle.applications(("controller-test",))
        typed = OperationOutcome(
            action_id="controller-test",
            status="verified",
            phase="verify",
            message="Verified typed result.",
            run_id="saved-run",
            data={"source": "system"},
        )

        result = self.controller.execute_bundle(bundle, item_executor=lambda _item: typed)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.items[0].run_id, "saved-run")

        all_failed = self.controller.execute_bundle(
            ActionBundle.applications(("controller-test", "controller-test")),
            item_executor=lambda _item: ActionResult.fail("Not applied", exit_code=1),
        )
        self.assertEqual(all_failed.status, "failed")


class TestOperationControllerQtAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _wait_for_stopped(self, adapter: OperationControllerQtAdapter) -> None:
        loop = QEventLoop()
        timer = QTimer()
        stopped: list[bool] = []
        on_stopped = lambda: stopped.append(True)
        timer.setSingleShot(True)
        adapter.stopped.connect(loop.quit)
        adapter.stopped.connect(on_stopped)
        timer.timeout.connect(loop.quit)
        timer.start(3000)
        loop.exec()
        timer.stop()
        adapter.stopped.disconnect(loop.quit)
        adapter.stopped.disconnect(on_stopped)
        self.assertTrue(stopped, "operation thread did not stop before timeout")
        self.assertFalse(adapter.running)

    def test_worker_cancellation_before_execution_skips_callback(self) -> None:
        called: list[bool] = []
        worker = OperationWorker(lambda: called.append(True))
        worker.cancel()
        worker.run()

        self.assertTrue(worker.cancel_requested)
        self.assertEqual(called, [])

    def test_worker_failure_is_emitted_as_a_clear_terminal_error(self) -> None:
        worker = OperationWorker(lambda: (_ for _ in ()).throw(ValueError("bad worker response")))
        failures: list[str] = []
        worker.failed.connect(failures.append)
        worker.run()
        self.assertEqual(failures, ["ValueError: bad worker response"])

    def test_overlap_is_rejected_and_late_cancel_keeps_completed_result(self) -> None:
        parent = QObject()
        adapter = OperationControllerQtAdapter(parent=parent)
        entered = threading.Event()
        release = threading.Event()
        finished: list[object] = []
        adapter.finished.connect(finished.append)

        def operation():
            entered.set()
            release.wait(2)
            return {"saved_run": "run-1", "status": "succeeded"}

        progress: list[object] = []
        adapter.progress.connect(progress.append)
        self.assertTrue(adapter.start(operation))
        self.assertTrue(entered.wait(1))
        self.assertFalse(adapter.start(lambda: "overlap"))
        adapter._worker.progress.emit({"phase": "verify"})
        self.assertTrue(adapter.cancel())
        release.set()
        self._wait_for_stopped(adapter)

        self.assertEqual(finished, [{"saved_run": "run-1", "status": "succeeded"}])
        self.assertEqual(progress, [{"phase": "verify"}])
        self.assertIsNone(adapter._thread)
        self.assertIsNone(adapter._worker)
        parent.deleteLater()
        self.app.processEvents()

    def test_worker_exception_reaches_adapter_failure_signal(self) -> None:
        adapter = OperationControllerQtAdapter()
        failures: list[str] = []
        adapter.failed.connect(failures.append)
        self.assertTrue(adapter.start(lambda: (_ for _ in ()).throw(RuntimeError("operation failed"))))
        self._wait_for_stopped(adapter)
        self.assertEqual(failures, ["RuntimeError: operation failed"])
        adapter.deleteLater()
        self.app.processEvents()

    def test_adapter_stays_busy_until_queued_terminal_delivery(self) -> None:
        adapter = OperationControllerQtAdapter()
        finished: list[object] = []
        entered = threading.Event()
        release = threading.Event()
        thread_finished = threading.Event()
        adapter.finished.connect(finished.append)

        def operation():
            entered.set()
            release.wait(2)
            return "saved"

        self.assertTrue(adapter.start(operation))
        self.assertTrue(entered.wait(1))
        thread = adapter._thread
        self.assertIsNotNone(thread)
        thread.finished.connect(thread_finished.set, Qt.ConnectionType.DirectConnection)
        release.set()
        self.assertTrue(thread_finished.wait(2), "worker QThread did not finish")

        self.assertFalse(adapter.running)
        self.assertTrue(adapter.busy)
        self.assertEqual(finished, [])

        self.app.processEvents()

        self.assertFalse(adapter.busy)
        self.assertEqual(finished, ["saved"])
        adapter.deleteLater()
        self.app.processEvents()

    def test_thirty_worker_cycles_release_qthreads_and_owned_objects(self) -> None:
        parent = QObject()
        adapter = OperationControllerQtAdapter(parent=parent)
        owned_counts: list[int] = []

        for index in range(30):
            finished: list[object] = []
            on_finished = lambda value: finished.append(value)
            adapter.finished.connect(on_finished)
            self.assertTrue(adapter.start(lambda selected=index: selected))
            self._wait_for_stopped(adapter)
            self.assertEqual(finished, [index])
            adapter.finished.disconnect(on_finished)
            self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.app.processEvents()
            self.assertEqual(parent.findChildren(QThread), [])
            owned_counts.append(len(parent.findChildren(QObject)))

        self.assertEqual(len(set(owned_counts)), 1)
        self.assertEqual(owned_counts[-1], 1)
        adapter.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.assertEqual(parent.findChildren(QObject), [])
        parent.deleteLater()


class _ShutdownHarness(MainWindowInteractionMixin):
    def __init__(self, adapter) -> None:
        self._utility_operation_adapter = adapter
        self._pending_runtime_shutdown = None
        self._status_frame = None
        self._status_label = None
        self._runtime = None
        self._cleanup_runtime = MagicMock()
        self.close = MagicMock()
        self.tr = lambda message: message
        self.tray_icon = None


class TestOperationShutdownDeferral(unittest.TestCase):
    def test_close_waits_for_durable_operation_result_then_finishes_shutdown(self) -> None:
        adapter = SimpleNamespace(running=True, cancel=MagicMock())
        window = _ShutdownHarness(adapter)
        event = MagicMock()

        window.closeEvent(event)

        event.ignore.assert_called_once()
        event.accept.assert_not_called()
        adapter.cancel.assert_called_once()
        window._cleanup_runtime.assert_not_called()
        self.assertEqual(window._pending_runtime_shutdown, "close")

        adapter.running = False
        final_event = MagicMock()
        window.close.side_effect = lambda: MainWindowInteractionMixin.closeEvent(window, final_event)
        window._resume_deferred_runtime_shutdown()

        window._cleanup_runtime.assert_called_once_with(5.0)
        window.close.assert_called_once_with()
        final_event.accept.assert_called_once()
        self.assertIsNone(window._pending_runtime_shutdown)

    def test_quit_request_takes_precedence_over_a_deferred_close(self) -> None:
        adapter = SimpleNamespace(running=True, cancel=MagicMock())
        window = _ShutdownHarness(adapter)
        self.assertFalse(window._request_runtime_shutdown(action="close"))
        self.assertFalse(window._request_runtime_shutdown(action="quit"))
        self.assertFalse(window._request_runtime_shutdown(action="close"))
        self.assertEqual(window._pending_runtime_shutdown, "quit")

        adapter.running = False
        with patch.object(QApplication, "quit") as quit_app:
            window._resume_deferred_runtime_shutdown()

        quit_app.assert_called_once_with()
        window._cleanup_runtime.assert_called_once_with(5.0)
        window.close.assert_not_called()

    def test_shutdown_waits_for_result_delivery_after_thread_stops(self) -> None:
        adapter = SimpleNamespace(running=False, busy=True, cancel=MagicMock())
        window = _ShutdownHarness(adapter)

        self.assertFalse(window._request_runtime_shutdown(action="close"))

        window._cleanup_runtime.assert_not_called()
        self.assertEqual(window._pending_runtime_shutdown, "close")


if __name__ == "__main__":
    unittest.main()
