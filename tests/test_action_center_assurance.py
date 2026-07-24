"""v17 Assurance contracts for validated actions and reboot-aware runs."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.actions import ActionCatalog, ActionCenterOrchestrator, ActionPlanStore, ActionRun, ActionRunStore, PolicyDecision, VerificationDecision
from core.actions.catalog import validate_parameters
from core.actions.contracts import ActionDefinition, ActionPlan
from core.executor.action_result import ActionResult


class AssuranceRuntime:
    def __init__(self):
        self.atomic = False
        self.manager = "dnf"
        self.boot = "boot-a"
        self.results = {}

    def is_atomic(self):
        return self.atomic

    def package_manager(self):
        return self.manager

    def fedora_version(self):
        return "44"

    def package_manager_busy(self):
        return False

    def boot_id(self):
        return self.boot

    def execute_read_only(self, vector, *, action_id, timeout=30):
        result = self.results.get(tuple(vector))
        if result is not None:
            return result
        return ActionResult.ok("ok", stdout="ok\n", exit_code=0, action_id=action_id)


class TestAssuranceValidation(unittest.TestCase):
    def test_every_catalog_entry_has_closed_haven_metadata_and_parameters(self):
        for definition in ActionCatalog().list():
            with self.subTest(action=definition.id):
                self.assertIn(definition.operation_class, {"host", "app_state", "session", "manual_only"})
                self.assertTrue(definition.supported_variants)
                self.assertTrue(definition.supported_variants <= {"traditional", "atomic"})
                self.assertIn(definition.reboot_policy, {"none", "may_require", "required"})
                self.assertTrue(definition.affected_resources)
                self.assertEqual(
                    validate_parameters(definition, {"__unexpected": "value"}).reason_code,
                    "invalid_parameters",
                )

    def test_application_identifiers_sources_and_urls_are_strict(self):
        definition = ActionCatalog().get("install-application")
        self.assertIsNotNone(definition)
        assert definition is not None

        self.assertTrue(validate_parameters(definition, {"source": "fedora", "package_id": "firefox"}).allowed)
        self.assertTrue(validate_parameters(definition, {"source": "flatpak", "package_id": "org.mozilla.firefox"}).allowed)
        self.assertFalse(validate_parameters(definition, {"source": "fedora", "package_id": "--nogpgcheck"}).allowed)
        self.assertFalse(validate_parameters(definition, {"source": "fedora", "package_id": "https://example.invalid/a.rpm"}).allowed)
        self.assertFalse(validate_parameters(definition, {"source": "external", "package_id": "firefox"}).allowed)

    def test_retention_and_backend_values_are_closed_sets(self):
        journal = ActionCatalog().get("vacuum-journal")
        recovery = ActionCatalog().get("create-recovery-point")
        assert journal is not None and recovery is not None

        self.assertTrue(validate_parameters(journal, {"days": 14}).allowed)
        self.assertFalse(validate_parameters(journal, {"days": "14"}).allowed)
        self.assertFalse(validate_parameters(journal, {"days": 31}).allowed)
        self.assertTrue(validate_parameters(recovery, {"backend": "snapper", "description": "Before update"}).allowed)
        self.assertFalse(validate_parameters(recovery, {"backend": "btrfs", "description": "Before update"}).allowed)

    def test_application_privilege_is_source_specific(self):
        definition = ActionCatalog().get("install-application")
        assert definition is not None and definition.privilege_resolver is not None
        runtime = AssuranceRuntime()

        self.assertTrue(definition.privilege_resolver({"source": "fedora", "package_id": "firefox"}, runtime))
        self.assertFalse(definition.privilege_resolver({"source": "flatpak", "package_id": "org.mozilla.firefox"}, runtime))

    def test_local_profile_review_accepts_only_bounded_data(self):
        definition = ActionCatalog().get("local-profile-review")
        assert definition is not None
        valid = {
            "profile": "travel",
            "settings": {
                "schema_version": 1,
                "name": "Travel",
                "power_profile": "balanced",
                "battery_limit": 80,
            },
        }

        self.assertTrue(validate_parameters(definition, valid).allowed)
        self.assertFalse(validate_parameters(definition, {**valid, "profile": "travel; reboot"}).allowed)
        self.assertFalse(validate_parameters(definition, {**valid, "settings": []}).allowed)
        self.assertFalse(
            validate_parameters(
                definition,
                {**valid, "settings": {"unknown_setting": "value"}},
            ).allowed
        )

    def test_manual_boundary_parameter_matrix_rejects_out_of_range_and_injection_values(self):
        cases = {
            "block-firewall-port": ({"port": 443, "protocol": "tcp"}, {"port": 0, "protocol": "tcp"}),
            "allow-usb-device": ({"device_id": "1234:abcd"}, {"device_id": "1234; reboot"}),
            "set-grub-timeout": ({"seconds": 10}, {"seconds": 61}),
            "set-cpu-governor": ({"governor": "performance"}, {"governor": "turbo"}),
            "set-power-profile": ({"profile": "balanced"}, {"profile": "turbo"}),
            "set-gpu-mode": ({"mode": "hybrid"}, {"mode": "discrete"}),
            "set-fan-speed": ({"speed": -1}, {"speed": 101}),
            "install-developer-tool": ({"tool": "rustup"}, {"tool": "curl | sh"}),
            "apply-system-profile": ({"profile": "workstation"}, {"profile": "../../etc"}),
            "configure-hostname-privacy": (
                {"connection": "Home WiFi", "hidden": True},
                {"connection": "Home\nWiFi", "hidden": True},
            ),
            "configure-network-dns": (
                {"connection": "Home WiFi", "dns": "1.1.1.1, 2606:4700:4700::1111"},
                {"connection": "Home WiFi", "dns": "https://resolver.invalid"},
            ),
            "service-control": (
                {"service": "sshd.service", "action": "restart", "scope": "system"},
                {"service": "sshd.service", "action": "reload-or-reboot", "scope": "system"},
            ),
            "configure-kernel-parameter": (
                {"parameter": "ipv6.disable=1", "enabled": True},
                {"parameter": "ipv6.disable=1;reboot", "enabled": True},
            ),
            "restore-grub-backup": ({"backup": "backup-1"}, {"backup": "../backup"}),
            "configure-zram": (
                {"size_percent": 50, "algorithm": "zstd"},
                {"size_percent": 5, "algorithm": "gzip"},
            ),
        }
        catalog = ActionCatalog()
        for action_id, (valid, invalid) in cases.items():
            definition = catalog.get(action_id)
            assert definition is not None
            with self.subTest(action=action_id, case="valid"):
                self.assertTrue(validate_parameters(definition, valid).allowed)
            with self.subTest(action=action_id, case="invalid"):
                self.assertFalse(validate_parameters(definition, invalid).allowed)


class TestAssuranceLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.runtime = AssuranceRuntime()
        self.facade = MagicMock()
        self.facade.execute.return_value = ActionResult.ok("executed", exit_code=0)
        definition = ActionDefinition(
            id="reboot-test",
            capability_id="test.reboot",
            title="Reboot test",
            description="Test reboot lifecycle.",
            parameter_schema={},
            risk_level="low",
            privileged=False,
            confirmation_policy="explicit",
            recovery_guidance="None",
            rollback_supported=False,
            command_renderer=lambda _parameters, _runtime: ["dnf", "clean", "all"],
            preflight_checker=lambda _parameters, _runtime: PolicyDecision(True, "preflight_ok", "Ready."),
            verifier=lambda run, _plan, runtime: (
                VerificationDecision.awaiting_reboot("Reboot required.", expected_boot="boot-b")
                if runtime.boot_id() == run.execution_boot_id
                else VerificationDecision.succeeded("Expected boot verified.")
            ),
        )
        self.orchestrator = ActionCenterOrchestrator(
            facade=self.facade,
            catalog=ActionCatalog([definition]),
            plan_store=ActionPlanStore(root / "plans.json"),
            run_store=ActionRunStore(root / "runs.jsonl"),
            lease_path=root / "lease",
            runtime=self.runtime,
            clock=lambda: 1000.0,
            id_factory=iter(["plan", "run", "correlation"]).__next__,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_verification_waits_for_and_resumes_after_reboot(self):
        plan = self.orchestrator.plan("reboot-test")
        run = self.orchestrator.apply(plan.plan_id, confirmed=True)

        waiting = self.orchestrator.verify(run.run_id)
        self.assertEqual(waiting.state, "awaiting_reboot")
        self.assertTrue(waiting.reboot_required)
        self.assertEqual(waiting.verification_attempts, 1)

        still_waiting = self.orchestrator.verify(run.run_id)
        self.assertEqual(still_waiting.state, "awaiting_reboot")
        self.assertEqual(still_waiting.verification_attempts, 2)

        self.runtime.boot = "boot-b"
        succeeded = self.orchestrator.verify(run.run_id)
        self.assertEqual(succeeded.state, "succeeded")
        self.assertFalse(succeeded.reboot_required)
        self.assertEqual(succeeded.verification_attempts, 3)


class TestAssuranceDefinitionMatrix(unittest.TestCase):
    def setUp(self):
        self.runtime = AssuranceRuntime()
        self.catalog = ActionCatalog()

    @staticmethod
    def _plan(definition, parameters, decision):
        return ActionPlan(
            plan_id="plan",
            action_id=definition.id,
            parameters=dict(parameters),
            target="44",
            digest="digest",
            preview=[],
            policy_decision=decision,
            risk_level=definition.risk_level,
            privileged=definition.privileged,
            confirmation_policy=definition.confirmation_policy,
            recovery_guidance=definition.recovery_guidance,
            rollback_supported=definition.rollback_supported,
        )

    @staticmethod
    def _run(action_id, *, boot_id="boot-a", verification_result=None):
        return ActionRun(
            "run",
            "plan",
            action_id,
            "correlation",
            execution_boot_id=boot_id,
            verification_result=verification_result,
        )

    def test_traditional_fedora_update_verifies_only_planned_nevras_and_health(self):
        definition = self.catalog.get("update-fedora-system")
        assert definition is not None
        query = ("dnf", "repoquery", "--upgrades", "--qf", "%{name}|%{evr}|%{arch}")
        self.runtime.results[query] = ActionResult.ok("updates", stdout="alpha|2-1|x86_64\nbeta|3-1|noarch\n")

        decision = definition.preflight_checker({}, self.runtime)

        self.assertTrue(decision.allowed)
        self.assertEqual(definition.command_renderer({}, self.runtime), ["dnf", "upgrade", "--refresh", "-y"])
        self.runtime.results[("rpm", "-q", "--qf", "%{name}|%{evr}|%{arch}\\n", "alpha")] = ActionResult.ok(
            "installed", stdout="alpha|2-1|x86_64\n"
        )
        self.runtime.results[("rpm", "-q", "--qf", "%{name}|%{evr}|%{arch}\\n", "beta")] = ActionResult.ok(
            "installed", stdout="beta|3-1|noarch\n"
        )
        self.runtime.results[("dnf", "check")] = ActionResult.ok("healthy")
        result = definition.verifier(self._run(definition.id), self._plan(definition, {}, decision), self.runtime)
        self.assertEqual(result.state, "succeeded")
        self.assertEqual(result.data["verified_packages"], 2)

    def test_atomic_update_stages_then_requires_the_exact_booted_deployment(self):
        definition = self.catalog.get("update-fedora-system")
        assert definition is not None
        self.runtime.atomic = True
        status = ("rpm-ostree", "status", "--json")
        self.runtime.results[status] = ActionResult.ok(
            "status",
            stdout=json.dumps({"deployments": [{"booted": True, "checksum": "old"}]}),
        )
        decision = definition.preflight_checker({}, self.runtime)
        plan = self._plan(definition, {}, decision)
        self.runtime.results[status] = ActionResult.ok(
            "status",
            stdout=json.dumps({"deployments": [{"staged": True, "checksum": "new"}, {"booted": True, "checksum": "old"}]}),
        )

        waiting = definition.verifier(self._run(definition.id), plan, self.runtime)

        self.assertEqual(waiting.state, "awaiting_reboot")
        self.assertEqual(waiting.data["expected_checksum"], "new")
        previous = {"data": {"expected_checksum": "new"}}
        self.runtime.boot = "boot-b"
        self.runtime.results[status] = ActionResult.ok(
            "status",
            stdout=json.dumps({"deployments": [{"booted": True, "checksum": "new"}]}),
        )
        verified = definition.verifier(self._run(definition.id, verification_result=previous), plan, self.runtime)
        self.assertEqual(verified.state, "succeeded")

    def test_flatpak_update_uses_and_verifies_exact_refs_and_commits(self):
        definition = self.catalog.get("update-flatpaks")
        assert definition is not None
        query = ("flatpak", "remote-ls", "--updates", "--columns=ref,commit")
        self.runtime.results[query] = ActionResult.ok("updates", stdout="org.example.App\tcommit-2\n")
        decision = definition.preflight_checker({}, self.runtime)

        self.assertEqual(
            definition.command_renderer({}, self.runtime),
            ["flatpak", "update", "--noninteractive", "--assumeyes", "org.example.App"],
        )
        self.runtime.results[("flatpak", "info", "--show-commit", "org.example.App")] = ActionResult.ok(
            "installed", stdout="commit-2\n"
        )
        result = definition.verifier(self._run(definition.id), self._plan(definition, {}, decision), self.runtime)
        self.assertEqual(result.state, "succeeded")

    def test_firmware_missing_history_waits_once_then_fails_after_reboot(self):
        definition = self.catalog.get("update-firmware")
        assert definition is not None
        updates = ("fwupdmgr", "get-updates", "--json")
        self.runtime.results[updates] = ActionResult.ok(
            "updates",
            stdout=json.dumps({"Devices": [{"Guid": "GUID-1", "Version": "2", "Checksum": "sha256:abc"}]}),
        )
        decision = definition.preflight_checker({}, self.runtime)
        self.runtime.results[("fwupdmgr", "get-history", "--json")] = ActionResult.ok("history", stdout="{}")
        plan = self._plan(definition, {}, decision)
        run = self._run(definition.id)

        self.assertEqual(definition.verifier(run, plan, self.runtime).state, "awaiting_reboot")
        self.runtime.boot = "boot-b"
        self.assertEqual(definition.verifier(run, plan, self.runtime).state, "failed")

    def test_application_matrix_verifies_exact_rpm_and_flatpak_state(self):
        install = self.catalog.get("install-application")
        remove = self.catalog.get("remove-application")
        assert install is not None and remove is not None
        rpm_query = ("rpm", "-q", "--qf", "%{name}|%{evr}|%{arch}\\n", "alpha")
        self.runtime.results[rpm_query] = ActionResult.fail("missing", exit_code=1)
        available = ("dnf", "repoquery", "--available", "--latest-limit", "1", "--qf", "%{name}|%{evr}|%{arch}", "alpha")
        self.runtime.results[available] = ActionResult.ok("available", stdout="alpha|2-1|x86_64\n")
        params = {"source": "fedora", "package_id": "alpha"}
        decision = install.preflight_checker(params, self.runtime)
        self.runtime.results[rpm_query] = ActionResult.ok("installed", stdout="alpha|2-1|x86_64\n")
        self.assertEqual(install.verifier(self._run(install.id), self._plan(install, params, decision), self.runtime).state, "succeeded")

        flatpak_params = {"source": "flatpak", "package_id": "org.example.App"}
        self.runtime.results[("flatpak", "info", "org.example.App")] = ActionResult.ok("installed")
        remove_decision = remove.preflight_checker(flatpak_params, self.runtime)
        self.runtime.results[("flatpak", "info", "--show-commit", "org.example.App")] = ActionResult.fail("missing")
        self.assertEqual(remove.verifier(self._run(remove.id), self._plan(remove, flatpak_params, remove_decision), self.runtime).state, "succeeded")

    def test_cleanup_and_recovery_verify_measured_postconditions(self):
        journal = self.catalog.get("vacuum-journal")
        autoremove = self.catalog.get("autoremove-packages")
        recovery = self.catalog.get("create-recovery-point")
        assert journal is not None and autoremove is not None and recovery is not None
        usage = ("journalctl", "--disk-usage", "--no-pager")
        self.runtime.results[usage] = ActionResult.ok("usage", stdout="Archived and active journals take up 1.0G in the file system.\n")
        journal_decision = journal.preflight_checker({"days": 14}, self.runtime)
        self.runtime.results[usage] = ActionResult.ok("usage", stdout="Archived and active journals take up 512.0M in the file system.\n")
        self.assertEqual(
            journal.verifier(self._run(journal.id), self._plan(journal, {"days": 14}, journal_decision), self.runtime).state,
            "succeeded",
        )

        query = ("dnf", "repoquery", "--unneeded", "--installed", "--qf", "%{name}")
        self.runtime.results[query] = ActionResult.ok("unneeded", stdout="old-lib\n")
        autoremove_decision = autoremove.preflight_checker({}, self.runtime)
        self.assertEqual(autoremove.command_renderer({}, self.runtime), ["dnf", "remove", "-y", "old-lib"])
        self.runtime.results[("rpm", "-q", "old-lib")] = ActionResult.fail("removed", exit_code=1)
        self.runtime.results[("dnf", "check")] = ActionResult.ok("healthy")
        self.assertEqual(
            autoremove.verifier(self._run(autoremove.id), self._plan(autoremove, {}, autoremove_decision), self.runtime).state,
            "succeeded",
        )
        self.runtime.atomic = True
        self.assertEqual(autoremove.preflight_checker({}, self.runtime).reason_code, "atomic_manual_only")
        self.runtime.atomic = False

        listing = ("snapper", "list")
        self.runtime.results[listing] = ActionResult.ok("before", stdout="1 | old\n")
        recovery_params = {"backend": "snapper", "description": "Before update"}
        recovery_decision = recovery.preflight_checker(recovery_params, self.runtime)
        self.runtime.results[listing] = ActionResult.ok("after", stdout="1 | old\n2 | Before update\n")
        self.assertEqual(
            recovery.verifier(self._run(recovery.id), self._plan(recovery, recovery_params, recovery_decision), self.runtime).state,
            "succeeded",
        )


class TestAssuranceStoreMigration(unittest.TestCase):
    def test_v1_plan_is_migrated_to_v4_with_backup_and_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plans.json"
            plan = ActionPlan(
                plan_id="plan-1",
                action_id="dnf-clean-all",
                parameters={},
                target="44",
                digest="digest",
                preview=["dnf", "clean", "all"],
                policy_decision=PolicyDecision(True, "preflight_ok", "Ready."),
                risk_level="low",
                privileged=True,
                confirmation_policy="explicit",
                recovery_guidance="Refresh metadata.",
                rollback_supported=True,
            )
            path.write_text(json.dumps({"schema_version": 1, "plans": [plan.to_dict()]}), encoding="utf-8")

            loaded = ActionPlanStore(path).list()

            self.assertEqual(loaded[0].plan_id, "plan-1")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 4)
            self.assertTrue(path.with_suffix(".json.lkg").exists())

    def test_v1_run_is_migrated_to_v4_with_backup_and_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.jsonl"
            run = ActionRun("run-1", "plan-1", "dnf-clean-all", "correlation-1")
            path.write_text(json.dumps({"action_run_schema_version": 1, **run.to_dict()}) + "\n", encoding="utf-8")

            loaded = ActionRunStore(path).list()

            self.assertEqual(loaded[0].run_id, "run-1")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["action_run_schema_version"], 4)
            self.assertTrue(path.with_suffix(".jsonl.lkg").exists())
