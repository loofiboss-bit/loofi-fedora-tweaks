#!/usr/bin/env python3
"""Capture real Orca speech generation for a safe review fixture on a private bus.

Uses the installed Orca engine with its audio server disabled. Generated speech
is recorded, not played. This qualifies integration, not human comprehension.
The desktop's Orca instance, settings, and accessibility bus are untouched.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def _speech_lines(log: Path, offset: int = 0) -> list[str]:
    return [line for line in log.read_bytes()[offset:].decode("utf-8", errors="replace").splitlines()
            if "SPEECH OUTPUT:" in line]


def _positive_checked(line: str) -> bool:
    return bool(
        re.search(r"\bchecked\b", line, re.IGNORECASE)
        and not re.search(r"\bnot\s+checked\b|\bunchecked\b", line, re.IGNORECASE)
    )


def _wait_for_speech(log: Path, predicate, offset: int = 0, timeout: int = 8) -> bool:
    from PyQt6.QtTest import QTest

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(predicate(line) for line in _speech_lines(log, offset)):
            return True
        QTest.qWait(100)
    return False


def probe(output: Path) -> int:
    sys.path.insert(0, str(ROOT / "loofi-fedora-tweaks"))
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    from ui.confirm_dialog import ReviewedActionDialog

    app = QApplication([])
    app.setApplicationName("Loofi accessibility qualification fixture")
    dialog = ReviewedActionDialog(
        "Loofi safe accessibility fixture", "No host action is connected to this review.",
        "Scope: qualification fixture only.", "No system or user setting is changed.",
        require_no_rollback_acceptance=True,
    )
    try:
        dialog.show()
        QTest.qWaitForWindowExposed(dialog, 3000)
        QTest.qWait(1000)
        log = output / "orca-debug.log"
        dialog.scope_view.setFocus()
        _wait_for_speech(log, lambda line: "exact change scope" in line.casefold())
        dialog.no_rollback_checkbox.setFocus()
        _wait_for_speech(log, lambda line: bool(re.search(r"\bnot\s+checked\b|\bunchecked\b", line, re.IGNORECASE)))
        assert not dialog.no_rollback_checkbox.isChecked()
        # Orca uses a line-buffered log. This boundary distinguishes unchecked
        # focus speech from state-change speech generated after the Space input.
        offset = (output / "orca-debug.log").stat().st_size
        QTest.keyClick(dialog.no_rollback_checkbox, Qt.Key.Key_Space)
        _wait_for_speech(log, _positive_checked, offset)
        assert dialog.no_rollback_checkbox.isChecked()
        (output / "probe-stages.json").write_text(json.dumps({
            "before_space_log_offset": offset,
            "unchecked_before_space": True,
            "checked_after_space": dialog.no_rollback_checkbox.isChecked(),
        }), encoding="utf-8")
        dialog.accept_button.setFocus()
        _wait_for_speech(log, lambda line: "apply and verify" in line.casefold(), offset)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        QTest.qWait(500)
        return 0
    finally:
        dialog.close()
        app.processEvents()


def _stop_process(process) -> None:
    """Bounded cleanup for one owned child, including partial startup failures."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _stop_process_group(process) -> None:
    """Clean only the new session group created for this private-bus wrapper."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # The group may retain broker/registry descendants after its leader exits.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=3)


def _speech_checks(log: bytes, stage: dict[str, object]) -> tuple[dict[str, bool], list[str]]:
    offset = stage.get("before_space_log_offset")
    if type(offset) is not int or not 0 <= offset <= len(log):
        raise ValueError("The probe must provide a valid pre-Space speech-log boundary.")
    before = [line for line in log[:offset].decode("utf-8", errors="replace").splitlines() if "SPEECH OUTPUT:" in line]
    after = [line for line in log[offset:].decode("utf-8", errors="replace").splitlines() if "SPEECH OUTPUT:" in line]
    speech = before + after
    checks = {text: any(text.casefold() in line.casefold() for line in speech)
              for text in ("Exact change scope", "Accept that this action has no automatic rollback", "Apply and verify")}
    checks["unchecked before Space"] = stage.get("unchecked_before_space") is True and any(
        re.search(r"\bnot\s+checked\b|\bunchecked\b", line, re.IGNORECASE) for line in before
    )
    checks["checked after Space"] = stage.get("checked_after_space") is True and any(
        _positive_checked(line) for line in after
    )
    return checks, speech


def _reset_run_artifacts(output: Path) -> None:
    # A previous readiness line must not let this engine skip its own startup.
    for name in ("orca-debug.log", "orca-process.log", "probe-stages.json", "qt-probe.log", "summary.json"):
        (output / name).unlink(missing_ok=True)


def worker(output: Path, platform: str) -> int:
    engine_code = """
import sys
from orca import debug, orca, speech_manager
debug.debugFile = open(sys.argv[1], 'w', encoding='utf-8', buffering=1)
# Full event debug formatting performs extra synchronous AT-SPI reads and can
# delay the event queue. Keep real speech output and readiness, plus severe errors.
debug.debugLevel = debug.LEVEL_SEVERE
original_print_message = debug.print_message
def capture_message(level, message, *args, **kwargs):
    if message.startswith('SPEECH OUTPUT:') or 'Starting Atspi main event loop' in message:
        level = debug.LEVEL_SEVERE
    original_print_message(level, message, *args, **kwargs)
