"""Safe RPM diagnostics and exact prerelease/postrelease version evidence."""
import json
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from core.actions import ActionRun
from core.executor.action_result import ActionResult
from services.software.rpm_transaction_helper import _error_code, main
from services.software.rpm_transactions import (
    ERROR_MESSAGES, RpmTransactionService, evidence_digest, parse_args, preview_from_facts,
    request_args, verify_preview,
)
from test_action_center_v14 import OrchestratorFixture
from test_rpm_transactions import preview


class RpmSafeDiagnosticsTests(unittest.TestCase):
    def test_private_backend_failures_map_to_closed_actionable_codes(self):
        failures = (
            (ImportError("private dependency path"), "backend_unavailable"),
            (TimeoutError("private timeout detail"), "operation_timeout"),
            (OSError("No space left on device"), "no_space"),
            (RuntimeError("NOT ENOUGH SPACE for transaction"), "no_space"),
            (RuntimeError("insufficient space in /private"), "no_space"),
            (RuntimeError("Another operation holds the system repository lock"), "package_lock"),
            (RuntimeError("lock is held by private process"), "package_lock"),
            (RuntimeError("failed to obtain lock"), "package_lock"),
            (ValueError("Package signature missing at private URL"), "signature_error"),
            (RuntimeError("GPG check failed"), "signature_error"),
            (ValueError("Package state or sources changed. Create a fresh review."), "transaction_drift"),
            (ValueError("The transaction would remove a protected system component"), "protected_package"),
            (RuntimeError("Could not resolve private host"), "network_error"),
            (OSError("Network is unreachable"), "network_error"),
            (RuntimeError("Connection timed out"), "network_error"),
            (RuntimeError("Curl error at private source"), "network_error"),
            (ValueError("unrecognized private backend error"), "rpm_transaction_unavailable"),
        )
        for error, expected in failures:
            with self.subTest(error=str(error)):
                self.assertEqual(_error_code(error), expected)
                self.assertIn(expected, ERROR_MESSAGES)

    @patch("services.software.rpm_transaction_helper.signal.alarm")
    @patch("services.software.rpm_transaction_helper.signal.signal")
    @patch("services.software.rpm_transaction_helper.RpmSession")
    @patch("builtins.print")
    def test_helper_emits_only_safe_messages_for_each_failure_category(self, output, session_class, _signal, _alarm):
        errors = (
            ImportError("private module"), TimeoutError("private timeout"), OSError("No space left on private disk"),
            RuntimeError("lock is held by private process"), ValueError("signature check failed for private URL"),
            ValueError("Sources changed. Create a fresh review. private token"),
            ValueError("protected system component private path"), RuntimeError("curl error private source"),
            AttributeError("private API details"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                session_class.return_value.resolve.side_effect = error
                self.assertEqual(main(["preview", *request_args("install", ("fixture",))]), 1)
                payload = json.loads(output.call_args.args[0])
                self.assertEqual(payload, {"available": False, "error_code": _error_code(error), "error": ERROR_MESSAGES[_error_code(error)]})
                self.assertNotIn("private", output.call_args.args[0])

    @patch("services.software.rpm_transactions.helper_command", return_value="/usr/bin/loofi-rpm-transaction")
    def test_service_uses_safe_catalog_messages_for_nonzero_and_unavailable_helper(self, _helper):
        runtime = Mock()
        for success in (False, True):
            for code, safe_message in ERROR_MESSAGES.items():
                with self.subTest(success=success, code=code):
                    result = ActionResult(success, "private backend message", stdout=json.dumps(
                        {"available": False, "error_code": code, "error": "private upstream exception"}))
                    runtime.execute_read_only.return_value = result
                    observed = RpmTransactionService(runtime).preview("install", ("fixture",))
                    self.assertFalse(observed.available)
                    self.assertEqual(observed.error, safe_message)
                    self.assertNotIn("private", observed.error)

    @patch("services.software.rpm_transactions.helper_command", return_value="/usr/bin/loofi-rpm-transaction")
    def test_service_ignores_unrecognized_messages_and_prefers_complete_structured_output(self, _helper):
        runtime = Mock()
        for code in ("arbitrary_upstream_code", None):
            result = ActionResult.fail("private message", stdout=json.dumps({"error_code": code, "error": "private diagnostic"}))
            runtime.execute_read_only.return_value = result
            self.assertEqual(RpmTransactionService(runtime).preview("install", ("fixture",)).error,
                             ERROR_MESSAGES["rpm_transaction_unavailable"])
        result = ActionResult.fail("truncated", stdout="not valid JSON")
        result.structured_output = json.dumps({"available": False, "error_code": "package_lock"})
        runtime.execute_read_only.return_value = result
        self.assertEqual(RpmTransactionService(runtime).preview("install", ("fixture",)).error, ERROR_MESSAGES["package_lock"])


class RpmVersionEvidenceTests(unittest.TestCase):
    def test_prerelease_and_snapshot_evr_roundtrip_through_review_and_verification(self):
        for version in ("2.0~rc1", "2.0^20261019git", "2.0~rc1^snapshot"):
            with self.subTest(version=version):
                nevra = f"fixture-0:{version}-1.noarch"
                base = preview()
                operation = {**base.operations[0], "nevra": nevra}
                snapshot = replace(base, packages=(nevra,), operations=(operation,),
                                   installed=("unrelated-0:1~beta1-1.noarch",))
                snapshot = replace(snapshot, digest=evidence_digest(snapshot.to_dict()))
                self.assertEqual(preview_from_facts(snapshot.to_dict()), snapshot)
                self.assertEqual(parse_args(snapshot.apply_vector()[1:])[2], (nevra,))
                runtime = Mock()
                runtime.execute_read_only.return_value = ActionResult.ok("inventory", stdout=(
                    f"fixture|{nevra}\nunrelated|unrelated-0:1~beta1-1.noarch\n"))
                self.assertEqual(verify_preview(snapshot, runtime).state, "succeeded")
                runtime.execute_read_only.return_value = ActionResult.ok("inventory", stdout=(
                    "fixture|fixture-0:2.0-1.noarch\nunrelated|unrelated-0:1~beta1-1.noarch\n"))
                self.assertEqual(verify_preview(snapshot, runtime).state, "failed")

    def test_evr_support_does_not_allow_paths_shell_expressions_or_globs(self):
        for token in ("fixture~rc1*", "fixture^snapshot/other", "fixture~$(id)", "fixture^snapshot;id", "fixture~rc1\n"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                request_args("install", (token,))


class RpmRecordedErrorTests(OrchestratorFixture):
    def save_running_application(self):
        run = ActionRun("exact-failed-application", "recorded-plan", "install-application", "recorded-correlation")
        self.run_store.save(run)
        self.orchestrator._held_leases[run.run_id] = self.orchestrator._acquire_lease()
        return run

    def test_closed_backend_code_and_safe_message_are_persisted_for_activity(self):
        for code, message in ERROR_MESSAGES.items():
            with self.subTest(code=code):
                run = self.save_running_application()
                result = ActionResult.fail("backend failed", stdout=json.dumps({"available": False, "error_code": code}),
                                           data={"existing_evidence": "preserved"})
                observed = self.orchestrator.complete_run(run.run_id, result)
                self.assertEqual(observed.state, "failed")
                self.assertEqual(observed.execution_result["message"], message)
                self.assertEqual(observed.execution_result["data"], {"error_code": code, "existing_evidence": "preserved"})
                self.assertEqual(self.run_store.get(run.run_id).execution_result, observed.execution_result)
                self.assertNotIn(run.run_id, self.orchestrator._held_leases)
                self.facade.execute.assert_not_called()

    def test_malformed_and_unknown_payloads_do_not_inject_error_codes(self):
        for stdout in ("not json", "[]", "null", '{"error_code":"untrusted"}', '{"error_code":[]}'):
            with self.subTest(stdout=stdout):
                run = self.save_running_application()
                observed = self.orchestrator.complete_run(run.run_id, ActionResult.fail("Recorded failure", stdout=stdout))
                self.assertEqual(observed.state, "failed")
                self.assertNotIn("error_code", observed.execution_result.get("data") or {})
                self.assertEqual(observed.execution_result["message"], "Recorded failure")
                self.assertNotIn(run.run_id, self.orchestrator._held_leases)
