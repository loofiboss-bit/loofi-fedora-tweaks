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
from services.hardware.diagnostic_probes import MAX_OUTPUT_BYTES, HardwareDiagnosticProbe


class TestHardwareDiagnosticProbe(unittest.TestCase):
    def collect(self, kind, outputs, signal=None):
        runner = MagicMock(side_effect=[subprocess.CompletedProcess([], 0, text, "") if isinstance(text, str) else text for text in outputs])
        probe = HardwareDiagnosticProbe(
            runner=runner, which=lambda name: "/usr/bin/" + name,
            current_user=lambda: "test",
        )
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

    def test_oversized_output_is_rejected_with_stable_reason_code(self):
        result, runner = self.collect("display", ["x" * (MAX_OUTPUT_BYTES + 1)])
        self.assertEqual(result.state, "unavailable")
        self.assertEqual(result.reason_code, "output-too-large")
        self.assertIsNone(result.facts["displays"])
        self.assertNotIn("xxxx", str(result.facts))
        self.assertLessEqual(runner.call_args.kwargs["timeout"], 2.0)

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

    def test_energy_uses_aggregate_sysfs_metadata_and_power_profile(self):
        values = {
            "/sys/class/power_supply/BAT0/type": "Battery", "/sys/class/power_supply/BAT0/status": "Discharging",
            "/sys/class/power_supply/BAT0/capacity": "72", "/sys/class/power_supply/BAT0/energy_full": "42000000",
            "/sys/class/power_supply/BAT0/energy_full_design": "50000000", "/sys/class/power_supply/AC/type": "Mains",
            "/sys/class/power_supply/AC/online": "1",
        }
        runner = MagicMock(return_value=subprocess.CompletedProcess([], 0, "balanced", ""))
        probe = HardwareDiagnosticProbe(runner=runner, which=lambda name: "/usr/bin/" + name,
                                        listdir=lambda _: ["BAT0", "AC"], read_text=values.__getitem__)
        result = probe.collect("energy", cancellation=CancellationSignal())
        self.assertEqual(result.facts["batteries"], [{"status": "Discharging", "capacity_vs_design_percent": 84,
                         "capacity_percent": 72, "capacity_basis": "energy"}])
        self.assertTrue(result.facts["ac_online"])
        self.assertEqual(result.facts["power_profile"], "balanced")

    def test_energy_keeps_battery_when_optional_health_attributes_are_missing(self):
        values = {
            "/sys/class/power_supply/BAT0/type": "Battery",
            "/sys/class/power_supply/BAT0/status": "Full",
            "/sys/class/power_supply/BAT0/capacity": "65",
            "/sys/class/power_supply/BAT0/charge_full": "6500",
            "/sys/class/power_supply/BAT0/charge_full_design": "10000",
        }

        def read_text(path):
            try:
                return values[path]
            except KeyError as exc:
                raise FileNotFoundError(path) from exc

        probe = HardwareDiagnosticProbe(
            runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "balanced", ""),
            which=lambda _: "/usr/bin/powerprofilesctl", listdir=lambda _: ["BAT0"], read_text=read_text,
        )
        result = probe.collect("energy", cancellation=CancellationSignal())
        self.assertEqual(result.state, "completed")
        self.assertEqual(result.facts["battery_count"], 1)
        self.assertEqual(result.facts["batteries"], [{"status": "Full", "capacity_percent": 65,
            "capacity_vs_design_percent": 65, "capacity_basis": "charge"}])

    def test_energy_keeps_partial_battery_when_health_attributes_are_unavailable(self):
        values = {
            "/sys/class/power_supply/BAT0/type": "Battery",
            "/sys/class/power_supply/BAT0/status": "Discharging",
            "/sys/class/power_supply/BAT0/capacity": "41",
        }

        def read_text(path):
            try:
                return values[path]
            except KeyError as exc:
                raise FileNotFoundError(path) from exc

        probe = HardwareDiagnosticProbe(
            runner=lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "balanced", ""),
            which=lambda _: "/usr/bin/powerprofilesctl", listdir=lambda _: ["BAT0"], read_text=read_text,
        )
        result = probe.collect("energy", cancellation=CancellationSignal())
        self.assertEqual(result.state, "partial")
        self.assertEqual(result.facts["battery_count"], 1)
        self.assertEqual(result.facts["batteries"][0]["capacity_percent"], 41)
        self.assertIsNone(result.facts["batteries"][0]["capacity_vs_design_percent"])

    def test_display_probe_discards_names_and_keeps_unknown_mode_values(self):
        result, _ = self.collect("display", ['{"outputs":[{"name":"Private panel","connected":true,"enabled":true,"scale":1.25,"currentMode":{"size":{"width":1920,"height":1080},"refreshRate":60}}]}'])
        self.assertEqual(result.facts["displays"]["displays"][0], {"connected": True, "enabled": True, "width": 1920,
                         "height": 1080, "refresh_hz": 60.0, "scale": 1.25})
        self.assertNotIn("Private", str(result.facts))

    def test_display_probe_matches_kscreen_current_mode_id(self):
        payload = '{"outputs":[{"name":"Private panel","connected":true,"enabled":true,"scale":1.5,"size":{"width":2560,"height":1440},"currentModeId":"mode-2","modes":[{"id":"mode-1","size":{"width":1920,"height":1080},"refreshRate":60},{"id":"mode-2","size":{"width":2560,"height":1440},"refreshRate":144}]}]}'
        result, _ = self.collect("display", [payload])
        display = result.facts["displays"]["displays"][0]
        self.assertEqual(display, {"connected": True, "enabled": True, "width": 2560,
                         "height": 1440, "refresh_hz": 144.0, "scale": 1.5})
        self.assertEqual(result.facts["displays"]["connected_count"], 1)

    def test_input_aggregates_devices_without_persisting_names_or_motion(self):
        values = {"/sys/class/input/event0/device/name": "Private USB Keyboard",
                  "/sys/class/input/event1/device/name": "Private Touchpad",
                  "/home/test/.config/kcminputrc": "[Libinput][1234][5678][Private Touchpad]\nEnabled=false\n"}
        probe = HardwareDiagnosticProbe(which=lambda _: None, listdir=lambda _: ["event0", "event1"], read_text=values.__getitem__)
        with patch("services.hardware.diagnostic_probes.os.path.expanduser", return_value="/home/test/.config/kcminputrc"):
            result = probe.collect("input", cancellation=CancellationSignal())
        self.assertEqual(result.facts["devices"], 2)
        self.assertEqual(result.facts["touchpads"], 1)
        self.assertFalse(result.facts["touchpad_setting"])
        self.assertNotIn("Private", str(result.facts))

    def test_printer_probe_retains_only_counts(self):
        result, runner = self.collect("printer", ["active", "printer PrivateQueue is idle. enabled since ...",
            "PrivateQueue accepts requests since ...", "PrivateQueue-42 user 1 Tue"])
        self.assertEqual(result.facts["queues"], {"total": 1, "enabled": 1, "disabled": 0})
        self.assertEqual(result.facts["queue_acceptance"], {"total": 1, "accepting": 1, "rejecting": 0})
        self.assertEqual(result.facts["pending_job_count"], 1)
        self.assertNotIn("PrivateQueue", str(result.facts))
        self.assertEqual([call.args[0][1:] for call in runner.call_args_list], [
            ["is-active", "cups.service"], ["-p"], ["-a"], ["-W", "not-completed", "-u", "test"],
        ])

    def test_printer_disabled_continuation_and_rejecting_state_are_aggregated(self):
        result, _ = self.collect("printer", ["active",
            "printer PrivateQueue disabled since ... - backend unavailable\n  private detail continuation",
            "PrivateQueue not accepting requests since ...\n  private rejection detail", ""])
        self.assertEqual(result.facts["queues"], {"total": 1, "enabled": 0, "disabled": 1})
        self.assertEqual(result.facts["queue_acceptance"], {"total": 1, "accepting": 0, "rejecting": 1})
        self.assertNotIn("private", str(result.facts).lower())

    def test_malformed_display_or_printer_output_is_not_retained(self):
        display, _ = self.collect("display", ["not json"])
        printer, _ = self.collect("printer", ["active", "unexpected private content", "unexpected acceptance", ""])
        self.assertEqual(display.state, "unavailable")
        self.assertIsNone(display.facts["displays"])
        self.assertEqual(printer.state, "partial")
        self.assertIsNone(printer.facts["queues"])

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

    @patch("services.hardware.diagnostic_probes.HardwareDiagnosticProbe")
    def test_healthy_display_does_not_leave_a_persistent_issue_finding(self, probe):
        probe.return_value.collect.return_value = SimpleNamespace(
            facts={"displays": {"connected_count": 1, "active_count": 1, "displays": []}},
            state="completed", reason_code="",
        )
        session = start_session(new_session("display_problem", "traditional", started_at=10), started_at=10)
        evidence = DefaultEvidenceCollector(clock=lambda: 11).collect(
            "display-state", session, started_at=10, cancellation=CancellationSignal(),
        )
        self.assertFalse(evidence.findings)


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
