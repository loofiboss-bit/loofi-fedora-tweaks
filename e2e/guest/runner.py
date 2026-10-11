#!/usr/bin/python3
"""Guest-side runner invoked through the authenticated guest serial console."""

from __future__ import annotations

import argparse
import json
import os
import pwd
import subprocess
import sys
import tarfile
from pathlib import Path


WORK = Path("/var/tmp/loofi-e2e")


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
    print("RPM installed and E2E tests staged in the guest.")
    return 0


def _session_environment(uid: int) -> dict[str, str]:
    """Read display/session values from the logged-in Plasma processes."""
    candidates: list[dict[str, str]] = []
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            status = (entry / "status").read_text(encoding="utf-8", errors="replace")
            uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
            if int(uid_line.split()[1]) != uid:
                continue
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", errors="replace").lower()
            if not any(name in cmdline for name in ("plasmashell", "kwin_x11", "startplasma-x11", "plasma-session")):
                continue
            values: dict[str, str] = {}
            for item in (entry / "environ").read_bytes().split(b"\0"):
                if b"=" in item:
                    key, value = item.split(b"=", 1)
                    values[key.decode("utf-8", errors="replace")] = value.decode("utf-8", errors="replace")
            if values.get("DISPLAY") and values.get("XDG_RUNTIME_DIR"):
                candidates.append(values)
        except (OSError, StopIteration, ValueError):
            continue
    if not candidates:
        raise RuntimeError("No Plasma X11 session environment was found for the test user.")
    env = candidates[0]
    required = ("DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise RuntimeError("Plasma session is missing: " + ", ".join(missing))
    env["QT_LINUX_ACCESSIBILITY_ALWAYS_ON"] = "1"
    env["QT_QPA_PLATFORM"] = "xcb"
    return env


def _run_tests() -> int:
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
    env["PYTHONUNBUFFERED"] = "1"
    env.update({"HOME": user.pw_dir, "USER": user_name, "LOGNAME": user_name})
    junit = WORK / "junit.xml"
    log_path = WORK / "pytest.log"
    # Start tests in the graphical user's systemd manager, rather than the
    # serial login session, so pkexec uses KDE's actual graphical Polkit agent.
    exported = {key: env[key] for key in (
        "DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "HOME", "USER", "LOGNAME",
        "QT_LINUX_ACCESSIBILITY_ALWAYS_ON", "QT_QPA_PLATFORM", "PYTHONUNBUFFERED",
    )}
    if session.get("XAUTHORITY"):
        exported["XAUTHORITY"] = session["XAUTHORITY"]
    exported["LOOFI_E2E_CREDENTIALS_PATH"] = str(credentials_path)
    command = [
        "runuser", "--preserve-environment", "--user", user_name, "--",
        "systemd-run", "--user", "--wait", "--pipe", "--collect", "--quiet", "--unit=loofi-e2e-pytest",
        *[f"--setenv={key}={value}" for key, value in exported.items()],
        "/usr/bin/python3", "-m", "pytest", str(WORK / "e2e" / "tests"),
        "-v", "-s", "--tb=short", f"--junitxml={junit}",
    ]
    try:
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=45 * 60, check=False)
    finally:
        credentials_path.unlink(missing_ok=True)
    subprocess.run(["chcon", "-R", "-t", "virt_qemu_ga_log_t", str(WORK)], timeout=30, check=True)
    summary = {"exit_code": result.returncode, "status": "passed" if result.returncode == 0 else "failed"}
    (WORK / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"pytest finished with exit code {result.returncode}; see {log_path} and {junit}.")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", nargs=3, metavar=("RPM", "TEST_ARCHIVE", "CREDENTIALS"))
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    marker = Path("/etc/loofi-e2e-guest")
    if not marker.is_file() or marker.read_text().strip() != "loofi-fedora-tweaks-e2e":
        raise RuntimeError("Refusing to run outside the dedicated E2E guest.")
    if subprocess.run(["systemd-detect-virt", "--vm"], capture_output=True, text=True, check=False).stdout.strip() not in {"qemu", "kvm"}:
        raise RuntimeError("The E2E runner requires QEMU virtualization.")
    WORK.mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.install:
        return _run_install(Path(args.install[0]), Path(args.install[1]), Path(args.install[2]))
    if args.run:
        return _run_tests()
    parser.error("choose --install or --run")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print(f"E2E guest setup failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
