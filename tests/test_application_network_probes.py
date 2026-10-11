"""Deterministic contracts for bounded application and network probes."""

import json
import sys
import subprocess
import time
import unittest
from unittest.mock import MagicMock

from core.troubleshooting.lifecycle import CancellationSignal
from services.troubleshooting.application_network import (
    ApplicationIdentity,
    ApplicationNetworkProbe,
    _ProbeFailure,
    _bounded_subprocess_run,
)


class TestApplicationDiagnosticProbe(unittest.TestCase):
    def test_log_query_requires_explicit_launch_attempt_and_never_returns_raw_log(self):
        runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, "org.example.Editor\n", ""))
        probe = ApplicationNetworkProbe(runner=runner, which=lambda name: "/usr/bin/" + name)
        identity = ApplicationIdentity("rpm", "org.example.Editor")

        result = probe.collect_application(identity, launch_attempted=False, cancellation=CancellationSignal())

        self.assertTrue(result.facts["installed"])
        self.assertEqual(result.availability["recent_error_count"], "not_requested")
        self.assertEqual(runner.call_count, 1)
        runner.assert_called_once()
        self.assertEqual(runner.call_args.args[0], ["/usr/bin/rpm", "-q", "--qf", "%{NAME}\\n", "org.example.Editor"])

    def test_confirmed_flatpak_launch_collects_only_normalized_recent_error_counts(self):
        private = "/home/alice/Documents/private-project"
        journal = "\n".join((
            json.dumps({"PRIORITY": "3", "_COMM": "org.example.Editor", "MESSAGE": f"failed to read {private}"}),
            json.dumps({"PRIORITY": "6", "MESSAGE": "org.example.Editor startup detail"}),
        ))
        runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, "app/org.example.Editor/x86_64/stable\n", ""))
        bounded_runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, journal, ""))
        probe = ApplicationNetworkProbe(runner=runner, bounded_runner=bounded_runner, which=lambda name: "/usr/bin/" + name)
        identity = ApplicationIdentity("flatpak", "app/org.example.Editor/x86_64/stable", "user")

        result = probe.collect_application(identity, launch_attempted=True, cancellation=CancellationSignal())

        self.assertEqual(result.state, "completed")
        self.assertTrue(result.facts["installed"])
        self.assertEqual(result.facts["recent_error_count"], 1)
        self.assertEqual(result.facts["recent_matching_entry_count"], 2)
        self.assertEqual(result.facts["recent_metadata_match_count"], 1)
        self.assertEqual(result.facts["recent_message_match_count"], 1)
        self.assertNotIn(private, str(result))
        self.assertEqual(runner.call_args[0][0], [
            "/usr/bin/flatpak", "--user", "list", "--app", "--columns=ref",
        ])
        log_call = bounded_runner.call_args
        self.assertIn("--since=-5min", log_call.args[0])
        self.assertIn("--lines=100", log_call.args[0])
        self.assertIn("--output-fields=PRIORITY,_COMM,_EXE,_SYSTEMD_USER_UNIT,SYSLOG_IDENTIFIER,MESSAGE", log_call.args[0])
        self.assertIn(r"--grep=org\.example\.Editor", log_call.args[0])
        self.assertEqual(log_call.kwargs["max_output_bytes"], 65536)
        self.assertLessEqual(log_call.kwargs["timeout"], 2)

    def test_missing_rpm_is_known_absent_but_probe_errors_remain_unknown(self):
        absent = subprocess.CompletedProcess([], 1, "package missing-app is not installed\n", "")
        runner = MagicMock(return_value=absent)
        result = ApplicationNetworkProbe(runner=runner, which=lambda _: "/usr/bin/rpm").collect_application(
            ApplicationIdentity("rpm", "missing-app"), launch_attempted=False, cancellation=CancellationSignal(),
        )
        self.assertFalse(result.facts["installed"])
        self.assertEqual(result.availability["installed"], "available")

        runner.return_value = subprocess.CompletedProcess([], 2, "", "private stderr")
        failed = ApplicationNetworkProbe(runner=runner, which=lambda _: "/usr/bin/rpm").collect_application(
            ApplicationIdentity("rpm", "missing-app"), launch_attempted=False, cancellation=CancellationSignal(),
        )
        self.assertIsNone(failed.facts["installed"])
        self.assertEqual(failed.errors["installed"], "probe-failed")
        self.assertNotIn("private stderr", str(failed))

    def test_invalid_or_mismatched_flatpak_identity_is_rejected_or_unknown(self):
        with self.assertRaises(ValueError):
            ApplicationIdentity("flatpak", "../private")
        runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, "garbled inventory\n", ""))
        result = ApplicationNetworkProbe(runner=runner, which=lambda _: "/usr/bin/flatpak").collect_application(
            ApplicationIdentity("flatpak", "app/org.example.Editor/x86_64/stable"), launch_attempted=False, cancellation=CancellationSignal(),
        )
        self.assertIsNone(result.facts["installed"])
        self.assertEqual(result.errors["installed"], "invalid-response")

    def test_flatpak_exact_ref_absence_is_distinct_from_inventory_failure(self):
        runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, "app/org.example.Other/x86_64/stable\n", ""))
        probe = ApplicationNetworkProbe(runner=runner, which=lambda _: "/usr/bin/flatpak")
        absent = probe.collect_application(
            ApplicationIdentity("flatpak", "app/org.example.Editor/x86_64/stable", "system"),
            launch_attempted=False, cancellation=CancellationSignal(),
        )
        self.assertFalse(absent.facts["installed"])
        self.assertEqual(absent.availability["installed"], "available")
        self.assertEqual(runner.call_args.args[0], [
            "/usr/bin/flatpak", "--system", "list", "--app", "--columns=ref",
        ])

        runner.return_value = subprocess.CompletedProcess([], 1, "", "inventory permission denied")
        failed = probe.collect_application(
            ApplicationIdentity("flatpak", "app/org.example.Editor/x86_64/stable", "system"),
            launch_attempted=False, cancellation=CancellationSignal(),
        )
        self.assertIsNone(failed.facts["installed"])
        self.assertEqual(failed.errors["installed"], "probe-failed")
        self.assertNotIn("permission denied", str(failed))

    def test_named_flatpak_installation_uses_exact_installation_option(self):
        runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, "app/org.example.Editor/x86_64/stable\n", ""))
        result = ApplicationNetworkProbe(runner=runner, which=lambda _: "/usr/bin/flatpak").collect_application(
            ApplicationIdentity("flatpak", "app/org.example.Editor/x86_64/stable", "work-apps"),
            launch_attempted=False, cancellation=CancellationSignal(),
        )
        self.assertTrue(result.facts["installed"])
        self.assertEqual(runner.call_args.args[0], [
            "/usr/bin/flatpak", "--installation=work-apps", "list", "--app", "--columns=ref",
        ])

    def test_missing_journal_tool_does_not_hide_verified_installation(self):
        runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, "example-app\n", ""))
        probe = ApplicationNetworkProbe(runner=runner, which=lambda name: "/usr/bin/rpm" if name == "rpm" else None)
        result = probe.collect_application(
            ApplicationIdentity("rpm", "example-app"), launch_attempted=True, cancellation=CancellationSignal(),
        )
        self.assertTrue(result.facts["installed"])
        self.assertEqual(result.availability["recent_error_count"], "unknown")
        self.assertEqual(result.errors["recent_error_count"], "tool-unavailable")


