"""v20 named-plan and retired direct-mutation contracts."""

from __future__ import annotations

import argparse
import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cli.action_plans import create_public_plans, manual_guidance
from cli.main import _create_action_center_plan, cmd_advanced, cmd_network, cmd_tweak
from core.actions import ActionCatalog
from core.actions.catalog import validate_parameters
from core.actions.public_operations import public_operation_inventory
from core.executor.operations import AdvancedOps, NetworkOps, TweakOps
from scripts.validate_product_contract import _api_operation_ids, _cli_operation_ids

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "loofi-fedora-tweaks"
PUBLIC_HANDLER_PATHS = (
    SOURCE / "cli" / "main.py",
    *sorted((SOURCE / "cli" / "commands").glob("*.py")),
    *sorted((SOURCE / "api" / "routes").glob("*.py")),
)
DIRECT_MUTATION_METHODS = {
    "apply_profile",
    "apply_recommendation",
    "apply_swappiness",
    "apply_teleport",
    "close_port",
    "connect_device",
    "delete_snapshot",
    "disable_service",
    "enable_fractional_scaling",
    "enable_service",
    "install_app",
    "mask_service",
    "open_port",
    "pair_device",
    "remove_app",
    "restart_service",
    "restore_snapshot",
    "set_default_zone",
    "set_dns",
    "set_power",
    "start_service",
    "start_vm",
    "stop_service",
    "stop_vm",
    "trim_ssd",
    "unmask_service",
}


class TestV20MutationBoundary(unittest.TestCase):
    def _assert_named_plan(
        self,
        command,
        args: argparse.Namespace,
        action_id: str,
        parameters: dict[str, object],
    ) -> None:
        plan = MagicMock(state="blocked")
        plan.to_dict.return_value = {"action_id": action_id}
        plan.policy_decision.explanation = "Manual review required."
        with (
            patch("cli.main._create_action_center_plan", return_value=plan) as create,
            patch("cli.main._emit_legacy_plans", return_value=0) as emit,
        ):
            result = command(args)

        self.assertEqual(result, 0)
        create.assert_called_once_with(action_id, parameters)
        emit.assert_called_once_with([plan])

    def test_legacy_cli_mutations_create_exact_named_plans(self):
        cases = (
            (
                cmd_tweak,
                argparse.Namespace(action="power", profile="balanced", limit=80),
                "set-power-profile",
                {"profile": "balanced"},
            ),
            (
                cmd_tweak,
                argparse.Namespace(action="battery", profile="balanced", limit=75),
                "set-battery-limit",
                {"limit": 75},
            ),
            (
                cmd_advanced,
                argparse.Namespace(action="bbr", value=10),
                "enable-tcp-bbr",
                {},
            ),
            (
                cmd_advanced,
                argparse.Namespace(action="swappiness", value=20),
                "set-swappiness",
                {"value": 20},
            ),
            (
                cmd_network,
                argparse.Namespace(
                    action="dns",
                    provider="quad9",
                    connection="Wired connection 1",
                ),
                "configure-network-dns",
                {
                    "connection": "Wired connection 1",
                    "dns": "9.9.9.9 149.112.112.112",
                },
            ),
        )
        for command, args, action_id, parameters in cases:
            with self.subTest(action_id=action_id):
                self._assert_named_plan(command, args, action_id, parameters)

    @patch("core.executor.operations.subprocess.run")
    def test_retired_operation_helpers_never_spawn_mutating_commands(self, run):
        results = (
            TweakOps.set_battery_limit(80),
            AdvancedOps.apply_dnf_tweaks(),
            AdvancedOps.enable_tcp_bbr(),
            AdvancedOps.install_gamemode(),
            AdvancedOps.set_swappiness(10),
            NetworkOps.set_dns("cloudflare"),
        )

        self.assertTrue(all(not result.success for result in results))
        self.assertTrue(all("Action Center" in result.message for result in results))
        run.assert_not_called()

    def test_named_manual_boundaries_exist_and_validate_parameters(self):
        catalog = ActionCatalog()
        for action_id in (
            "set-battery-limit",
            "optimize-dnf-config",
            "enable-tcp-bbr",
            "install-gamemode",
            "set-swappiness",
            "configure-network-dns",
        ):
            with self.subTest(action_id=action_id):
                self.assertIsNotNone(catalog.get(action_id))

    @patch("core.actions.ActionCenterOrchestrator")
    def test_legacy_plan_alias_rejects_invalid_parameters_before_persistence(
        self,
        orchestrator_cls,
    ):
        with self.assertRaisesRegex(ValueError, "Invalid parameters"):
            _create_action_center_plan("set-battery-limit", {"limit": 101})

        orchestrator_cls.assert_not_called()


