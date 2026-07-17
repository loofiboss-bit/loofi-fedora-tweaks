"""Regression tests for the commit-bound SRPM builder."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build_srpm.sh"


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _create_checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    (checkout / "loofi-fedora-tweaks").mkdir()
    shutil.copy2(BUILD_SCRIPT, checkout / "scripts" / "build_srpm.sh")
    (checkout / "loofi-fedora-tweaks" / "version.py").write_text(
        '__version__ = "14.0.0"\n',
        encoding="utf-8",
    )
    (checkout / "loofi-fedora-tweaks.spec").write_text(
        "Name: loofi-fedora-tweaks\nVersion: 14.0.0\nRelease: 1%{?dist}\n",
        encoding="utf-8",
    )
    (checkout / "tracked-marker.txt").write_text("committed\n", encoding="utf-8")

    _run("git", "init", "-q", cwd=checkout)
    _run("git", "config", "user.name", "Test User", cwd=checkout)
    _run("git", "config", "user.email", "test@example.invalid", cwd=checkout)
    _run("git", "add", ".", cwd=checkout)
    _run("git", "commit", "-qm", "fixture", cwd=checkout)
    return checkout


def _stub_rpmbuild(bin_dir: Path) -> None:
    _write_executable(
        bin_dir / "rpmbuild",
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "topdir=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ $1 == --define ]]; then\n"
        "    shift\n"
        "    topdir=${1#_topdir }\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "tarball=$topdir/SOURCES/loofi-fedora-tweaks-14.0.0.tar.gz\n"
        "tar -xOf \"$tarball\" loofi-fedora-tweaks-14.0.0/tracked-marker.txt > archived-marker.txt\n"
        "mkdir -p \"$topdir/SRPMS\"\n"
        "touch \"$topdir/SRPMS/loofi-fedora-tweaks-14.0.0-1.fc44.src.rpm\"\n",
    )


def test_build_srpm_archives_verified_head_not_dirty_worktree(tmp_path):
    checkout = _create_checkout(tmp_path)
    head = _run("git", "rev-parse", "HEAD", cwd=checkout).stdout.strip()
    (checkout / "tracked-marker.txt").write_text("dirty\n", encoding="utf-8")
    (checkout / "loofi-fedora-tweaks" / "version.py").write_text(
        '__version__ = "99.0.0"\n',
        encoding="utf-8",
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub_rpmbuild(bin_dir)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["GITHUB_SHA"] = head

    result = subprocess.run(
        ["/bin/bash", "scripts/build_srpm.sh"],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert (checkout / "archived-marker.txt").read_text(encoding="utf-8") == "committed\n"
    assert (checkout / "rpmbuild" / "SRPMS" / "loofi-fedora-tweaks-14.0.0-1.fc44.src.rpm").exists()
    assert "Verified source commit" in result.stdout
    script_text = (checkout / "scripts" / "build_srpm.sh").read_text(encoding="utf-8")
    assert "curl" not in script_text
    assert "/archive/v" not in script_text


def test_build_srpm_rejects_checkout_sha_mismatch_before_rpmbuild(tmp_path):
    checkout = _create_checkout(tmp_path)
    expected = _run("git", "rev-parse", "HEAD", cwd=checkout).stdout.strip()
    (checkout / "second.txt").write_text("second\n", encoding="utf-8")
    _run("git", "add", "second.txt", cwd=checkout)
    _run("git", "commit", "-qm", "second", cwd=checkout)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "rpmbuild-called"
    _write_executable(
        bin_dir / "rpmbuild",
        f"#!/bin/bash\ntouch '{marker}'\nexit 0\n",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["GITHUB_SHA"] = expected

    result = subprocess.run(
        ["/bin/bash", "scripts/build_srpm.sh"],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "does not match expected source commit" in result.stderr
    assert not marker.exists()