class TestNetworkDiagnosticProbe(unittest.TestCase):
    def test_reports_link_route_resolver_and_cached_connectivity_independently(self):
        runner = MagicMock(side_effect=[
            subprocess.CompletedProcess([], 0, "connected\ndisconnected\n", ""),
            subprocess.CompletedProcess([], 0, '[{"dst":"default","dev":"wlp0s20f3"}]', ""),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "full\n", ""),
        ])
        probe = ApplicationNetworkProbe(
            runner=runner, which=lambda name: "/usr/bin/" + name,
            read_text=lambda *_args, **_kwargs: "# managed\nnameserver 192.0.2.53\n",
        )

        result = probe.collect_network(cancellation=CancellationSignal())

        self.assertEqual(result.state, "completed")
        self.assertEqual(result.facts, {
            "active_link": True,
            "default_route": True,
            "default_route_ipv4": True,
            "default_route_ipv6": False,
            "resolver_configured": True,
            "networkmanager_connectivity": "full",
        })
        self.assertNotIn("wlp0s20f3", str(result))
        self.assertEqual([call.args[0] for call in runner.call_args_list], [
            ["/usr/bin/nmcli", "-g", "STATE", "device", "status"],
            ["/usr/bin/ip", "-j", "route", "show", "default"],
            ["/usr/bin/ip", "-6", "-j", "route", "show", "default"],
            ["/usr/bin/nmcli", "-t", "-f", "CONNECTIVITY", "general"],
        ])

    def test_active_link_alone_does_not_imply_route_or_connectivity(self):
        runner = MagicMock(side_effect=[
            subprocess.CompletedProcess([], 0, "connected\n", ""),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "none\n", ""),
        ])
        result = ApplicationNetworkProbe(
            runner=runner, which=lambda name: "/usr/bin/" + name,
            read_text=lambda *_args, **_kwargs: "nameserver 192.0.2.1\n",
        ).collect_network(cancellation=CancellationSignal())
        self.assertTrue(result.facts["active_link"])
        self.assertFalse(result.facts["default_route"])
        self.assertEqual(result.facts["networkmanager_connectivity"], "none")

    def test_missing_tools_and_bad_resolver_are_unknown_with_distinct_errors(self):
        def missing_resolver(*_args, **_kwargs):
            raise FileNotFoundError("resolver unavailable")

        result = ApplicationNetworkProbe(which=lambda _: None, read_text=missing_resolver).collect_network(cancellation=CancellationSignal())
        self.assertEqual(result.state, "unavailable")
        self.assertEqual(result.errors["active_link"], "tool-unavailable")
        self.assertEqual(result.errors["default_route"], "tool-unavailable")
        self.assertEqual(result.availability["resolver_configured"], "unknown")
        self.assertEqual(result.errors["resolver_configured"], "read-failed")

    def test_malformed_command_output_is_not_reported_as_negative_state(self):
        runner = MagicMock(side_effect=[
            subprocess.CompletedProcess([], 0, "connected\nprivate-interface-name:unknown\n", ""),
            subprocess.CompletedProcess([], 0, "not json", ""),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "maybe\n", ""),
        ])
        result = ApplicationNetworkProbe(
            runner=runner, which=lambda name: "/usr/bin/" + name,
            read_text=lambda *_args, **_kwargs: "nameserver not-an-address\n",
        ).collect_network(cancellation=CancellationSignal())
        self.assertIsNone(result.facts["active_link"])
        self.assertIsNone(result.facts["default_route"])
        self.assertFalse(result.facts["resolver_configured"])
        self.assertIsNone(result.facts["networkmanager_connectivity"])
        self.assertEqual(result.errors["active_link"], "invalid-response")
        self.assertEqual(result.errors["default_route"], "invalid-response")
        self.assertEqual(result.errors["networkmanager_connectivity"], "invalid-response")

    def test_timeout_keeps_other_observations_and_is_bounded(self):
        runner = MagicMock(side_effect=[
            subprocess.CompletedProcess([], 0, "connected\n", ""),
            subprocess.TimeoutExpired("ip", 2),
            subprocess.CompletedProcess([], 0, '[{"dst":"default"}]', ""),
            subprocess.CompletedProcess([], 0, "limited\n", ""),
        ])
        result = ApplicationNetworkProbe(
            runner=runner, which=lambda name: "/usr/bin/" + name,
            read_text=lambda *_args, **_kwargs: "",
        ).collect_network(cancellation=CancellationSignal())
        self.assertEqual(result.state, "partial")
        self.assertTrue(result.facts["active_link"])
        self.assertTrue(result.facts["default_route"])
        self.assertEqual(result.errors["default_route_ipv4"], "timed-out")
        self.assertTrue(all(call.kwargs["timeout"] <= 2 for call in runner.call_args_list))

    def test_ipv6_only_default_route_counts_as_a_default_route(self):
        runner = MagicMock(side_effect=[
            subprocess.CompletedProcess([], 0, "connected\n", ""),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, '[{"dst":"default","gateway":"2001:db8::1"}]', ""),
            subprocess.CompletedProcess([], 0, "full\n", ""),
        ])
        result = ApplicationNetworkProbe(
            runner=runner, which=lambda name: "/usr/bin/" + name,
            read_text=lambda *_args, **_kwargs: "nameserver 2001:4860:4860::8888\n",
        ).collect_network(cancellation=CancellationSignal())
        self.assertTrue(result.facts["default_route"])
        self.assertFalse(result.facts["default_route_ipv4"])
        self.assertTrue(result.facts["default_route_ipv6"])

    def test_resolver_requires_a_strict_ip_address(self):
        runner = MagicMock(side_effect=[
            subprocess.CompletedProcess([], 0, "connected\n", ""),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "full\n", ""),
        ])
        result = ApplicationNetworkProbe(
            runner=runner, which=lambda name: "/usr/bin/" + name,
            read_text=lambda *_args, **_kwargs: "nameserver 999.999.999.999\nnameserver ::::\n",
        ).collect_network(cancellation=CancellationSignal())
        self.assertFalse(result.facts["resolver_configured"])


class TestBoundedJournalExecution(unittest.TestCase):
    def test_journal_output_is_stopped_before_it_can_be_fully_buffered(self):
        cancellation = CancellationSignal()
        with self.assertRaises(_ProbeFailure) as raised:
            _bounded_subprocess_run(
                [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1000000)"],
                timeout=2.0, max_output_bytes=1024, cancellation=cancellation,
                monotonic=time.monotonic, env={},
            )
        self.assertEqual(raised.exception.reason, "output-too-large")

    def test_bounded_journal_process_observes_timeout_and_cancellation(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            _bounded_subprocess_run(
                [sys.executable, "-c", "import time; time.sleep(2)"],
                timeout=0.03, max_output_bytes=1024, cancellation=CancellationSignal(),
                monotonic=time.monotonic, env={},
            )

        signal = CancellationSignal()
        signal.cancel()
        with self.assertRaises(_ProbeFailure) as raised:
            _bounded_subprocess_run(
                [sys.executable, "-c", "import time; time.sleep(2)"],
                timeout=2.0, max_output_bytes=1024, cancellation=signal,
                monotonic=time.monotonic, env={},
            )
        self.assertEqual(raised.exception.reason, "cancelled")


if __name__ == "__main__":
    unittest.main()