debug.print_message = capture_message
# Keep Orca's real event handling and speech generation, without audio output.
speech_manager.get_manager().start_speech = lambda *args, **kwargs: None
sys.exit(orca.main(prefs_dir=sys.argv[2]))
"""
    _reset_run_artifacts(output)
    log = output / "orca-debug.log"
    stdout = output / "orca-process.log"
    with ExitStack() as stack:
        preferences = stack.enter_context(tempfile.TemporaryDirectory(prefix="loofi-orca-preferences-"))
        stream = stack.enter_context(stdout.open("w", encoding="utf-8", buffering=1))
        worker_env = os.environ.copy()
        launcher_env = dict(worker_env, ATSPI_DBUS_IMPLEMENTATION="dbus-daemon")
        accessibility_bus = subprocess.Popen(
            ["/usr/libexec/at-spi-bus-launcher", "--launch-immediately"],
            stdout=stream, stderr=subprocess.STDOUT, env=launcher_env,
        )
        stack.callback(_stop_process, accessibility_bus)
        deadline = time.monotonic() + 10
        while True:
            address = subprocess.run(
                ["gdbus", "call", "--session", "--dest", "org.a11y.Bus", "--object-path", "/org/a11y/bus",
                 "--method", "org.a11y.Bus.GetAddress"], capture_output=True, text=True, check=False, timeout=5,
            )
            if address.returncode == 0:
                worker_env["AT_SPI_BUS_ADDRESS"] = ast.literal_eval(address.stdout)[0]
                break
            if accessibility_bus.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("The private accessibility bus did not publish its address.")
            time.sleep(0.1)
        registry = subprocess.Popen(["/usr/libexec/at-spi2-registryd"], stdout=stream, stderr=subprocess.STDOUT, env=worker_env)
        stack.callback(_stop_process, registry)
        time.sleep(1)
        engine = subprocess.Popen([sys.executable, "-c", engine_code, str(log), preferences], stdout=stream, stderr=subprocess.STDOUT, env=worker_env)
        stack.callback(_stop_process, engine)
        deadline = time.monotonic() + 30
        while not log.exists() or "Starting Atspi main event loop" not in log.read_text(errors="replace"):
            if engine.poll() is not None:
                raise RuntimeError("The isolated Orca engine exited; inspect orca-process.log.")
            if time.monotonic() >= deadline:
                raise RuntimeError("The isolated Orca engine did not become ready within 30 seconds.")
            time.sleep(0.1)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--probe", "--platform", platform, "--output-dir", str(output)],
            capture_output=True, text=True, check=False, timeout=45, env=worker_env,
        )
        (output / "qt-probe.log").write_text(result.stderr, encoding="utf-8")
        result.check_returncode()
        time.sleep(1)
    stage = json.loads((output / "probe-stages.json").read_text(encoding="utf-8"))
    checks, speech = _speech_checks(log.read_bytes(), stage)
    report = {"platform": platform, "private_bus": True, "audio_server_disabled": True,
              "speech_generation_checks": checks, "utterances": speech, "probe_stages": stage,
              "scope": "Installed Orca event handling and speech generation; no human listening qualification"}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all(checks.values()) else 1


def _run_private_session(command: list[str], env: dict[str, str], timeout: int = 90) -> int:
    with ExitStack() as stack:
        process = subprocess.Popen(command, env=env, start_new_session=True)
        stack.callback(_stop_process_group, process)
        return process.wait(timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("wayland", "xcb"), default="wayland")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "test-results" / "orca-review")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.environ["QT_QPA_PLATFORM"] = args.platform
    os.environ["QT_LINUX_ACCESSIBILITY_ALWAYS_ON"] = "1"
    output = args.output_dir.resolve()
    if args.probe:
        return probe(output)
    output.mkdir(parents=True, exist_ok=True)
    if args.worker:
        try:
            return worker(output, args.platform)
        except (RuntimeError, ValueError, subprocess.SubprocessError) as error:
            report = {"platform": args.platform, "status": "failed", "reason": str(error),
                      "scope": "Incomplete private Orca run; no speech qualification success is asserted."}
            (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 1
    if not shutil.which("dbus-run-session") or not shutil.which("orca"):
        parser.error("This qualification requires installed Orca and dbus-run-session; no host packages are installed.")
    with tempfile.TemporaryDirectory(prefix="loofi-orca-xdg-") as directory:
        env = os.environ.copy()
        env.pop("AT_SPI_BUS_ADDRESS", None)
        env.pop("NO_AT_BRIDGE", None)
        for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
            env[f"XDG_{kind}_HOME"] = str(Path(directory) / kind.lower())
        env.update(LANG="en_US.UTF-8", LC_ALL="en_US.UTF-8", GSETTINGS_BACKEND="memory", QT_NO_XDG_DESKTOP_PORTAL="1", GTK_USE_PORTAL="0")
        try:
            return _run_private_session(
                ["dbus-run-session", "--", sys.executable, str(Path(__file__).resolve()), "--worker",
                 "--platform", args.platform, "--output-dir", str(output)], env,
            )
        except subprocess.TimeoutExpired:
            report = {"platform": args.platform, "status": "failed", "reason": "Private Orca qualification exceeded 90 seconds.",
                      "scope": "Timeout; no speech qualification success is asserted."}
            (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
