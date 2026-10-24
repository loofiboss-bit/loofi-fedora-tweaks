#!/usr/bin/python3
"""Guest-side runner invoked through the authenticated guest serial console."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


WORK = Path("/var/tmp/loofi-e2e")


def _crash_diagnostics() -> dict:
    """Retain bounded guest crash frames, never coredump environment fields."""
    diagnostics = {}
    commands = {
        "kernel": ["journalctl", "--boot", "--dmesg", "--no-pager", "--output=short-monotonic",
                   "--grep=segfault|general protection|traps:|oom-kill|Out of memory|Killed process"],
        "coredumps": ["coredumpctl", "--no-pager", "--since=-1h", "info"],
    }
    for name, command in commands.items():
        if not shutil.which(command[0]):
            diagnostics[name] = {"available": False}
            continue
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            lines = result.stdout.splitlines()
            if name == "coredumps":
                lines = [line for line in lines if line.lstrip().startswith(
                    ("Signal:", "Executable:", "Stack trace of thread", "#"))]
            diagnostics[name] = {"available": True, "exit_code": result.returncode,
                                 "text": "\n".join(lines)[-32768:]}
        except (OSError, subprocess.TimeoutExpired):
            diagnostics[name] = {"available": False}
    return diagnostics


def _run_install(rpm_path: Path, archive_path: Path, credentials_path: Path) -> int:
    log_path = WORK / "install.log"
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            ["/usr/bin/rpm", "--upgrade", "--replacepkgs", "--nosignature", "--verbose", str(rpm_path)],
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=5 * 60,
            check=False,
        )
    if result.returncode:
        print(f"Guest RPM installation failed; see {log_path}.")
        return result.returncode

    suite = WORK / "suite"
    suite.mkdir(mode=0o700, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            target = Path(member.name)
            if target.is_absolute() or ".." in target.parts or not member.isfile():
                raise RuntimeError(f"Unsafe E2E test archive member: {member.name}")
        archive.extractall(WORK, filter="data")

    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    user = pwd.getpwnam(str(credentials["user"]))
    os.chown(credentials_path, user.pw_uid, user.pw_gid)
    os.chmod(credentials_path, 0o600)
    os.chown(WORK, user.pw_uid, user.pw_gid)
    os.chmod(WORK, 0o700)
    sys.path.insert(0, str(WORK / "e2e" / "tests"))
    from flatpak_fixture import prepare
    prepare(user.pw_name)
    print("RPM installed and E2E tests staged in the guest.")
    return 0


def _session_environment(uid: int) -> dict[str, str]:
    """Read display/session values from the logged-in Plasma processes."""
    candidates: list[dict[str, str]] = []
    kwin_pid: str | None = None
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            status = (entry / "status").read_text(encoding="utf-8", errors="replace")
            uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
            if int(uid_line.split()[1]) != uid:
                continue
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", errors="replace").lower()
            if not any(name in cmdline for name in ("plasmashell", "kwin_x11", "kwin_wayland", "startplasma-x11", "startplasma-wayland", "plasma-session")):
                continue
            if "/kwin_wayland " in cmdline or cmdline.startswith("kwin_wayland "):
                kwin_pid = entry.name
            values: dict[str, str] = {}
            for item in (entry / "environ").read_bytes().split(b"\0"):
                if b"=" in item:
                    key, value = item.split(b"=", 1)
                    values[key.decode("utf-8", errors="replace")] = value.decode("utf-8", errors="replace")
            if (values.get("DISPLAY") or values.get("WAYLAND_DISPLAY")) and values.get("XDG_RUNTIME_DIR"):
                candidates.append(values)
        except (OSError, StopIteration, ValueError):
            continue
    if not candidates:
        raise RuntimeError("No Plasma session environment was found for the test user.")
    env = candidates[0]
    wayland = env.get("XDG_SESSION_TYPE") == "wayland"
    required = (("WAYLAND_DISPLAY",) if wayland else ("DISPLAY",)) + ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise RuntimeError("Plasma session is missing: " + ", ".join(missing))
    env["QT_LINUX_ACCESSIBILITY_ALWAYS_ON"] = "1"
    env["QT_LOGGING_RULES"] = "*.debug=false"
    env["QT_QPA_PLATFORM"] = "wayland" if wayland else "xcb"
    if wayland and kwin_pid:
        env["KWIN_PID"] = kwin_pid
    if wayland:
        missing_tools = [name for name in ("selenium-webdriver-at-spi-inputsynth", "selenium-webdriver-at-spi-screenshotter") if not shutil.which(name)]
        if missing_tools:
            raise RuntimeError("Wayland automation requires KDE helper binaries in the guest: " + ", ".join(missing_tools))
    return env


def _qualify_qt_runtime() -> dict:
    """Fail closed on an incompatible guest before exposing the library to apps."""
    evidence = {"passed": False}
    try:
        payload = json.loads((WORK / "qt-runtime-request.json").read_text())
        manifest = payload["manifest"]
        if manifest.get("passed") is not True or manifest.get("exit_code") != 0:
            raise RuntimeError("Host corrected-runtime regression was not successful.")
        directory = WORK / "qt-runtime"
        library = directory / "libQt6Widgets.so.6.11.2"
        probe = directory / "qt-scroll-probe"
        for path, expected in ((library, manifest["runtime_sha256"]), (probe, payload["probe_sha256"])):
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError("Staged corrected-runtime artifact hash mismatch.")
        clean_env = {key: value for key, value in os.environ.items() if key not in {"LD_LIBRARY_PATH", "LD_PRELOAD"}}
        packages = subprocess.run(["/usr/bin/rpm", "-q", "qt6-qtbase", "qt6-qtbase-gui"],
                                  capture_output=True, text=True, env=clean_env, timeout=30, check=True).stdout.splitlines()
        evidence["guest_packages"] = packages
        if packages != payload["expected_packages"]:
            raise RuntimeError("Guest Qt Core/Gui packages do not match the corrected runtime: " + repr(packages))
        for name in ("Core", "Gui"):
            dependency = manifest["dependency_libraries"][name]
            path = Path(f"/usr/lib64/libQt6{name}.so.6.11.2")
            if hashlib.sha256(path.read_bytes()).hexdigest() != dependency["sha256"]:
                raise RuntimeError(f"Guest Qt{name} library hash does not match the corrected runtime.")
        link = directory / "libQt6Widgets.so.6"
        if link.is_symlink() and link.readlink() == Path(library.name):
            pass
        elif link.exists() or link.is_symlink():
            raise RuntimeError("Unexpected staged QtWidgets SONAME link.")
        else:
            link.symlink_to(library.name)
        probe.chmod(0o755)
        dependencies = subprocess.run(["/lib64/ld-linux-x86-64.so.2", "--library-path", str(directory), "--list", str(probe)],
                                      env=clean_env, capture_output=True, text=True, timeout=30, check=True).stdout
        evidence["probe_dependencies"] = dependencies
        if f"libQt6Widgets.so.6 => {link} " not in dependencies:
            raise RuntimeError("Guest regression probe did not resolve the isolated QtWidgets library.")
        for name in ("Core", "Gui"):
            if f"libQt6{name}.so.6 => /lib64/libQt6{name}.so.6 " not in dependencies and f"libQt6{name}.so.6 => /usr/lib64/libQt6{name}.so.6 " not in dependencies:
                raise RuntimeError(f"Guest regression probe resolved an unexpected Qt{name} library.")
        user_name = str(json.loads((WORK / "credentials.json").read_text())["user"])
        user = pwd.getpwnam(user_name)
        state = directory / "probe-state"
        state.mkdir(mode=0o700, exist_ok=True)
        os.chown(state, user.pw_uid, user.pw_gid)
        result = subprocess.run(["runuser", "--user", user_name, "--", "/usr/bin/env",
                                 f"LD_LIBRARY_PATH={directory}", "QT_QPA_PLATFORM=offscreen",
                                 "QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1", f"XDG_RUNTIME_DIR={state}",
                                 f"XDG_CONFIG_HOME={state}", f"XDG_DATA_HOME={state}", f"XDG_CACHE_HOME={state}", str(probe)],
                                env=clean_env, capture_output=True, text=True, timeout=30, check=False)
        evidence.update({"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
                         "runtime_sha256": manifest["runtime_sha256"], "runtime_library_dir": str(directory)})
        if result.returncode != 0:
            raise RuntimeError("Corrected Qt runtime native regression failed inside the guest.")
        evidence["passed"] = True
        return evidence
    except (OSError, KeyError, TypeError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        evidence["error"] = str(exc)
        raise RuntimeError(str(exc)) from exc
    finally:
        (WORK / "qt-runtime-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")


def _run_setup_fixture() -> int:
    """Keep native setup evidence independent of a desktop assertion failure."""
    target = WORK / "setup-transactions.log"
    with target.open("w", encoding="utf-8") as log:
        target.chmod(0o600)
        try:
            result = subprocess.run(["/usr/bin/python3", str(WORK / "e2e/tests/setup_transaction_fixture.py")],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=900, check=False)
            return result.returncode
        except (OSError, subprocess.SubprocessError) as error:
            log.write("Native setup fixture could not complete: " + type(error).__name__ + "\n")
            return 1


def _run_tests(phase: str = "normal") -> int:
    qt_runtime = _qualify_qt_runtime() if (WORK / "qt-runtime-request.json").exists() else None
    if phase == "after-reboot":
        subprocess.run(["/usr/bin/python3", str(WORK / "e2e/tests/offline_update_fixture.py"), "verify"],
                       timeout=300, check=True)
    credentials_path = WORK / "credentials.json"
    credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    user_name = str(credentials["user"])
    user = pwd.getpwnam(user_name)
    subprocess.run(["loginctl", "unlock-sessions"], timeout=30, check=True)
    session = _session_environment(user.pw_uid)
    os.chown(WORK, user.pw_uid, user.pw_gid)
    os.chmod(WORK, 0o700)
    for path in WORK.rglob("*"):
        os.chown(path, user.pw_uid, user.pw_gid)
    env = os.environ.copy()
    env.update(session)
    env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    env["PYTHONUNBUFFERED"] = "1"
    env.update({"HOME": user.pw_dir, "USER": user_name, "LOGNAME": user_name})
    junit = WORK / "junit.xml"
    log_path = WORK / "pytest.log"
    # Start tests in the graphical user's systemd manager, rather than the
    # serial login session, so pkexec uses KDE's actual graphical Polkit agent.
    exported = {key: env[key] for key in (
        "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "HOME", "USER", "LOGNAME",
        "QT_LINUX_ACCESSIBILITY_ALWAYS_ON", "QT_QPA_PLATFORM", "QT_LOGGING_RULES", "PYTHONUNBUFFERED",
    )}
    # Native tests import modules from the installed RPM's application tree.
    exported["PYTHONPATH"] = "/usr/lib/loofi-fedora-tweaks"
    exported["LOOFI_E2E_PHASE"] = phase
    if qt_runtime is not None:
        exported["LOOFI_E2E_QT_RUNTIME_DIR"] = qt_runtime["runtime_library_dir"]
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "KWIN_PID"):
        if session.get(name):
            exported[name] = session[name]
    if session.get("XAUTHORITY"):
        exported["XAUTHORITY"] = session["XAUTHORITY"]
    exported["LOOFI_E2E_CREDENTIALS_PATH"] = str(credentials_path)
    command = [
        "runuser", "--preserve-environment", "--user", user_name, "--",
        "systemd-run", "--user", "--wait", "--pipe", "--collect", "--quiet", "--unit=loofi-e2e-pytest",
        *[f"--setenv={key}={value}" for key, value in exported.items()],
        "/usr/bin/python3", "-m", "pytest", str(WORK / "e2e" / "tests" / "test_guest_reboot.py") if phase == "after-reboot" else str(WORK / "e2e" / "tests"),
        "-v", "-s", "--tb=short", "--maxfail=1", f"--junitxml={junit}",
    ]
    try:
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=45 * 60, check=False)
    finally:
        credentials_path.unlink(missing_ok=True)
    (WORK / "crash-diagnostics.json").write_text(json.dumps(_crash_diagnostics(), indent=2) + "\n")
    final_code = result.returncode
    setup_code = _run_setup_fixture() if phase == "before-reboot" else None
    if setup_code:
        final_code = final_code or setup_code
    if final_code == 0 and phase == "before-reboot":
        subprocess.run(["/usr/bin/python3", str(WORK / "e2e/tests/offline_update_fixture.py"), "prepare"],
                       timeout=600, check=True)
    subprocess.run(["chcon", "-R", "-t", "virt_qemu_ga_log_t", str(WORK)], timeout=30, check=True)
    summary = {"exit_code": final_code, "pytest_exit_code": result.returncode,
               "setup_fixture_exit_code": setup_code, "status": "passed" if final_code == 0 else "failed"}
    (WORK / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Desktop pytest exit {result.returncode}; native setup exit {setup_code}; overall exit {final_code}; see {log_path} and {junit}.")
    return final_code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", nargs=3, metavar=("RPM", "TEST_ARCHIVE", "CREDENTIALS"))
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--qualify-qt-runtime", action="store_true")
    parser.add_argument("--activate-offline", action="store_true")
    parser.add_argument("--phase", choices=("normal", "before-reboot", "after-reboot"), default="normal")
    args = parser.parse_args()
    marker = Path("/etc/loofi-e2e-guest")
    if not marker.is_file() or marker.read_text().strip() != "loofi-fedora-tweaks-e2e":
        raise RuntimeError("Refusing to run outside the dedicated E2E guest.")
    if subprocess.run(["systemd-detect-virt", "--vm"], capture_output=True, text=True, check=False).stdout.strip() not in {"qemu", "kvm"}:
        raise RuntimeError("The E2E runner requires QEMU virtualization.")
    WORK.mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.qualify_qt_runtime:
        _qualify_qt_runtime()
        print("Corrected Qt runtime guest compatibility and native regression passed.")
        return 0
    if args.install:
        return _run_install(Path(args.install[0]), Path(args.install[1]), Path(args.install[2]))
    if args.activate_offline:
        with (WORK / "offline-activation.log").open("a") as log:
            subprocess.Popen(["/usr/bin/python3", str(WORK / "e2e/tests/offline_update_fixture.py"), "activate"],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        return 0
    if args.run:
        return _run_tests(args.phase)
    parser.error("choose --install or --run")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print(f"E2E guest setup failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
