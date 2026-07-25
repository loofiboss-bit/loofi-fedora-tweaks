"""v20 named-plan and retired direct-mutation contracts."""

from __future__ import annotations

import argparse
import unittest
from unittest.mock import MagicMock, patch

from cli.main import cmd_advanced, cmd_network, cmd_tweak
from core.actions import ActionCatalog
from core.executor.operations import AdvancedOps, NetworkOps, TweakOps


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
            patch("cli.main._emit_legacy_plans", return_value=1) as emit,
        ):
            result = command(args)

        self.assertEqual(result, 1)
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
