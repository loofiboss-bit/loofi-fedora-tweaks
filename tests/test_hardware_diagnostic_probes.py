"""Deterministic contracts for Everyday read-only device diagnostics."""

import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.catalog_models import NativeHandoffId
from core.platform.profile import DesktopEnvironment
from core.troubleshooting.lifecycle import CancellationSignal, new_session, start_session
from core.troubleshooting.service import DefaultEvidenceCollector
from services.desktop.native_handoff import NativeHandoffService
from services.hardware.diagnostic_probes import HardwareDiagnosticProbe


class TestHardwareDiagnosticProbe(unittest.TestCase):
    def collect(self, kind, outputs, signal=None):
        runner = MagicMock(side_effect=[subprocess.CompletedProcess([], 0, text, "") if isinstance(text, str) else text for text in outputs])
        probe = HardwareDiagnosticProbe(runner=runner, which=lambda name: "/usr/bin/" + name)
        result = probe.collect(kind, cancellation=signal or CancellationSignal())
        return result, runner

    def test_audio_reads_only_services_default_output_and_volume(self):
        result, runner = self.collect("audio", ["active", "active", "id 42, type PipeWire:Interface:Node\n", "Volume: 0.40 [MUTED]\n"])
        self.assertEqual(result.state, "completed")
        self.assertEqual(result.facts["default_sink_id"], 42)
        self.assertEqual(result.facts["output_volume"], {"level": 0.4, "muted": True})
        self.assertTrue(all(call.kwargs["timeout"] <= 2 for call in runner.call_args_list))
        self.assertEqual([call.args[0][1] for call in runner.call_args_list], ["--user", "--user", "inspect", "get-volume"])
        self.assertTrue(all(call.kwargs["env"]["LC_ALL"] == "C" for call in runner.call_args_list))

    def test_missing_tools_are_unknown_not_disabled(self):
        runner = MagicMock()
        result = HardwareDiagnosticProbe(runner=runner, which=lambda _: None).collect("audio", cancellation=CancellationSignal())
        self.assertEqual(result.state, "unavailable")
        self.assertEqual(result.reason_code, "tool-unavailable")
        self.assertTrue(all(value is None for value in result.facts.values()))
        runner.assert_not_called()

    def test_timeouts_and_malformed_output_retain_partial_metadata(self):
        result, _ = self.collect("audio", ["active", subprocess.TimeoutExpired("systemctl", 2), "garbled", "Volume: nan"])
        self.assertEqual(result.state, "partial")
        self.assertEqual(result.reason_code, "timed-out")
        self.assertIsNone(result.facts["output_volume"])
        self.assertEqual(result.facts["pipewire_state"], "active")

    def test_nonzero_exit_does_not_report_inactive(self):
        failure = subprocess.CompletedProcess([], 1, "inactive", "")
        result, _ = self.collect("audio", [failure] * 4)
        self.assertEqual(result.state, "unavailable")
        self.assertIsNone(result.facts["pipewire_state"])

    def test_bluetooth_retains_only_aggregate_local_metadata(self):
        result, runner = self.collect("bluetooth", [
            "active", "Controller AA:BB:CC:DD:EE:FF Private name\n\tPowered: no\n",
            '{"rfkilldevices": [{"type": "bluetooth", "soft": "blocked", "hard": "unblocked"}]}',
            "Device 11:22:33:44:55:66 Personal device\n",
        ])
        self.assertEqual(result.state, "completed")
        self.assertEqual(result.facts["paired_device_count"], 1)
        self.assertFalse(result.facts["adapter"]["powered"])
        self.assertTrue(result.facts["radio"]["soft_blocked"])
        self.assertNotIn("Private", str(result.facts))
        self.assertNotIn("11:22", str(result.facts))
        self.assertEqual([call.args[0][1:] for call in runner.call_args_list], [
            ["is-active", "bluetooth.service"], ["show"], ["--json", "--output", "TYPE,SOFT,HARD"], ["devices", "Paired"],
        ])

    def test_radio_malformed_rows_do_not_discard_other_observations(self):
        result, _ = self.collect("bluetooth", ["active", "garbled", '{"rfkilldevices": [null]}', ""])
        self.assertEqual(result.state, "partial")
        self.assertIsNone(result.facts["radio"])
        self.assertEqual(result.facts["paired_device_count"], 0)

    def test_deadline_prevents_later_commands(self):
        runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, "active", ""))
        clock = MagicMock(side_effect=[0, 0, 14, 14, 14])
        result = HardwareDiagnosticProbe(runner=runner, which=lambda _: "systemctl", monotonic=clock).collect("audio", cancellation=CancellationSignal())
        self.assertEqual(result.state, "partial")
        self.assertEqual(result.reason_code, "timed-out")
        self.assertEqual(runner.call_count, 1)

    def test_cancellation_preserves_first_observation_and_stops_reads(self):
        signal = CancellationSignal()
        def first(*args, **kwargs):
            signal.cancel()
            return subprocess.CompletedProcess([], 0, "active", "")
        runner = MagicMock(side_effect=first)
        result = HardwareDiagnosticProbe(runner=runner, which=lambda _: "systemctl").collect("audio", cancellation=signal)
        self.assertEqual(result.state, "partial")
        self.assertEqual(result.reason_code, "cancelled")
        self.assertEqual(result.facts["pipewire_state"], "active")
        self.assertEqual(runner.call_count, 1)

    @patch("services.hardware.diagnostic_probes.HardwareDiagnosticProbe")
    def test_collector_uses_real_profile_and_manual_guidance(self, probe):
        probe.return_value.collect.return_value = SimpleNamespace(
            facts={"output_volume": {"level": 0.0, "muted": True}}, state="partial", reason_code="tool-unavailable",
        )
        session = start_session(new_session("sound_not_working", "traditional", started_at=10), started_at=10)
        evidence = DefaultEvidenceCollector(clock=lambda: 11).collect("audio-state", session, started_at=10, cancellation=CancellationSignal())
        self.assertEqual(evidence.result.state, "partial")
        self.assertEqual(evidence.result.timeout_seconds, 15)
        self.assertEqual(evidence.findings[0].next_step.kind, "manual")
        self.assertIn("muted", evidence.findings[0].summary)


