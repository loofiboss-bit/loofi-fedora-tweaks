"""Tests for v14 Helm's policy-backed Action Center core."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.actions import (
    ActionCatalog,
    ActionCenterBusyError,
    ActionCenterOrchestrator,
    ActionLifecycleError,
    ActionPlanIntegrityError,
    ActionPlanRejectedError,
    ActionPlanStore,
    ActionRun,
    ActionRunStore,
    ActionStoreVersionError,
    PolicyDecision,
)
from core.actions.contracts import ActionDefinition, ActionPlan, PLAN_TRANSITIONS, RUN_TRANSITIONS
from core.actions.catalog import SystemActionRuntime, validate_parameters
from core.actions.center import ActionCenterService
from core.executor.action_result import ActionResult


class FakeRuntime:
    def __init__(self):
        self.atomic = False
        self.manager = "dnf"
        self.host_version = "44"
        self.busy = False
        self.failed = ["broken.service"]
        self.failed_probe_success = True
        self.trim_supported = True
        self.read_results = {}

    def is_atomic(self):
        return self.atomic

    def package_manager(self):
        return self.manager

    def fedora_version(self):
        return self.host_version

    def package_manager_busy(self):
        return self.busy

    def failed_services(self):
        return self.failed_probe_success, list(self.failed), "probe failed" if not self.failed_probe_success else ""

    def fstrim_support(self):
        facts = {"fstrim_available": True, "discard_supported": self.trim_supported}
        return self.trim_supported, facts, "No discard support."

    def execute_read_only(self, vector, *, action_id, timeout=30):
        key = tuple(vector)
        if key in self.read_results:
            return self.read_results[key]
        if vector[:2] == ["systemctl", "is-active"]:
            return ActionResult.ok("active", stdout="active\n", exit_code=0, action_id=action_id)
        return ActionResult.ok("healthy", stdout="healthy\n", exit_code=0, action_id=action_id)


class OrchestratorFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.plan_store = ActionPlanStore(root / "plans.json")
        self.run_store = ActionRunStore(root / "runs.jsonl")
        self.lease_path = root / "mutation"
        self.runtime = FakeRuntime()
        self.facade = MagicMock()
        self.ids = iter(f"id-{index}" for index in range(100))
        self.now = 1000.0
        self.orchestrator = ActionCenterOrchestrator(
            facade=self.facade,
            plan_store=self.plan_store,
            run_store=self.run_store,
            lease_path=self.lease_path,
            runtime=self.runtime,
            clock=lambda: self.now,
            id_factory=lambda: next(self.ids),
        )

    def tearDown(self):
        for run_id in list(self.orchestrator._held_leases):
            self.orchestrator.interrupt_run(run_id, "test-cleanup")
        self.temp.cleanup()


class TestV14CatalogAndPlanning(OrchestratorFixture):
    def test_catalog_is_deny_by_default_and_has_only_audited_ids(self):
        catalog = ActionCatalog()

        self.assertEqual(
            [definition.id for definition in catalog.list()],
            [
                "autoremove-packages",
                "create-recovery-point",
                "dnf-clean-all",
                "fstrim-all",
                "install-application",
                "remove-application",
                "restart-failed-service",
                "update-fedora-system",
                "update-firmware",
                "update-flatpaks",
                "vacuum-journal",
            ],
        )
        self.assertFalse(catalog.denied("gaming-install-tools").allowed)
        self.assertEqual(catalog.denied("gaming-install-tools").reason_code, "manual_only")

    def test_plan_has_thirty_minute_expiry_and_no_pkexec_in_vector(self):
        plan = self.orchestrator.plan("dnf-clean-all")

        self.assertEqual(plan.state, "ready")
        self.assertEqual(plan.preview, ["dnf", "clean", "all"])
        self.assertNotIn("pkexec", plan.preview)
        self.assertEqual(plan.expires_at - plan.created_at, 1800)
        self.assertTrue(plan.privileged)

    def test_atomic_dnf_action_is_blocked_with_safe_alternative(self):
        self.runtime.atomic = True
        self.runtime.manager = "rpm-ostree"

        plan = self.orchestrator.plan("dnf-clean-all")

        self.assertEqual(plan.state, "blocked")
        self.assertEqual(plan.policy_decision.reason_code, "atomic_manual_only")
        self.assertIn("rpm-ostree", plan.policy_decision.alternative)

    def test_fedora_45_host_is_read_only_even_with_default_target(self):
        self.runtime.host_version = "45"

        plan = self.orchestrator.plan("dnf-clean-all")

        self.assertEqual(plan.state, "blocked")
        self.assertEqual(plan.policy_decision.reason_code, "host_preview_read_only")

    def test_package_busy_probe_covers_dnf_and_rpm_locks(self):
        facade = MagicMock()
        facade.execute.return_value = ActionResult.fail("idle", exit_code=1)
        runtime = SystemActionRuntime(facade)

        self.assertFalse(runtime.package_manager_busy())
        facade.execute.assert_called_once_with(
            [
                "fuser",
                "/var/lib/dnf/metadata_lock.pid",
                "/var/lib/dnf/lock",
                "/var/lib/rpm/.rpm.lock",
            ],
            privileged=False,
            timeout=10,
            action_id="action-center-preflight-package-lock",
        )
    def test_fedora_45_action_target_is_read_only_preview(self):
        plan = self.orchestrator.plan("dnf-clean-all", target="45-preview")

        self.assertEqual(plan.state, "blocked")
        self.assertEqual(plan.policy_decision.reason_code, "preview_target_read_only")
        self.assertEqual(plan.preview, ["dnf", "clean", "all"])

    def test_unknown_action_is_persisted_as_manual_only_block(self):
        plan = self.orchestrator.plan("plugin-free-form-command", {"command": "echo bad"})

        self.assertEqual(plan.state, "blocked")
        self.assertEqual(plan.preview, [])
        self.assertEqual(plan.policy_decision.reason_code, "manual_only")

    def test_package_manager_lock_blocks_dnf_action(self):
        self.runtime.busy = True

        plan = self.orchestrator.plan("dnf-clean-all")

        self.assertEqual(plan.state, "blocked")
        self.assertEqual(plan.policy_decision.reason_code, "package_manager_busy")


    def test_fstrim_without_discard_support_is_blocked(self):
        self.runtime.trim_supported = False

        plan = self.orchestrator.plan("fstrim-all")

        self.assertEqual(plan.state, "blocked")
        self.assertEqual(plan.policy_decision.reason_code, "fstrim_unsupported")

    def test_service_must_be_in_fresh_failed_list(self):
        plan = self.orchestrator.plan("restart-failed-service", {"service": "healthy.service"})

        self.assertEqual(plan.state, "blocked")
        self.assertEqual(plan.policy_decision.reason_code, "service_not_freshly_failed")

    def test_service_parameter_injection_is_rejected_before_preflight(self):
        plan = self.orchestrator.plan("restart-failed-service", {"service": "sshd; reboot"})

        self.assertEqual(plan.state, "blocked")
        self.assertEqual(plan.policy_decision.reason_code, "invalid_service_unit")
        self.assertEqual(plan.preview, [])

    def test_preview_regenerates_command_instead_of_trusting_persisted_vector(self):
        plan = self.orchestrator.plan("dnf-clean-all")
        self.facade.preview.return_value = ActionResult.previewed("dnf", ["clean", "all"])

        result = self.orchestrator.preview(plan.plan_id)

        self.assertTrue(result.preview)
        self.assertEqual(result.data["schema_version"], 2)
        self.facade.preview.assert_called_once_with(
            ["dnf", "clean", "all"], privileged=True, action_id="dnf-clean-all"
        )

    def test_tampered_persisted_plan_fails_digest_validation(self):
        plan = self.orchestrator.plan("dnf-clean-all")
        plan.parameters["injected"] = "value"
        self.plan_store.save(plan)

        with self.assertRaises(ActionPlanIntegrityError):
            self.orchestrator.prepare_run(plan.plan_id, confirmed=True)

    def test_catalog_definition_cannot_smuggle_pkexec_into_canonical_vector(self):
        definition = ActionDefinition(
            id="bad-wrapper",
            capability_id="test.bad-wrapper",
            title="Bad wrapper",
            description="Rejected test definition.",
            parameter_schema={},
            risk_level="low",
            privileged=True,
            confirmation_policy="explicit",
            recovery_guidance="None",
            rollback_supported=True,
            command_renderer=lambda _parameters, _runtime: ["pkexec", "dnf", "clean", "all"],
            preflight_checker=lambda _parameters, _runtime: PolicyDecision(True, "preflight_ok", "ok"),
            verifier=lambda _run, _plan, _runtime: ActionResult.ok("ok"),
        )
        catalog = ActionCatalog([definition])
        orchestrator = ActionCenterOrchestrator(
            facade=self.facade,
            catalog=catalog,
            plan_store=self.plan_store,
            run_store=self.run_store,
            lease_path=self.lease_path,
            runtime=self.runtime,
            id_factory=lambda: next(self.ids),
        )

        plan = orchestrator.plan("bad-wrapper")

        self.assertEqual(plan.state, "blocked")
        self.assertEqual(plan.policy_decision.reason_code, "command_policy_rejected")


class TestSystemActionRuntime(unittest.TestCase):
    def setUp(self):
        self.facade = MagicMock()
        self.system_manager = MagicMock()
        self.runtime = SystemActionRuntime(self.facade, self.system_manager)

    def test_system_identity_delegates_to_system_manager(self):
        self.system_manager.is_atomic.return_value = True
        self.system_manager.get_package_manager.return_value = "rpm-ostree"
        self.assertTrue(self.runtime.is_atomic())
        self.assertEqual(self.runtime.package_manager(), "rpm-ostree")

    @patch("core.actions.catalog.platform.freedesktop_os_release")
    def test_fedora_version_is_reported_only_for_fedora(self, os_release):
        os_release.return_value = {"ID": "fedora", "VERSION_ID": "45"}
        self.assertEqual(self.runtime.fedora_version(), "45")
        os_release.return_value = {"ID": "ubuntu", "VERSION_ID": "24.04"}
        self.assertEqual(self.runtime.fedora_version(), "")
        os_release.side_effect = OSError("missing")
        self.assertEqual(self.runtime.fedora_version(), "")

    def test_package_manager_busy_fails_closed_on_probe_errors(self):
        self.facade.execute.return_value = ActionResult.ok("busy", exit_code=0)
        self.assertTrue(self.runtime.package_manager_busy())
        self.facade.execute.return_value = ActionResult.fail("unknown", exit_code=2)
        self.assertTrue(self.runtime.package_manager_busy())

    def test_failed_services_parses_valid_unique_units(self):
        self.facade.execute.return_value = ActionResult.ok(
            "queried",
            stdout="● broken.service loaded failed failed\ninvalid/unit loaded failed failed\nbroken.service loaded failed failed\n",
        )
        success, units, error = self.runtime.failed_services()
        self.assertTrue(success)
        self.assertEqual(units, ["broken.service"])
        self.assertEqual(error, "")

    def test_failed_services_propagates_probe_failure(self):
        self.facade.execute.return_value = ActionResult.fail("query failed", stderr="denied")
        success, units, error = self.runtime.failed_services()
        self.assertFalse(success)
        self.assertEqual(units, [])
        self.assertEqual(error, "query failed")

    def test_fstrim_support_probe_failure_paths_and_success(self):
        self.facade.execute.side_effect = [ActionResult.fail("missing")]
        supported, facts, reason = self.runtime.fstrim_support()
        self.assertFalse(supported)
        self.assertFalse(facts["fstrim_available"])
        self.assertIn("unavailable", reason)

        self.facade.execute.side_effect = [ActionResult.ok("version"), ActionResult.fail("lsblk failed")]
        supported, facts, reason = self.runtime.fstrim_support()
        self.assertFalse(supported)
        self.assertTrue(facts["fstrim_available"])
        self.assertIn("could not be verified", reason)

        self.facade.execute.side_effect = [ActionResult.ok("version"), ActionResult.ok("discard", stdout="0B\n0\n")]
        supported, facts, reason = self.runtime.fstrim_support()
        self.assertFalse(supported)
        self.assertFalse(facts["discard_supported"])
        self.assertIn("No mounted", reason)

        self.facade.execute.side_effect = [ActionResult.ok("version"), ActionResult.ok("discard", stdout="0B\n2G\n")]
        supported, facts, reason = self.runtime.fstrim_support()
        self.assertTrue(supported)
        self.assertTrue(facts["discard_supported"])
        self.assertEqual(reason, "")

    def test_parameter_validation_rejects_every_invalid_shape(self):
        definition = ActionCatalog().get("restart-failed-service")
        self.assertIsNotNone(definition)
        assert definition is not None
        self.assertEqual(validate_parameters(definition, {"extra": "x"}).reason_code, "invalid_parameters")
        self.assertEqual(validate_parameters(definition, {}).reason_code, "missing_parameter")
        self.assertEqual(validate_parameters(definition, {"service": 1}).reason_code, "invalid_parameter_type")
        self.assertEqual(validate_parameters(definition, {"service": "bad;unit"}).reason_code, "invalid_service_unit")
        self.assertTrue(validate_parameters(definition, {"service": "broken.service"}).allowed)

    def test_action_center_service_exposes_complete_catalog_without_preflight(self):
        items = ActionCenterService(facade=MagicMock(), history=MagicMock(), queue=MagicMock()).catalog_items("45-preview")

        self.assertEqual([item.id for item in items], [definition.id for definition in ActionCatalog().list()])
        self.assertTrue(all(item.source == "catalog:v17" for item in items))
        self.assertTrue(all(item.metadata["target"] == "45-preview" for item in items))
        self.assertTrue(all(not item.manual_only for item in items))


class TestV14ExecutionLifecycle(OrchestratorFixture):
    def test_apply_requires_confirmation_and_expires_after_thirty_minutes(self):
        plan = self.orchestrator.plan("dnf-clean-all")

        with self.assertRaises(ActionPlanRejectedError) as missing:
            self.orchestrator.prepare_run(plan.plan_id, confirmed=False)
        self.assertEqual(missing.exception.decision.reason_code, "confirmation_required")

        self.now = plan.expires_at
        with self.assertRaises(ActionPlanRejectedError) as expired:
            self.orchestrator.prepare_run(plan.plan_id, confirmed=True)
        self.assertEqual(expired.exception.decision.reason_code, "plan_expired")

    def test_medium_risk_without_rollback_requires_explicit_acceptance(self):
        plan = self.orchestrator.plan("restart-failed-service", {"service": "broken.service"})

        self.assertEqual(plan.state, "needs_review")
        with self.assertRaises(ActionPlanRejectedError) as rejected:
            self.orchestrator.prepare_run(plan.plan_id, confirmed=True)
        self.assertEqual(rejected.exception.decision.reason_code, "no_rollback_acceptance_required")

    def test_changed_preflight_facts_block_apply_as_system_drift(self):
        plan = self.orchestrator.plan("restart-failed-service", {"service": "broken.service"})
        self.runtime.failed.append("another.service")

        with self.assertRaises(ActionPlanRejectedError) as rejected:
            self.orchestrator.prepare_run(plan.plan_id, confirmed=True, accept_no_rollback=True)

        self.assertEqual(rejected.exception.decision.reason_code, "system_drift")
        self.assertEqual(self.plan_store.get(plan.plan_id).state, "blocked")

    def test_apply_stops_at_verifying_then_separate_verify_succeeds(self):
        plan = self.orchestrator.plan("restart-failed-service", {"service": "broken.service"})
        self.facade.execute.return_value = ActionResult.ok("restarted", exit_code=0, action_id=plan.action_id)

        run = self.orchestrator.apply(
            plan.plan_id,
            confirmed=True,
            accept_no_rollback=True,
            timeout=5,
        )

        self.assertEqual(run.state, "verifying")
        self.facade.execute.assert_called_once_with(
            ("systemctl", "restart", "broken.service"),
            privileged=True,
            timeout=5,
            action_id="restart-failed-service",
        )
        self.runtime.failed = []
        verified = self.orchestrator.verify(run.run_id)
        self.assertEqual(verified.state, "succeeded")
        self.assertTrue(verified.verification_result["success"])

    def test_polkit_dismissal_is_cancelled(self):
        plan = self.orchestrator.plan("dnf-clean-all")
        self.facade.execute.return_value = ActionResult.fail("Authorization dismissed", exit_code=126)

        run = self.orchestrator.apply(plan.plan_id, confirmed=True)

        self.assertEqual(run.state, "cancelled")
        self.assertEqual(run.state_history[-1]["reason"], "polkit-cancelled")

    def test_fstrim_needs_exit_zero_and_validated_output(self):
        plan = self.orchestrator.plan("fstrim-all")
        self.facade.execute.return_value = ActionResult.ok("done", stdout="no trim result\n", exit_code=0)
        run = self.orchestrator.apply(plan.plan_id, confirmed=True)

        verified = self.orchestrator.verify(run.run_id)

        self.assertEqual(verified.state, "verification_failed")
        self.assertEqual(verified.recovery_status, "manual-review-required")

    def test_fstrim_success_requires_a_validated_filesystem_line(self):
        plan = self.orchestrator.plan("fstrim-all")
        self.facade.execute.return_value = ActionResult.ok(
            "trimmed", stdout="/: 1.2 GiB (1288490188 bytes) trimmed on /dev/nvme0n1p3\n", exit_code=0
        )
        run = self.orchestrator.apply(plan.plan_id, confirmed=True)

        verified = self.orchestrator.verify(run.run_id)

        self.assertEqual(verified.state, "succeeded")
        self.assertEqual(verified.verification_result["data"]["validated_filesystem_count"], 1)

    def test_second_process_cannot_prepare_while_async_lease_is_held(self):
        first_plan = self.orchestrator.plan("dnf-clean-all")
        prepared = self.orchestrator.prepare_run(first_plan.plan_id, confirmed=True)
        other = ActionCenterOrchestrator(
            facade=MagicMock(),
            plan_store=self.plan_store,
            run_store=self.run_store,
            lease_path=self.lease_path,
            runtime=self.runtime,
            recover_interrupted=True,
        )
        second_plan = other.plan("dnf-clean-all")

        with self.assertRaises(ActionCenterBusyError):
            other.prepare_run(second_plan.plan_id, confirmed=True)

        self.assertEqual(self.run_store.get(prepared.run_id).state, "running")
        self.orchestrator.interrupt_run(prepared.run_id)


class TestV14PersistenceAndTransitions(unittest.TestCase):
    def test_plan_and_run_stores_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan_store = ActionPlanStore(Path(tmp) / "plans.json", max_plans=2)
            runtime = FakeRuntime()
            ids = iter(f"bounded-{index}" for index in range(20))
            orchestrator = ActionCenterOrchestrator(
                facade=MagicMock(),
                plan_store=plan_store,
                run_store=ActionRunStore(Path(tmp) / "runs.jsonl"),
                lease_path=Path(tmp) / "lease",
                runtime=runtime,
                id_factory=lambda: next(ids),
            )

            for _index in range(3):
                orchestrator.plan("dnf-clean-all")

            self.assertEqual(len(plan_store.list()), 2)

    def test_run_store_is_bounded_and_keeps_latest_record_per_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ActionRunStore(Path(tmp) / "runs.jsonl", max_runs=2)
            for index in range(3):
                store.save(ActionRun(f"run-{index}", "plan", "dnf-clean-all", f"correlation-{index}"))
            replacement = store.get("run-2")
            replacement.recovery_status = "updated"
            store.save(replacement)

            runs = store.list()
            self.assertEqual([run.run_id for run in runs], ["run-1", "run-2"])
            self.assertEqual(runs[-1].recovery_status, "updated")

    def test_future_schema_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plans.json"
            path.write_text(json.dumps({"schema_version": 99, "plans": []}), encoding="utf-8")
            store = ActionPlanStore(path)

            with self.assertRaises(ActionStoreVersionError):
                store.list()
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 99)

    def test_restart_marks_incomplete_runs_interrupted_without_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ActionRunStore(root / "runs.jsonl")
            store.save(
                ActionRun(
                    run_id="stale",
                    plan_id="plan",
                    action_id="dnf-clean-all",
                    correlation_id="correlation",
                    state="running",
                )
            )

            ActionCenterOrchestrator(
                facade=MagicMock(),
                plan_store=ActionPlanStore(root / "plans.json"),
                run_store=store,
                lease_path=root / "lease",
                runtime=FakeRuntime(),
            )

            recovered = store.get("stale")
            self.assertEqual(recovered.state, "interrupted")
            self.assertEqual(recovered.recovery_status, "manual-review-required")

    def test_restart_preserves_run_waiting_for_explicit_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ActionRunStore(root / "runs.jsonl")
            store.save(
                ActionRun(
                    run_id="awaiting-verification",
                    plan_id="plan",
                    action_id="dnf-clean-all",
                    correlation_id="correlation",
                    state="verifying",
                    execution_result={"success": True, "exit_code": 0},
                )
            )

            ActionCenterOrchestrator(
                facade=MagicMock(),
                plan_store=ActionPlanStore(root / "plans.json"),
                run_store=store,
                lease_path=root / "lease",
                runtime=FakeRuntime(),
            )

            recovered = store.get("awaiting-verification")
            self.assertEqual(recovered.state, "verifying")

    def test_succeeded_transition_requires_successful_verification(self):
        run = ActionRun("run", "plan", "dnf-clean-all", "correlation", state="verifying")

        with self.assertRaises(ActionLifecycleError):
            run.transition("succeeded", "invalid")

    def test_transition_tables_allow_only_declared_edges(self):
        for source, targets in PLAN_TRANSITIONS.items():
            for target in PLAN_TRANSITIONS:
                plan = ActionPlan(
                    "plan",
                    "dnf-clean-all",
                    {},
                    "44",
                    "digest",
                    ["dnf", "clean", "all"],
                    PolicyDecision(True, "ok", "ok"),
                    "low",
                    True,
                    "explicit",
                    "recovery",
                    True,
                    state=source,
                )
                if target in targets:
                    plan.transition(target, "test")
                    self.assertEqual(plan.state, target)
                else:
                    with self.assertRaises(ActionLifecycleError):
                        plan.transition(target, "test")

        for source, targets in RUN_TRANSITIONS.items():
            for target in RUN_TRANSITIONS:
                run = ActionRun("run", "plan", "dnf-clean-all", "correlation", state=source)
                if target == "succeeded":
                    run.verification_result = {"success": True}
                if target in targets:
                    run.transition(target, "test")
                    self.assertEqual(run.state, target)
                else:
                    with self.assertRaises(ActionLifecycleError):
                        run.transition(target, "test")


if __name__ == "__main__":
    unittest.main()
