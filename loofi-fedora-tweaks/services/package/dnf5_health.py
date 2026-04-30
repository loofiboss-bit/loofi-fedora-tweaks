"""Fedora 44 DNF5 and repository health diagnostics.

All probes are read-only and intended for CLI, GUI, and support-bundle use.
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List

from services.system.system import cached_which
from utils.log import get_logger

logger = get_logger(__name__)


@dataclass
class RepoRisk:
    """A masked repository risk finding."""

    repo_id: str
    source: str
    risk: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "repo_id": self.repo_id,
            "source": self.source,
            "risk": self.risk,
            "reason": self.reason,
        }


@dataclass
class DNF5HealthReport:
    """Read-only package manager health report."""

    package_manager: str = "Unknown"
    dnf5_available: bool = False
    dnf_available: bool = False
    packagekit_active: bool = False
    packagekit_detail: str = "Unknown"
    dnf_locked: bool = False
    lock_detail: str = ""
    repo_probe_ok: bool = True
    repo_probe_detail: str = ""
    repo_risks: List[RepoRisk] = field(default_factory=list)
    raw: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "package_manager": self.package_manager,
            "dnf5_available": self.dnf5_available,
            "dnf_available": self.dnf_available,
            "packagekit_active": self.packagekit_active,
            "packagekit_detail": self.packagekit_detail,
            "dnf_locked": self.dnf_locked,
            "lock_detail": self.lock_detail,
            "repo_probe_ok": self.repo_probe_ok,
            "repo_probe_detail": self.repo_probe_detail,
            "repo_risks": [risk.to_dict() for risk in self.repo_risks],
            "raw": dict(self.raw),
        }


class DNF5HealthService:
    """Read-only DNF5 and repository diagnostics."""

    REPO_PATHS = (
        "/etc/yum.repos.d/*.repo",
        "/etc/dnf/repos.d/*.repo",
    )

    @staticmethod
    def _run(cmd: List[str], timeout: int = 12) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
            logger.debug("Package health probe failed for %s: %s", cmd, exc)
            return None

    @staticmethod
    def _mask_repo_text(text: str) -> str:
        masked = re.sub(r"(?i)(token|password|secret|key)=([^\s&]+)", r"\1=<masked>", text)
        masked = re.sub(r"/home/[^/\\s]+", "/home/<user>", masked)
        masked = re.sub(r"copr:[^:\s]+:[^:\s]+:", "copr:<host>:<user>:", masked)
        return masked[:2000]

    @classmethod
    def _scan_repo_files(cls) -> List[RepoRisk]:
        risks: List[RepoRisk] = []
        seen: set[str] = set()
        for pattern in cls.REPO_PATHS:
            for path in sorted(glob.glob(pattern)):
                try:
                    content = open(path, "r", encoding="utf-8", errors="replace").read()
                except OSError as exc:
                    logger.debug("Failed to read repo file %s: %s", path, exc)
                    continue

                current_repo = os.path.basename(path)
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("[") and stripped.endswith("]"):
                        current_repo = stripped.strip("[]")
                    lowered = stripped.lower()
                    reason = ""
                    risk = "info"
                    if "copr" in lowered:
                        risk = "warning"
                        reason = "Third-party COPR repository can break major-version upgrades."
                    elif "rpmfusion" in lowered or "rpm fusion" in lowered:
                        risk = "info"
                        reason = "RPM Fusion is common on Fedora KDE but should be checked before upgrades."
                    elif "baseurl=" in lowered and "download.example" not in lowered and "fedoraproject.org" not in lowered:
                        risk = "info"
                        reason = "Non-Fedora baseurl detected."

                    if reason:
                        key = f"{current_repo}:{reason}"
                        if key in seen:
                            continue
                        seen.add(key)
                        risks.append(
                            RepoRisk(
                                repo_id=cls._mask_repo_text(current_repo),
                                source=cls._mask_repo_text(path),
                                risk=risk,
                                reason=reason,
                            )
                        )
        return risks

    @classmethod
    def _packagekit_status(cls) -> tuple[bool, str]:
        result = cls._run(["systemctl", "is-active", "packagekit.service"], timeout=5)
        if result is None:
            return False, "Unable to query PackageKit"
        detail = (result.stdout or result.stderr).strip() or f"exit={result.returncode}"
        return result.returncode == 0 and detail == "active", detail

    @classmethod
    def _lock_status(cls) -> tuple[bool, str]:
        paths = [
            "/var/lib/dnf/metadata_lock.pid",
            "/var/lib/dnf/lock",
            "/var/lib/rpm/.rpm.lock",
        ]
        existing = [path for path in paths if os.path.exists(path)]
        result = cls._run(["fuser"] + paths, timeout=5) if cached_which("fuser") else None
        if result and result.returncode == 0:
            return True, cls._mask_repo_text(result.stdout or result.stderr)
        if existing:
            return False, "Lock files present but no active lock holder detected: " + ", ".join(existing)
        return False, "No DNF/RPM lock holders detected"

    @classmethod
    def _repo_probe(cls, manager: str) -> tuple[bool, str]:
        if manager == "Unknown":
            return False, "No DNF-compatible package manager found"
        args = ["repolist", "--enabled"]
        result = cls._run([manager] + args, timeout=20)
        if result is None:
            return False, f"{manager} repolist probe failed"
        output = (result.stdout or result.stderr).strip()
        return result.returncode == 0, cls._mask_repo_text(output or f"exit={result.returncode}")

    @classmethod
    def collect(cls) -> DNF5HealthReport:
        dnf5_path = cached_which("dnf5")
        dnf_path = cached_which("dnf")
        manager = "dnf5" if dnf5_path else ("dnf" if dnf_path else "Unknown")
        packagekit_active, packagekit_detail = cls._packagekit_status()
        locked, lock_detail = cls._lock_status()
        repo_ok, repo_detail = cls._repo_probe(manager)

        return DNF5HealthReport(
            package_manager=manager,
            dnf5_available=dnf5_path is not None,
            dnf_available=dnf_path is not None,
            packagekit_active=packagekit_active,
            packagekit_detail=packagekit_detail,
            dnf_locked=locked,
            lock_detail=lock_detail,
            repo_probe_ok=repo_ok,
            repo_probe_detail=repo_detail,
            repo_risks=cls._scan_repo_files(),
            raw={
                "dnf5_path": dnf5_path or "",
                "dnf_path": dnf_path or "",
            },
        )