class TestPublicMutationBoundary(unittest.TestCase):
    def test_migrated_definitions_are_closed_for_traditional_and_atomic(self):
        catalog = ActionCatalog()
        cases = {
            "allow-firewall-port": {"port": 443, "protocol": "tcp", "zone": "public"},
            "firewall-service-control": {
                "action": "add",
                "service": "ssh",
                "zone": "public",
            },
            "set-firewall-default-zone": {"zone": "public"},
            "reload-firewall": {},
            "apply-performance-tuning": {
                "settings": {"governor": "schedutil", "swappiness": 20}
            },
            "restore-recovery-point": {
                "backend": "snapper",
                "snapshot_id": "42",
            },
            "delete-recovery-point": {
                "backend": "timeshift",
                "snapshot_id": "42",
            },
            "enable-desktop-extension": {"uuid": "example@example.org"},
            "disable-desktop-extension": {"uuid": "example@example.org"},
            "install-desktop-extension": {"uuid": "example@example.org"},
            "remove-desktop-extension": {"uuid": "example@example.org"},
            "update-flatpak-application": {"app_id": "org.example.App"},
            "set-fractional-scaling": {"enabled": True},
            "schedule-system-update": {"when": "02:00"},
            "rollback-latest-update": {},
            "control-focus-mode": {"action": "enable", "profile": "default"},
            "control-bluetooth-device": {
                "action": "connect",
                "target": "11:22:33:44:55:66",
            },
            "control-virtual-machine": {"action": "start", "name": "test-vm"},
        }

        for action_id, parameters in cases.items():
            with self.subTest(action_id=action_id):
                definition = catalog.get(action_id)
                self.assertIsNotNone(definition)
                assert definition is not None
                self.assertTrue(validate_parameters(definition, parameters).allowed)
                self.assertEqual(
                    definition.supported_variants,
                    frozenset({"traditional", "atomic"}),
                )
                self.assertEqual(definition.operation_class, "manual_only")
                self.assertTrue(callable(definition.verifier))

    def test_migrated_definition_rejects_unknown_parameters(self):
        definition = ActionCatalog().get("allow-firewall-port")
        self.assertIsNotNone(definition)
        assert definition is not None

        decision = validate_parameters(
            definition,
            {"port": 443, "protocol": "tcp", "command": "firewall-cmd"},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "invalid_parameters")

    def test_inventory_covers_every_cli_and_api_operation(self):
        operation_ids = _cli_operation_ids() | _api_operation_ids()
        inventory = public_operation_inventory(operation_ids)

        self.assertEqual({item.operation_id for item in inventory}, operation_ids)
        self.assertTrue(
            all(
                item.classification in {
                    "read_only",
                    "plan_only",
                    "manual_only",
                    "mutating",
                }
                for item in inventory
            )
        )
        self.assertFalse(any(item.direct_host_mutation for item in inventory))
        self.assertEqual(
            [item.operation_id for item in inventory if item.classification == "mutating"],
            ["cli:action-center apply"],
        )
        self.assertTrue(
            all(
                item.verification_method != "not_applicable"
                for item in inventory
                if item.classification != "read_only"
            )
        )

    def test_public_handlers_have_no_direct_execution_or_mutation_calls(self):
        violations = []
        for path in PUBLIC_HANDLER_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = (
                        [alias.name for alias in node.names]
                        if isinstance(node, ast.Import)
                        else [node.module or ""]
                    )
                    if "subprocess" in modules:
                        violations.append(f"{path.name}:{node.lineno}: subprocess import")
                if not isinstance(node, ast.Call):
                    continue
                call_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if call_name == "run_operation" or call_name in DIRECT_MUTATION_METHODS:
                    violations.append(f"{path.name}:{node.lineno}: {call_name}")
                if call_name in {"ActionDefinition", "PrivilegedCommand"}:
                    violations.append(f"{path.name}:{node.lineno}: open definition")

        self.assertEqual(violations, [])

    def test_only_action_center_apply_can_apply_an_existing_plan(self):
        apply_sites = []
        for path in PUBLIC_HANDLER_PATHS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "apply"
                ):
                    apply_sites.append((path.relative_to(SOURCE).as_posix(), node.lineno))

        self.assertEqual(len(apply_sites), 1)
        self.assertEqual(
            apply_sites[0][0],
            "cli/commands/readiness_commands.py",
        )
        readiness_source = (
            SOURCE / "core" / "diagnostics" / "readiness_actions.py"
        ).read_text(encoding="utf-8")
        run_source = readiness_source.split("    def run(", 1)[1].split(
            "    @classmethod\n    def verify(", 1
        )[0]
        self.assertNotIn(".apply(", run_source)

    @patch("cli.action_plans.ActionCenterOrchestrator")
    @patch("cli.action_plans.validate_parameters")
    @patch("cli.action_plans.ActionCatalog")
    def test_human_plan_summary_never_applies(
        self,
        catalog_cls,
        validate,
        orchestrator_cls,
    ):
        definition = MagicMock()
        catalog_cls.return_value.get.return_value = definition
        validate.return_value = MagicMock(allowed=True)
        plan = MagicMock(
            plan_id="plan-1",
            action_id="service-control",
            state="blocked",
            recovery_guidance="Review manually.",
        )
        plan.to_dict.return_value = {"plan_id": "plan-1", "state": "blocked"}
        plan.policy_decision.explanation = "Manual review required."
        orchestrator_cls.return_value.plan.return_value = plan
        lines = []

        result = create_public_plans(
            [
                (
                    "cli:service restart",
                    {"service": "sshd.service", "action": "restart", "scope": "system"},
                )
            ],
            json_output=False,
            output_json=lambda _payload: None,
            print_fn=lines.append,
        )

        self.assertEqual(result, 0)
        self.assertIn("Plan plan-1", lines[0])
        orchestrator_cls.return_value.apply.assert_not_called()

    @patch("cli.action_plans.ActionCenterOrchestrator")
    @patch("cli.action_plans.validate_parameters")
    @patch("cli.action_plans.ActionCatalog")
    def test_json_plan_summary_has_stable_review_fields(
        self,
        catalog_cls,
        validate,
        orchestrator_cls,
    ):
        catalog_cls.return_value.get.return_value = MagicMock()
        validate.return_value = MagicMock(allowed=True)
        plan = MagicMock(
            plan_id="plan-2",
            action_id="install-application",
            state="ready",
        )
        plan.to_dict.return_value = {"plan_id": "plan-2", "state": "ready"}
        orchestrator_cls.return_value.plan.return_value = plan
        payloads = []

        result = create_public_plans(
            [
                (
                    "cli:package install",
                    {"source": "fedora", "package_id": "htop"},
                )
            ],
            json_output=True,
            output_json=payloads.append,
            print_fn=lambda _text: None,
        )

        self.assertEqual(result, 0)
        payload = payloads[0]
        self.assertEqual(payload["schema_version"], 4)
        self.assertEqual(payload["plan_summaries"][0]["plan_id"], "plan-2")
        self.assertTrue(payload["plan_summaries"][0]["review_required"])
        self.assertFalse(payload["plan_summaries"][0]["auto_apply"])
        orchestrator_cls.return_value.apply.assert_not_called()

    @patch("cli.action_plans.ActionCenterOrchestrator")
    def test_invalid_parameters_are_rejected_before_plan_persistence(
        self,
        orchestrator_cls,
    ):
        payloads = []

        result = create_public_plans(
            [("cli:firewall open-port", {"port": 70000, "protocol": "tcp"})],
            json_output=True,
            output_json=payloads.append,
            print_fn=lambda _text: None,
        )

        self.assertEqual(result, 1)
        self.assertEqual(payloads[0]["error"], "invalid_action_parameters")
        orchestrator_cls.return_value.plan.assert_not_called()

    def test_manual_only_fallback_has_stable_json_contract(self):
        payloads = []

        result = manual_guidance(
            "cli:cleanup rpmdb",
            "Inspect RPM database health manually.",
            json_output=True,
            output_json=payloads.append,
            print_fn=lambda _text: None,
        )

        self.assertEqual(result, 0)
        self.assertEqual(payloads[0]["classification"], "manual_only")
        self.assertFalse(payloads[0]["auto_apply"])
