"""Restart observations never become updates or reboot authorization."""
import json
import unittest
from argparse import Namespace
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from core.executor.action_result import ActionResult
from core.platform.profile import DeploymentBackend
from core.tasks.update_flow import STALE_SECONDS
from services.software.restart_advice import RESTART_QUERY, RestartAdviceService, parse_restart_result
from services.software.update_overview import OverviewCancelled
from test_upgrade_preparation import profile


def result(required=False, **fields):
    row = {"type": "reboot", "reboot_required": required, "packages": ["kernel"] if required else []}
    row.update(fields)
    return ActionResult(not required, "", int(required), stdout=json.dumps([row]))


class TestRestartAdvice(unittest.TestCase):
    def test_exit_code_one_is_valid_when_json_agrees(self):
        advice = parse_restart_result(result(True))
        self.assertEqual(advice.state, "required")
        self.assertEqual(advice.packages, ("kernel",))
        self.assertEqual(parse_restart_result(result()).state, "not_required")

    def test_invalid_and_contradictory_responses_are_unknown(self):
        invalid = [result(True, reboot_required=False), result(reboot_required=0), result(type="service"),
                   result(packages=["bad name"]), result(packages="kernel"), result(packages=[None]),
                   result(packages=["kernel"] * 501), ActionResult(True, "", 0, stdout="{}"),
                   ActionResult(True, "", 0, stdout="not json")]
        for response in invalid:
            with self.subTest(response=response.stdout):
                self.assertEqual(parse_restart_result(response).state, "unknown")
                self.assertEqual(parse_restart_result(response).reason, "invalid_response")

    def test_timeout_and_missing_tool_are_unknown(self):
        self.assertEqual(parse_restart_result(ActionResult(False, "", -1)).reason, "timeout")
        self.assertEqual(parse_restart_result(ActionResult(False, "", 127)).state, "unknown")
        self.assertEqual(parse_restart_result(None).state, "unknown")

    def test_manual_bounded_query_and_session_freshness(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        clock = Mock(return_value=now)
        runtime = Mock()
        runtime.execute_read_only.return_value = result(True)
        service = RestartAdviceService(profile=profile(), runtime=runtime, clock=clock)
        self.assertEqual(service.load().reason, "not_checked")
        runtime.execute_read_only.assert_not_called()
        advice = service.check()
        self.assertFalse(advice.stale)
        self.assertEqual(advice.checked_at, now.isoformat())
        runtime.execute_read_only.assert_called_once_with(RESTART_QUERY, action_id="restart-advice", timeout=8)
        clock.return_value = now + timedelta(seconds=STALE_SECONDS)
        self.assertTrue(service.load().stale)
        clock.return_value = now - timedelta(seconds=1)
        self.assertTrue(service.load().stale)
        self.assertEqual(advice.to_dict()["packages"], ["kernel"])
        runtime.execute_read_only.assert_called_once()

    def test_unsupported_hosts_do_not_probe(self):
        hosts = [replace(profile(), is_atomic=True, deployment_backend=DeploymentBackend.RPM_OSTREE),
                 replace(profile(), deployment_backend=DeploymentBackend.UNKNOWN),
                 replace(profile(), package_manager_command="dnf")]
        for host in hosts:
            runtime = Mock()
            service = RestartAdviceService(profile=host, runtime=runtime)
            self.assertEqual(service.check().reason, "unsupported_backend")
            runtime.execute_read_only.assert_not_called()

    def test_cancel_preserves_previous_advice(self):
        runtime = Mock()
        runtime.execute_read_only.return_value = result(True)
        service = RestartAdviceService(profile=profile(), runtime=runtime)
        before = service.check()
        service.cancel()
        with self.assertRaises(OverviewCancelled):
            service.check()
        self.assertEqual(service.load(), before)
        service.reset_cancel()
        runtime.execute_read_only.side_effect = lambda *a, **k: (service.cancel(), result())[1]
        with self.assertRaises(OverviewCancelled):
            service.check()
        self.assertEqual(service.load(), before)


class TestRestartCli(unittest.TestCase):
    @patch("services.software.restart_advice.RestartAdviceService")
    def test_cli_json_and_text(self, service_cls):
        from cli.commands.update_commands import handle_updates
        advice = parse_restart_result(result(True), checked_at="2026-01-01T00:00:00+00:00")
        service_cls.return_value.check.return_value = advice
        output, printer = Mock(), Mock()
        args = Namespace(action="restart-advice")
        self.assertEqual(handle_updates(args, True, output, printer, Mock(), Mock()), 0)
        output.assert_called_once_with(advice.to_dict())
        self.assertEqual(handle_updates(args, False, output, printer, Mock(), Mock()), 0)
        printer.assert_any_call("Restart recommended")
        printer.assert_any_call("Packages updated since boot: kernel")
        service_cls.return_value.check.return_value = parse_restart_result(None)
        self.assertEqual(handle_updates(args, True, output, printer, Mock(), Mock()), 1)


class TestRestartCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_manual_card_stale_display_and_cleanup(self):
        from ui.restart_advice import RestartAdviceCard
        service = Mock()
        advice = parse_restart_result(result(True), checked_at="2026-01-01T00:00:00+00:00")
        service.load.return_value = replace(advice, stale=True)
        card = RestartAdviceCard(service=service)
        service.check.assert_not_called()
        self.assertIn("Out of date", card.details.text())
        self.assertIn("kernel", card.details.text())
        self.assertFalse(card.busy)
        self.assertTrue(card.cleanup())
        service.cancel.assert_called_once()

    def test_async_check_without_automatic_restart(self):
        import time
        from ui.restart_advice import RestartAdviceCard
        runtime = Mock()
        runtime.execute_read_only.return_value = result(True)
        service = RestartAdviceService(profile=profile(), runtime=runtime)
        card = RestartAdviceCard(service=service)
        card.check()
        deadline = time.monotonic() + 2
        while card.busy and time.monotonic() < deadline:
            self.app.processEvents()
        self.assertFalse(card.busy)
        self.assertIn("Restart recommended", card.details.text())
        self.assertIn("kernel", card.details.text())
        runtime.execute_read_only.assert_called_once()
        self.assertTrue(card.cleanup())
