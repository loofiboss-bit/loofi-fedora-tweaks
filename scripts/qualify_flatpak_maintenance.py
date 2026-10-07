#!/usr/bin/env python3
"""Exercise real libflatpak cleanup using synthetic, disposable installations.

The default user case uses a temporary HOME and XDG directories. System and
named installation cases are permitted only inside a disposable container.
No real application is launched or downloaded.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "loofi-fedora-tweaks"
APP_ID = "org.loofi.Care.App"
PLATFORM_ID = "org.loofi.Care.Platform"
UNUSED_ID = "org.loofi.Care.Unused"
PINNED_ID = "org.loofi.Care.Pinned"


def run(vector: list[str], env: dict[str, str], *, success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(vector, env=env, capture_output=True, text=True, timeout=45, check=False)
    if success and result.returncode:
        raise RuntimeError(f"Fixture command failed ({result.returncode}): {vector[:3]}: {result.stderr[-1000:]}")
    return result


def export_fixture(root: Path, env: dict[str, str], identifier: str, *, runtime: bool = True, eol: bool = False) -> str:
    architecture = platform.machine()
    build = root / identifier
    (build / "files").mkdir(parents=True)
    (build / "files" / "fixture.txt").write_text(identifier, encoding="utf-8")
    kind = "Runtime" if runtime else "Application"
    reference = f"{PLATFORM_ID}/{architecture}/stable"
    (build / "metadata").write_text(
        f"[{kind}]\nname={identifier}\nruntime={reference}\nsdk={reference}\n", encoding="utf-8",
    )
    if not runtime:
        (build / "export").mkdir()
    vector = ["flatpak", "build-export", "--files=files", "--disable-sandbox"]
    if runtime:
        vector.append("--runtime")
    if eol:
        vector.append("--end-of-life=Local fixture support ended")
    run([*vector, str(root / "repo"), str(build), "stable"], env)
    return f"{'runtime' if runtime else 'app'}/{identifier}/{architecture}/stable"


def qualify(installation: str) -> dict[str, object]:
    if installation != "user" and not Path("/run/.containerenv").exists():
        raise ValueError("Shared-installation fixtures may only run inside a disposable Podman container.")
    with tempfile.TemporaryDirectory(prefix="loofi-care-integration-") as directory:
        root = Path(directory)
        remote = "care-" + root.name.rsplit("-", 1)[-1]
        home = root / "home"
        home.mkdir()
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PYTHONPATH"] = str(SOURCE)
        env["LOOFI_IPC_MODE"] = "disabled"
        for key, name in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                          ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state"),
                          ("XDG_RUNTIME_DIR", "runtime")):
            path = home / name
            path.mkdir(mode=0o700)
            env[key] = str(path)
        env.pop("DBUS_SESSION_BUS_ADDRESS", None)
        refs = {
            "used": export_fixture(root, env, PLATFORM_ID, eol=True),
            "unused": export_fixture(root, env, UNUSED_ID),
            "pinned": export_fixture(root, env, PINNED_ID),
            "app": export_fixture(root, env, APP_ID, runtime=False, eol=True),
        }
        if installation not in {"user", "system"}:
            config = Path("/etc/flatpak/installations.d/care-test.conf")
            if not config.is_file():
                raise ValueError("Prepare the named fixture installation in the disposable container first.")
        scope = f"--{installation}" if installation in {"user", "system"} else f"--installation={installation}"
        run(["flatpak", scope, "remote-add", "--no-gpg-verify", remote, (root / "repo").as_uri()], env)
        for ref in refs.values():
            run(["flatpak", scope, "install", "--noninteractive", remote, ref], env)
        for ref in (refs["used"], refs["unused"]):
            run(["flatpak", scope, "pin", "--remove", ref], env)
        app_data = home / ".var" / "app" / APP_ID / "sentinel"
        app_data.parent.mkdir(parents=True)
        app_data.write_text("Preserve application data", encoding="utf-8")
        helper = ROOT / "scripts" / "loofi-flatpak-maintenance"

        def inspect() -> dict:
            # The service supplies the fixed helper vector and bounded decoder.
            code = (
                "import json; from services.software.flatpak_maintenance import FlatpakMaintenanceService; "
                f"print(json.dumps(FlatpakMaintenanceService().unused({installation!r}).to_dict()))"
            )
            return json.loads(run([sys.executable, "-c", code], env).stdout)

        snapshot = inspect()
        if not snapshot.get("available"):
            raise AssertionError("Real libflatpak inspection is unavailable: " + str(snapshot.get("error")))
        unused_refs = {entry["ref"] for entry in snapshot["refs"]}
        if unused_refs != {refs["unused"]}:
            raise AssertionError(f"Dependency/pinning inspection returned an unexpected set: {unused_refs}")
        run(["flatpak", scope, "pin", refs["unused"]], env)
        command = [str(helper), "apply", "--installation", installation,
                   "--snapshot-digest", snapshot["digest"], "--ref", refs["unused"]]
        drift = run(command, env, success=False)
        if drift.returncode == 0:
            raise AssertionError("Cleanup accepted an obsolete review after pinning changed")
        run(["flatpak", scope, "pin", "--remove", refs["unused"]], env)
        snapshot = inspect()
        command[command.index("--snapshot-digest") + 1] = snapshot["digest"]
        code = (
            "import json; from core.actions.operation_controller import OperationController; "
            "outcome=OperationController().execute('remove-unused-flatpaks', "
            f"{{'installation':{installation!r},'refs':[{refs['unused']!r}],'snapshot_digest':{snapshot['digest']!r}}}, "
            "confirmed=True,accept_no_rollback=True); "
            "print(json.dumps(outcome.to_dict())); raise SystemExit(0 if outcome.status == 'succeeded' else 1)"
        )
        action_outcome = json.loads(run([sys.executable, "-c", code], env).stdout)
        if action_outcome["run"]["verification_result"]["data"]["removed_refs"] != [refs["unused"]]:
            raise AssertionError("Action Center did not persist the independent removal observation")
        after = inspect()
        remaining = {entry["ref"] for entry in after["installed"]}
        expected = set(refs.values()) - {refs["unused"]}
        if remaining != expected:
            raise AssertionError(f"Cleanup changed unselected refs: {remaining}")
        if app_data.read_text(encoding="utf-8") != "Preserve application data":
            raise AssertionError("Cleanup changed application data")
        code = (
            "import json; from services.software.flatpak_maintenance import FlatpakMaintenanceService; "
            f"print(json.dumps(FlatpakMaintenanceService().details({refs['app']!r}, {installation!r}).to_dict()))"
        )
        details = json.loads(run([sys.executable, "-c", code], env).stdout)
        cross_installation_protected = None
        if installation != "user":
            run(["flatpak", "--user", "remote-add", "--no-gpg-verify", remote, (root / "repo").as_uri()], env)
            run(["flatpak", "--user", "install", "--noninteractive", "--no-deps", remote, refs["app"]], env)
            run(["flatpak", scope, "uninstall", "--noninteractive", "--no-related", refs["app"]], env)
            protected = inspect()
            if refs["used"] in {entry["ref"] for entry in protected["refs"]}:
                raise AssertionError("Shared cleanup offered the invoking user's active runtime dependency")
            cross_installation_protected = True
        return {"installation": installation, "pinning_and_dependencies": "passed",
                "review_drift": "blocked", "selected_runtime_removed": True,
                "remaining_refs_preserved": len(remaining), "app_data_preserved": True,
                "action_center_status": action_outcome["status"],
                "cross_installation_dependency_protected": cross_installation_protected, "details": details}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installation", default="user", choices=("user", "system", "care-fixture"))
    args = parser.parse_args()
    try:
        print(json.dumps(qualify(args.installation), indent=2))
    except (OSError, ValueError, RuntimeError, AssertionError, subprocess.TimeoutExpired) as exc:
        print(f"Care qualification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
