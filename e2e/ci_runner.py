"""Prepare or explicitly approve a repository-scoped GitHub Actions runner.

Nothing is installed unless --approve-host-change is supplied after human
approval. This is separate from the guest-only test lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

from e2e.vm import VMError, _default_data_root, preflight


REPOSITORY = "loofiboss-bit/loofi-fedora-tweaks"
RUNNER_NAME = "loofi-fedora-tweaks-vm"
UNIT = "loofi-fedora-tweaks-ci-runner.service"


def _run(args: list[str], *, cwd: Path | None = None, env: dict | None = None, timeout: int = 60) -> str:
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        detail = result.stderr.strip()
        if env and env.get("ACTIONS_RUNNER_INPUT_TOKEN"):
            detail = detail.replace(env["ACTIONS_RUNNER_INPUT_TOKEN"], "[redacted]")
        raise VMError(f"CI runner command failed: {args[0]}: {detail}")
    return result.stdout


def _quote(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise VMError("Refusing a line break in the user service configuration.")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def plan() -> dict:
    data = _default_data_root().parent
    return {
        "repository": REPOSITORY,
        "runner_name": RUNNER_NAME,
        "labels": ["self-hosted", "Linux", "X64", "loofi-vm-e2e"],
        "install_directory": str(data / "ci-runner"),
        "user_service": str(Path.home() / ".config/systemd/user" / UNIT),
        "host_changes": ["Download and extract the official GitHub runner with SHA-256 verification",
                         "Register a runner for this repository using the signed-in gh account",
                         "Create, enable and start a systemd user service",
                         "Allow the runner's standard updates in its private install directory"],
        "system_packages_installed": [],
        "requires_explicit_host_approval": True,
    }


def install() -> None:
    preflight()
    if shutil.which("gh") is None:
        raise VMError("gh is missing; installing it requires separate host approval.")
    details = plan()
    root = Path(details["install_directory"])
    marker = root / "loofi-runner.json"
    expected = {"repository": REPOSITORY, "name": RUNNER_NAME, "directory": str(root)}
    if root.exists():
        if root.is_symlink() or marker.is_symlink() or not marker.is_file() or json.loads(marker.read_text()) != expected:
            raise VMError("The runner directory is not owned by this setup; refusing to overwrite it.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    marker.write_text(json.dumps(expected, indent=2) + "\n")
    marker.chmod(0o600)
    if not (root / ".runner").is_file():
        release = json.loads(_run(["gh", "api", "repos/actions/runner/releases/latest"]))
        assets = [asset for asset in release["assets"] if re.fullmatch(r"actions-runner-linux-x64-[0-9.]+\.tar\.gz", asset["name"])]
        if len(assets) != 1:
            raise VMError("The official release did not contain exactly one Linux x64 runner.")
        asset = assets[0]
        digest = asset.get("digest", "")
        url = asset["browser_download_url"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or not url.startswith("https://github.com/actions/runner/releases/download/"):
            raise VMError("The runner asset has no verified official URL and SHA-256 digest.")
        archive = root / "runner-download.tar.gz"
        hasher = hashlib.sha256()
        written = 0
        try:
            with urllib.request.urlopen(url, timeout=60) as response, archive.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    written += len(chunk)
                    if written > asset["size"]:
                        raise VMError("The runner download exceeded its published size.")
                    hasher.update(chunk)
                    output.write(chunk)
            if written != asset["size"] or hasher.hexdigest() != digest.removeprefix("sha256:"):
                raise VMError("The runner archive did not match its published size and checksum.")
            with tarfile.open(archive, "r:gz") as bundle:
                bundle.extractall(root, filter="data")
        finally:
            archive.unlink(missing_ok=True)
        # Fail clearly on native dependencies; never invoke installdependencies.sh.
        _run([str(root / "bin/Runner.Listener"), "--version"], cwd=root)
        credential = json.loads(_run(["gh", "api", "--method", "POST", f"repos/{REPOSITORY}/actions/runners/registration-token"]))
        env = os.environ.copy()
        env["ACTIONS_RUNNER_INPUT_TOKEN"] = credential["token"]
        _run([str(root / "config.sh"), "--unattended", "--url", f"https://github.com/{REPOSITORY}",
              "--name", RUNNER_NAME, "--labels", "loofi-vm-e2e", "--work", "_work"], cwd=root, env=env, timeout=180)
        env.pop("ACTIONS_RUNNER_INPUT_TOKEN", None)
    settings = {key.lower(): value for key, value in json.loads((root / ".runner").read_text(encoding="utf-8-sig")).items()}
    if settings.get("githuburl", "").rstrip("/") != f"https://github.com/{REPOSITORY}" or settings.get("agentname") != RUNNER_NAME:
        raise VMError("The registered runner belongs to a different repository or name; refusing to start it.")
    service = Path(details["user_service"])
    # WorkingDirectory is a single path setting; systemd does not unquote it.
    working_directory = str(root).replace("%", "%%")
    runner_path = ":".join(dict.fromkeys([
        str(Path(shutil.which("just") or "/usr/bin/just").parent),
        str(Path.home() / ".local/bin"), "/usr/local/bin", "/usr/bin", "/usr/sbin",
    ]))
    body = ("[Unit]\nDescription=Loofi Fedora Tweaks trusted VM CI runner\n\n[Service]\nType=simple\n"
            f"WorkingDirectory={working_directory}\nExecStart={_quote(str(root / 'run.sh'))}\n"
            f"Environment={_quote('PATH=' + runner_path)}\n"
            f"Environment={_quote('XDG_DATA_HOME=' + str(_default_data_root().parents[1]))}\n"
            "Restart=on-failure\nRestartSec=10\n\n[Install]\nWantedBy=default.target\n")
    if service.is_symlink():
        raise VMError("The existing user service is a symlink; refusing to overwrite it.")
    if service.exists() and "Loofi Fedora Tweaks trusted VM CI runner" not in service.read_text():
        raise VMError("The existing user service is unrelated; refusing to overwrite it.")
    service.parent.mkdir(parents=True, exist_ok=True)
    service.write_text(body)
    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "enable", "--now", UNIT])
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        runners = json.loads(_run(["gh", "api", f"repos/{REPOSITORY}/actions/runners"]))["runners"]
        if any(item["name"] == RUNNER_NAME and item["status"] == "online" for item in runners):
            print(f"Repository runner {RUNNER_NAME} is online; the user service is enabled.")
            return
        time.sleep(3)
    raise VMError(f"The runner was registered but is not confirmed online. Inspect: journalctl --user -u {UNIT}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-host-change", action="store_true", help="Install/register/start only after explicit human approval")
    args = parser.parse_args()
    if not args.approve_host_change:
        print(json.dumps(plan(), indent=2))
        return 0
    try:
        install()
        return 0
    except (VMError, OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print(f"CI runner setup failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