class TestDeviceNativeHandoffs(unittest.TestCase):
    def test_gnome_panels_are_closed_and_launch_rechecks_availability(self):
        for target, panel in ((NativeHandoffId.AUDIO_SETTINGS, "sound"), (NativeHandoffId.BLUETOOTH_SETTINGS, "bluetooth")):
            with self.subTest(target=target):
                which = MagicMock(return_value="/usr/bin/gnome-control-center")
                runner = MagicMock()
                service = NativeHandoffService(which=which, runner=runner)
                profile = SimpleNamespace(desktop=DesktopEnvironment.GNOME)
                launch = service.prepare_launch(target, profile=profile)
                self.assertEqual(launch.arguments, (panel,))
                runner.assert_not_called()
                which.return_value = None
                self.assertIsNone(service.prepare_launch(target, profile=profile))

    def test_kde_requires_exact_device_module(self):
        service = NativeHandoffService(
            which=lambda _: "/usr/bin/kcmshell6",
            runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "kcm_pulseaudio - Sound\nkcm_bluetooth - Bluetooth", ""),
        )
        profile = SimpleNamespace(desktop=DesktopEnvironment.KDE)
        self.assertEqual(service.prepare_launch(NativeHandoffId.AUDIO_SETTINGS, profile=profile).arguments, ("kcm_pulseaudio",))
        self.assertEqual(service.prepare_launch(NativeHandoffId.BLUETOOTH_SETTINGS, profile=profile).arguments, ("kcm_bluetooth",))
        self.assertIsNone(service.prepare_launch(NativeHandoffId.AUDIO_SETTINGS, profile=SimpleNamespace(desktop=DesktopEnvironment.UNKNOWN)))
