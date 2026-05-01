"""Release readiness diagnostics for supported Fedora KDE targets."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from services.desktop.kde44 import KDE44DesktopInfo, KDE44DesktopService
from services.package.dnf5_health import DNF5HealthReport, DNF5HealthService
from services.security.secureboot import SecureBootManager
from services.system.system import SystemManager, cached_which
from utils.log import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReleaseTarget:
    """Fedora release target metadata used by readiness probes."""

    key: str
    label: str
    fedora_version: str
    supported: bool
    preview: bool = False
    compatible_versions: tuple[str, ...] = ()
    min_plasma: tuple[int, ...] = (6, 0)
    min_qt: tuple[int, ...] = (6, 6)
    beta_target: str = ""
    final_target: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "fedora_version": self.fedora_version,
            "supported": self.supported,
            "preview": self.preview,
            "compatible_versions": list(self.compatible_versions),
            "min_plasma": ".".join(str(part) for part in self.min_plasma),
            "min_qt": ".".join(str(part) for part in self.min_qt),
            "beta_target": self.beta_target,
            "final_target": self.final_target,
        }


TARGETS: Dict[str, ReleaseTarget] = {
    "44": ReleaseTarget(
        key="44",
        label="Fedora KDE 44",
        fedora_version="44",
        supported=True,
        compatible_versions=("43",),
    ),
    "45-preview": ReleaseTarget(
        key="45-preview",
        label="Fedora KDE 45 Preview",
        fedora_version="45",
        supported=False,
        preview=True,
        compatible_versions=("44",),
        beta_target="2026-09-15",
        final_target="2026-10-20",
    ),
}


@dataclass
class ReadinessRecommendation:
    """Action metadata attached to a readiness finding."""

    title: str
    description: str
    command_preview: Optional[List[str]] = None
    risk_level: str = "info"
    reversible: bool = True
    rollback_hint: str = "No system changes are made by this recommendation."
    manual_only: bool = True
    docs_link: str = ""

    def to_dict(self) -> Dict[str, object]:
        data: Dict[str, object] = {
            "title": self.title,
            "description": self.description,
            "risk_level": self.risk_level,
            "reversible": self.reversible,
            "rollback_hint": self.rollback_hint,
            "manual_only": self.manual_only,
        }
        if self.command_preview:
            data["command_preview"] = list(self.command_preview)
        if self.docs_link:
            data["docs_link"] = self.docs_link
        return data


@dataclass
class ReadinessCheck:
    """Single release readiness finding."""

    id: str
    title: str
    category: str
    status: str
    severity: str
    summary: str
    beginner_guidance: str
    advanced_detail: str = ""
    command_preview: Optional[List[str]] = None
    risk_level: str = "info"
    rollback_hint: str = "No changes are made by this readiness check."
    recommendation: Optional[ReadinessRecommendation] = None

    def to_dict(self, *, advanced: bool = True) -> Dict[str, object]:
        data: Dict[str, object] = {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "status": self.status,
            "severity": self.severity,
            "summary": self.summary,
            "beginner_guidance": self.beginner_guidance,
            "risk_level": self.risk_level,
            "rollback_hint": self.rollback_hint,
        }
        if self.command_preview:
            data["command_preview"] = list(self.command_preview)
        if self.recommendation:
            data["recommendation"] = self.recommendation.to_dict()
        if advanced:
            data["advanced_detail"] = self.advanced_detail
        return data


@dataclass
class ReleaseReadinessReport:
    """Aggregated release readiness report."""

    target: str
    generated_at: float
    score: int
    status: str
    summary: str
    checks: List[ReadinessCheck] = field(default_factory=list)
    desktop: Optional[KDE44DesktopInfo] = None
    package: Optional[DNF5HealthReport] = None
    target_metadata: ReleaseTarget = field(default_factory=lambda: TARGETS["44"])

    def to_dict(self, *, advanced: bool = True) -> Dict[str, object]:
        data: Dict[str, object] = {
            "target": self.target,
            "target_metadata": self.target_metadata.to_dict(),
            "generated_at": self.generated_at,
            "score": self.score,
            "status": self.status,
            "summary": self.summary,
            "checks": [check.to_dict(advanced=advanced) for check in self.checks],
        }
        if advanced:
            data["desktop"] = self.desktop.to_dict() if self.desktop else {}
            data["package"] = self.package.to_dict() if self.package else {}
        return data

    def support_summary(self) -> str:
        warnings = [check for check in self.checks if check.severity == "warning"]
        errors = [check for check in self.checks if check.severity in {"error", "critical"}]
        lines = [
            f"{self.target}: {self.score}/100 ({self.status})",
            f"{len(warnings)} warning(s), {len(errors)} error(s)",
        ]
        for check in warnings + errors:
            lines.append(f"- {check.title}: {check.summary}")
        return "\n".join(lines)


class ReleaseReadiness:
    """Read-only release readiness aggregator."""

    TARGET_KEY = "44"
    TARGET = TARGETS["44"].label
    FEDORA_COMPAT_VERSION = "43"
    FEDORA_TARGET_VERSION = "44"

    @staticmethod
    def get_target(target_key: str = "44") -> ReleaseTarget:
        return TARGETS.get(target_key, TARGETS["44"])

    @staticmethod
    def list_targets() -> List[ReleaseTarget]:
        return list(TARGETS.values())

    @staticmethod
    def _read_file(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read().strip()
        except OSError as exc:
            logger.debug("Failed to read %s: %s", path, exc)
            return ""

    @staticmethod
    def _run(cmd: List[str], timeout: int = 10) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
            logger.debug("Readiness probe failed for %s: %s", cmd, exc)
            return None

    @classmethod
    def _os_release(cls) -> Dict[str, str]:
        data: Dict[str, str] = {}
        text = cls._read_file("/etc/os-release")
        for line in text.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key] = value.strip().strip('"')
        return data

    @staticmethod
    def _version_tuple(version: str) -> tuple[int, ...]:
        return tuple(int(part) for part in re.findall(r"\d+", version)[:3]) if version else ()

    @classmethod
    def _fedora_version_check(
        cls,
        os_release: Dict[str, str],
        target: ReleaseTarget | None = None,
    ) -> ReadinessCheck:
        target = target or cls.get_target(cls.TARGET_KEY)
        version = os_release.get("VERSION_ID", "")
        pretty = os_release.get("PRETTY_NAME", "Unknown Fedora release")
        if version == target.fedora_version:
            return ReadinessCheck(
                id="fedora-version",
                title="Fedora Version",
                category="system",
                status="pass",
                severity="info",
                summary=f"{pretty} matches the supported {target.label} target.",
                beginner_guidance="You are on the release this readiness profile checks.",
                advanced_detail=json.dumps(os_release, indent=2, sort_keys=True),
                command_preview=["cat", "/etc/os-release"],
            )
        if version in target.compatible_versions:
            status = "info" if target.preview else "warning"
            severity = "info" if target.preview else "warning"
            return ReadinessCheck(
                id="fedora-version",
                title="Fedora Version",
                category="system",
                status=status,
                severity=severity,
                summary=(
                    f"{pretty} is compatible preview context for {target.label}."
                    if target.preview
                    else f"{pretty} is best-effort compatible context for {target.label}."
                ),
                beginner_guidance=(
                    f"{target.label} is a preview profile; current Fedora {version} is acceptable for planning."
                    if target.preview
                    else f"The app should still work, but {target.label} is the supported target."
                ),
                advanced_detail=json.dumps(os_release, indent=2, sort_keys=True),
                command_preview=["cat", "/etc/os-release"],
            )
        if version:
            return ReadinessCheck(
                id="fedora-version",
                title="Fedora Version",
                category="system",
                status="warning",
                severity="warning",
                summary=f"{pretty} is outside the {target.label} readiness target.",
                beginner_guidance="Use caution. Some release-specific guidance may not apply exactly.",
                advanced_detail=json.dumps(os_release, indent=2, sort_keys=True),
                command_preview=["cat", "/etc/os-release"],
            )
        return ReadinessCheck(
            id="fedora-version",
            title="Fedora Version",
            category="system",
            status="error",
            severity="error",
            summary="Unable to identify the Fedora version.",
            beginner_guidance=f"The readiness center cannot confirm this system against {target.label}.",
            advanced_detail="Missing or unreadable /etc/os-release",
            command_preview=["cat", "/etc/os-release"],
        )

    @classmethod
    def _desktop_checks(
        cls,
        desktop: KDE44DesktopInfo,
        target: ReleaseTarget | None = None,
    ) -> List[ReadinessCheck]:
        target = target or cls.get_target(cls.TARGET_KEY)
        checks: List[ReadinessCheck] = []
        plasma_version = cls._version_tuple(desktop.plasma_version)
        plasma_status = "pass" if plasma_version >= target.min_plasma else "warning"
        checks.append(
            ReadinessCheck(
                id="kde-plasma-version",
                title="KDE Plasma Version",
                category="desktop",
                status=plasma_status,
                severity="info" if plasma_status == "pass" else "warning",
                summary=f"Plasma version: {desktop.plasma_version}",
                beginner_guidance="Plasma version looks compatible." if plasma_status == "pass" else f"Plasma {'.'.join(str(x) for x in target.min_plasma)}+ is expected for {target.label}.",
                advanced_detail=desktop.display_manager_detail,
                command_preview=["plasmashell", "--version"],
            )
        )

        qt_version = cls._version_tuple(desktop.qt_version)
        qt_status = "pass" if qt_version >= target.min_qt else "warning"
        checks.append(
            ReadinessCheck(
                id="qt-version",
                title="Qt Version",
                category="desktop",
                status=qt_status,
                severity="info" if qt_status == "pass" else "warning",
                summary=f"Qt version: {desktop.qt_version}",
                beginner_guidance="Qt version looks compatible." if qt_status == "pass" else f"Qt {'.'.join(str(x) for x in target.min_qt)}+ is expected for current Plasma 6 desktops.",
                advanced_detail=json.dumps(desktop.to_dict(), indent=2, sort_keys=True),
                command_preview=["qmake6", "--version"],
            )
        )

        session = desktop.session_type.lower()
        session_status = "pass" if session == "wayland" else ("warning" if session == "x11" else "info")
        checks.append(
            ReadinessCheck(
                id="session-type",
                title="Wayland Session",
                category="desktop",
                status=session_status,
                severity="info" if session_status == "pass" else "warning",
                summary=f"Session type: {desktop.session_type}",
                beginner_guidance=f"{target.label} is optimized for Plasma Wayland." if session_status != "pass" else "Wayland session detected.",
                advanced_detail=json.dumps(desktop.raw, indent=2, sort_keys=True),
                command_preview=["printenv", "XDG_SESSION_TYPE"],
            )
        )

        dm_status = "pass" if desktop.display_manager == "SDDM" and desktop.display_manager_active else "warning"
        checks.append(
            ReadinessCheck(
                id="display-manager",
                title="Plasma Login Manager",
                category="desktop",
                status=dm_status,
                severity="info" if dm_status == "pass" else "warning",
                summary=f"Display manager: {desktop.display_manager}",
                beginner_guidance="SDDM is the expected login manager for Fedora KDE." if dm_status != "pass" else "SDDM is active.",
                advanced_detail=desktop.display_manager_detail,
                command_preview=["systemctl", "status", "display-manager.service", "--no-pager"],
            )
        )
        return checks

    @staticmethod
    def _package_checks(package: DNF5HealthReport) -> List[ReadinessCheck]:
        checks = [
            ReadinessCheck(
                id="dnf5-health",
                title="DNF5 Availability",
                category="package",
                status="pass" if package.dnf5_available else "warning",
                severity="info" if package.dnf5_available else "warning",
                summary=f"Package manager: {package.package_manager}",
                beginner_guidance="DNF5 is available." if package.dnf5_available else "DNF5 was not found; current Fedora package flows prefer DNF5.",
                advanced_detail=json.dumps(package.to_dict(), indent=2, sort_keys=True),
                command_preview=[package.package_manager, "--version"] if package.package_manager != "Unknown" else None,
            ),
            ReadinessCheck(
                id="packagekit-status",
                title="PackageKit Status",
                category="package",
                status="pass" if package.packagekit_active else "info",
                severity="info",
                summary=f"PackageKit: {package.packagekit_detail}",
                beginner_guidance="PackageKit is active." if package.packagekit_active else "PackageKit is not active or unavailable; this may be normal on some setups.",
                advanced_detail=package.packagekit_detail,
                command_preview=["systemctl", "is-active", "packagekit.service"],
            ),
            ReadinessCheck(
                id="dnf-locks",
                title="DNF/RPM Locks",
                category="package",
                status="warning" if package.dnf_locked else "pass",
                severity="warning" if package.dnf_locked else "info",
                summary="Active package-manager lock detected." if package.dnf_locked else "No active DNF/RPM lock detected.",
                beginner_guidance="Wait for the current package operation to finish." if package.dnf_locked else "Package manager is not locked.",
                advanced_detail=package.lock_detail,
                command_preview=["fuser", "/var/lib/dnf/metadata_lock.pid", "/var/lib/rpm/.rpm.lock"],
                recommendation=(
                    ReadinessRecommendation(
                        title="Wait for the active package operation",
                        description="Read-only checks should not compete with DNF, RPM, or PackageKit locks.",
                        command_preview=["ps", "aux"],
                        risk_level="info",
                    )
                    if package.dnf_locked
                    else None
                ),
            ),
            ReadinessCheck(
                id="repo-health",
                title="Repository Metadata",
                category="package",
                status="pass" if package.repo_probe_ok else "warning",
                severity="info" if package.repo_probe_ok else "warning",
                summary="Enabled repositories can be queried." if package.repo_probe_ok else "Repository query reported a problem.",
                beginner_guidance="Repository metadata looks reachable." if package.repo_probe_ok else "Check disabled, broken, or outdated repository files before upgrading.",
                advanced_detail=package.repo_probe_detail,
                command_preview=[package.package_manager, "repolist", "--enabled"] if package.package_manager != "Unknown" else None,
                recommendation=(
                    ReadinessRecommendation(
                        title="Review enabled repositories",
                        description="Fix disabled or unreachable repositories before major release work.",
                        command_preview=[package.package_manager, "repolist", "--enabled"] if package.package_manager != "Unknown" else None,
                        risk_level="low",
                    )
                    if not package.repo_probe_ok
                    else None
                ),
            ),
        ]

        high_risks = [risk for risk in package.repo_risks if risk.risk == "warning"]
        checks.append(
            ReadinessCheck(
                id="third-party-repos",
                title="Third-Party Repository Risk",
                category="package",
                status="warning" if high_risks else ("info" if package.repo_risks else "pass"),
                severity="warning" if high_risks else "info",
                summary=f"{len(package.repo_risks)} third-party repository signal(s) found.",
                beginner_guidance="Review COPR and RPM Fusion repos before major upgrades." if package.repo_risks else "No third-party repository risks found.",
                advanced_detail=json.dumps([risk.to_dict() for risk in package.repo_risks], indent=2, sort_keys=True),
                command_preview=["ls", "/etc/yum.repos.d"],
                recommendation=(
                    ReadinessRecommendation(
                        title="Review third-party repositories",
                        description="Leave common repos alone during daily use, but audit COPRs and vendor repos before major upgrades.",
                        command_preview=["dnf5", "repolist", "--enabled"],
                        risk_level="low",
                        rollback_hint="If a repo is disabled manually, re-enable it with the same repo management tool after the upgrade.",
                        docs_link="https://docs.fedoraproject.org/en-US/quick-docs/upgrading-fedora-offline/",
                    )
                    if package.repo_risks
                    else None
                ),
            )
        )
        return checks

    @classmethod
    def _atomic_check(cls) -> ReadinessCheck:
        if not SystemManager.is_atomic():
            return ReadinessCheck(
                id="atomic-status",
                title="Atomic Fedora Status",
                category="system",
                status="info",
                severity="info",
                summary="Traditional Fedora installation detected.",
                beginner_guidance="rpm-ostree guidance is not needed on this system.",
                advanced_detail="SystemManager.is_atomic() returned False.",
                command_preview=["test", "-e", "/run/ostree-booted"],
            )

        pending = SystemManager.has_pending_deployment()
        layered = SystemManager.get_layered_packages()
        return ReadinessCheck(
            id="atomic-status",
            title="Atomic Fedora Status",
            category="system",
            status="warning" if pending else "pass",
            severity="warning" if pending else "info",
            summary="Atomic Fedora detected; reboot pending." if pending else "Atomic Fedora detected.",
            beginner_guidance="Reboot before making more changes." if pending else "rpm-ostree state looks ready.",
            advanced_detail=json.dumps({"pending_deployment": pending, "layered_packages": layered}, indent=2, sort_keys=True),
            command_preview=["rpm-ostree", "status", "--json"],
            recommendation=(
                ReadinessRecommendation(
                    title="Reboot into the pending deployment",
                    description="Apply the staged rpm-ostree deployment before additional release work.",
                    command_preview=["systemctl", "reboot"],
                    risk_level="low",
                )
                if pending
                else None
            ),
        )

    @classmethod
    def _nvidia_check(cls) -> ReadinessCheck:
        lspci = cls._run(["lspci", "-nn"], timeout=8)
        lspci_text = (lspci.stdout if lspci else "") or ""
        has_nvidia = "nvidia" in lspci_text.lower()
        if not has_nvidia:
            return ReadinessCheck(
                id="nvidia-akmods-secureboot",
                title="NVIDIA, akmods, and Secure Boot",
                category="hardware",
                status="pass",
                severity="info",
                summary="No NVIDIA GPU detected by lspci.",
                beginner_guidance="No NVIDIA-specific readiness action is needed.",
                advanced_detail=lspci_text[:2000],
                command_preview=["lspci", "-nn"],
            )

        modinfo = cls._run(["modinfo", "nvidia"], timeout=10)
        module_ok = modinfo is not None and modinfo.returncode == 0
        akmods = cls._run(["akmods", "--kernels", platform.release()], timeout=20) if cached_which("akmods") else None
        secure_boot = SecureBootManager.get_status()
        status = "pass" if module_ok and not secure_boot.pending_mok else "warning"
        details = {
            "module_ok": module_ok,
            "modinfo": ((modinfo.stdout if modinfo else "") or (modinfo.stderr if modinfo else ""))[:2000],
            "akmods": ((akmods.stdout if akmods else "") or (akmods.stderr if akmods else ""))[:2000],
            "secure_boot": {
                "enabled": secure_boot.secure_boot_enabled,
                "mok_enrolled": secure_boot.mok_enrolled,
                "pending_mok": secure_boot.pending_mok,
                "status": secure_boot.status_message,
            },
            "kernel": platform.release(),
        }
        return ReadinessCheck(
            id="nvidia-akmods-secureboot",
            title="NVIDIA, akmods, and Secure Boot",
            category="hardware",
            status=status,
            severity="warning" if status == "warning" else "info",
            summary="NVIDIA GPU detected; module and Secure Boot checks completed.",
            beginner_guidance="Resolve module, akmods, or MOK warnings before upgrading kernels." if status == "warning" else "NVIDIA module state looks compatible.",
            advanced_detail=json.dumps(details, indent=2, sort_keys=True),
            command_preview=["modinfo", "nvidia"],
            recommendation=(
                ReadinessRecommendation(
                    title="Resolve NVIDIA module readiness",
                    description="Review akmods, Secure Boot, and MOK state before kernel or release upgrades.",
                    command_preview=["akmods", "--kernels", platform.release()],
                    risk_level="medium",
                    rollback_hint="Boot a previous working kernel if a rebuilt NVIDIA module causes display issues.",
                )
                if status == "warning"
                else None
            ),
        )

    @classmethod
    def _flatpak_check(cls) -> ReadinessCheck:
        if not cached_which("flatpak"):
            return ReadinessCheck(
                id="flatpak-kde-runtimes",
                title="Flatpak KDE Runtimes",
                category="software",
                status="info",
                severity="info",
                summary="Flatpak is not installed.",
                beginner_guidance="Flatpak runtime checks are skipped.",
                advanced_detail="flatpak executable not found.",
            )
        result = cls._run(["flatpak", "list", "--runtime", "--columns=application,branch"], timeout=20)
        output = result.stdout if result and result.returncode == 0 else ""
        kde_lines = [line for line in output.splitlines() if "KDE" in line or "org.kde" in line]
        return ReadinessCheck(
            id="flatpak-kde-runtimes",
            title="Flatpak KDE Runtimes",
            category="software",
            status="pass" if kde_lines else "info",
            severity="info",
            summary=f"{len(kde_lines)} KDE Flatpak runtime(s) detected.",
            beginner_guidance="KDE Flatpak runtimes are present." if kde_lines else "Install apps normally; Flatpak will pull KDE runtimes when needed.",
            advanced_detail="\n".join(kde_lines)[:3000],
            command_preview=["flatpak", "list", "--runtime", "--columns=application,branch"],
        )

    @staticmethod
    def _tls_check() -> ReadinessCheck:
        legacy_path = "/etc/pki/tls/cert.pem"
        fedora_bundle = "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
        if os.path.exists(legacy_path):
            detail = ""
            try:
                detail = f"mode={oct(os.stat(legacy_path).st_mode & 0o777)} size={os.path.getsize(legacy_path)}"
            except OSError as exc:
                detail = f"stat failed: {exc}"
            return ReadinessCheck(
                id="tls-cert-compat",
                title="TLS Certificate Compatibility",
                category="network",
                status="pass",
                severity="info",
                summary=f"{legacy_path} exists.",
                beginner_guidance="TLS certificate bundle path looks compatible.",
                advanced_detail=detail,
                command_preview=["test", "-f", legacy_path],
            )

        if os.path.exists(fedora_bundle):
            return ReadinessCheck(
                id="tls-cert-compat",
                title="TLS Certificate Compatibility",
                category="network",
                status="info",
                severity="info",
                summary=f"Fedora CA trust bundle exists at {fedora_bundle}.",
                beginner_guidance="Fedora's certificate trust is present; only legacy tools may expect /etc/pki/tls/cert.pem.",
                advanced_detail=f"{legacy_path} missing; {fedora_bundle} present.",
                command_preview=["test", "-f", fedora_bundle],
                recommendation=ReadinessRecommendation(
                    title="Check only affected legacy tools",
                    description="Do not create compatibility links unless a specific tool fails with this path.",
                    command_preview=["test", "-f", legacy_path],
                    risk_level="info",
                ),
            )

        return ReadinessCheck(
            id="tls-cert-compat",
            title="TLS Certificate Compatibility",
            category="network",
            status="warning",
            severity="warning",
            summary="No expected Fedora TLS certificate bundle path was found.",
            beginner_guidance="TLS verification may fail for tools that depend on Fedora's CA trust bundle.",
            advanced_detail=f"Missing {legacy_path} and {fedora_bundle}.",
            command_preview=["test", "-f", fedora_bundle],
            recommendation=ReadinessRecommendation(
                title="Repair Fedora CA trust package",
                description="Verify ca-certificates is installed and the trust store is generated before release work.",
                command_preview=["rpm", "-q", "ca-certificates"],
                risk_level="low",
            ),
        )

    @staticmethod
    def _score(checks: List[ReadinessCheck]) -> int:
        score = 100
        for check in checks:
            if check.severity == "critical":
                score -= 30
            elif check.severity == "error":
                score -= 22
            elif check.severity == "warning":
                score -= 9
        return max(0, min(100, score))

    @staticmethod
    def _overall_status(score: int, checks: List[ReadinessCheck], target: ReleaseTarget | None = None) -> str:
        target = target or TARGETS["44"]
        if target.preview:
            return "preview"
        if any(check.severity in {"critical", "error"} for check in checks):
            return "needs_attention"
        if score < 80:
            return "review"
        return "ready"

    @classmethod
    def run(cls, target_key: str | None = None) -> ReleaseReadinessReport:
        target = cls.get_target(target_key or cls.TARGET_KEY)
        os_release = cls._os_release()
        desktop = KDE44DesktopService.collect()
        package = DNF5HealthService.collect()
        checks: List[ReadinessCheck] = []
        checks.append(cls._fedora_version_check(os_release, target))
        checks.extend(cls._desktop_checks(desktop, target))
        checks.extend(cls._package_checks(package))
        checks.append(cls._atomic_check())
        checks.append(cls._nvidia_check())
        checks.append(cls._flatpak_check())
        checks.append(cls._tls_check())

        score = cls._score(checks)
        status = cls._overall_status(score, checks, target)
        warnings = len([check for check in checks if check.severity == "warning"])
        errors = len([check for check in checks if check.severity in {"error", "critical"}])
        preview_note = " Preview profile; findings are advisory." if target.preview else ""
        summary = f"{target.label} readiness score {score}/100 with {warnings} warning(s) and {errors} error(s).{preview_note}"
        return ReleaseReadinessReport(
            target=target.label,
            generated_at=time.time(),
            score=score,
            status=status,
            summary=summary,
            checks=checks,
            desktop=desktop,
            package=package,
            target_metadata=target,
        )


Fedora44ReadinessReport = ReleaseReadinessReport
