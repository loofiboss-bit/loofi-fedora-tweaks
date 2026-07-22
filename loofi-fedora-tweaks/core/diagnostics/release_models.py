"""Typed presentation models and Fedora target policy for release readiness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from services.desktop.kde44 import KDE44DesktopInfo
from services.package.dnf5_health import DNF5HealthReport


@dataclass(frozen=True)
class ReleaseChange:
    """Static release-profile metadata shown in upgrade planning surfaces."""

    id: str
    title: str
    summary: str
    impact: str = "info"
    docs_link: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "impact": self.impact,
            "docs_link": self.docs_link,
        }


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
    status_label: str = "Supported"
    release_phase: str = "stable"
    upgrade_from: tuple[str, ...] = ()
    important_changes: tuple[ReleaseChange, ...] = ()
    known_risks: tuple[ReleaseChange, ...] = ()
    docs_links: tuple[str, ...] = ()

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
            "status_label": self.status_label,
            "release_phase": self.release_phase,
            "upgrade_from": list(self.upgrade_from),
            "important_changes": [change.to_dict() for change in self.important_changes],
            "known_risks": [risk.to_dict() for risk in self.known_risks],
            "docs_links": list(self.docs_links),
        }


TARGETS: Dict[str, ReleaseTarget] = {
    FEDORA_RELEASE_POLICY.stable_target: ReleaseTarget(
        key=FEDORA_RELEASE_POLICY.stable_target,
        label=f"Fedora KDE {FEDORA_RELEASE_POLICY.stable_release}",
        fedora_version=FEDORA_RELEASE_POLICY.stable_release,
        supported=True,
        compatible_versions=("43",),
        status_label="Supported baseline",
        release_phase="stable",
        upgrade_from=("43",),
        important_changes=(
            ReleaseChange(
                "packagekit-dnf5",
                "PackageKit uses DNF5",
                "Fedora 44 aligns graphical software tools and command-line package management on the DNF5 stack.",
                "medium",
                "https://discussion.fedoraproject.org/t/f44-change-proposal-packagekit-dnf5-systemwide/179013",
            ),
            ReleaseChange(
                "kde-oobe",
                "Unified KDE setup",
                "Fedora KDE variants use Plasma Setup for a more consistent first-run experience.",
                "info",
                "https://fedoraproject.org/wiki/Releases/44/ChangeSet",
            ),
        ),
        known_risks=(
            ReleaseChange(
                "legacy-cert-path",
                "Legacy TLS bundle path changed",
                "Some legacy tools may still expect /etc/pki/tls/cert.pem even though Fedora uses the generated CA trust bundle.",
                "low",
                "https://fedoraproject.org/wiki/Releases/44/ChangeSet",
            ),
        ),
        docs_links=(
            "https://fedoraproject.org/kde/download/",
            "https://fedoramagazine.org/announcing-fedora-linux-44/",
        ),
    ),
    FEDORA_RELEASE_POLICY.preview_target: ReleaseTarget(
        key=FEDORA_RELEASE_POLICY.preview_target,
        label=f"Fedora KDE {FEDORA_RELEASE_POLICY.preview_release} Preview",
        fedora_version=FEDORA_RELEASE_POLICY.preview_release,
        supported=False,
        preview=True,
        compatible_versions=("44",),
        beta_target="2026-09-15",
        final_target="2026-10-20",
        status_label="Preview planning profile",
        release_phase="preview",
        upgrade_from=("44",),
        important_changes=(
            ReleaseChange(
                "repo-configs-usr",
                "Packaged repository configs move to /usr",
                "Fedora 45 plans to relocate packaged RPM repository configuration data from /etc to /usr.",
                "medium",
                "https://fedoraproject.org/wiki/Releases/45/ChangeSet",
            ),
            ReleaseChange(
                "python-315",
                "Python 3.15 and Setuptools changes",
                "Fedora 45 includes Python 3.15 planning and Setuptools 82+ compatibility work that can affect tools using removed legacy APIs.",
                "medium",
                "https://fedoraproject.org/wiki/Changes/Python3.15",
            ),
            ReleaseChange(
                "networkmanager-ipv6-mostly",
                "IPv6-mostly NetworkManager support",
                "NetworkManager gains default support for IPv6-mostly networks.",
                "low",
                "https://fedoraproject.org/wiki/Releases/45/ChangeSet",
            ),
            ReleaseChange(
                "podman-6",
                "Podman 6",
                "Podman 6 brings CLI/API changes and removes some deprecated container networking/storage components.",
                "medium",
                "https://fedoraproject.org/wiki/Releases/45/ChangeSet",
            ),
            ReleaseChange(
                "atomic-flatpak-filtering",
                "Atomic Flatpak filtering",
                "Atomic Desktop images may filter Fedora Flatpaks and enable a verified Flathub subset by default.",
                "low",
                "https://fedoraproject.org/wiki/Releases/45/ChangeSet",
            ),
        ),
        known_risks=(
            ReleaseChange(
                "third-party-repos",
                "Third-party repositories need review",
                "COPR, vendor, and RPM Fusion repositories can lag major release changes and should be audited before upgrade.",
                "medium",
            ),
            ReleaseChange(
                "rpm-openssl-compat",
                "RPM/OpenSSL compatibility should be checked",
                "RPM and OpenSSL stack changes can expose stale package metadata, signatures, or certificate assumptions.",
                "medium",
            ),
        ),
        docs_links=(
            "https://fedoraproject.org/wiki/Releases/45/ChangeSet",
            "https://fedoraproject.org/wiki/Changes/Python3.15",
        ),
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
    target_metadata: ReleaseTarget = field(default_factory=lambda: TARGETS[FEDORA_RELEASE_POLICY.stable_target])
    mode: str = "check"

    def to_dict(self, *, advanced: bool = True) -> Dict[str, object]:
        data: Dict[str, object] = {
            "target": self.target,
            "target_metadata": self.target_metadata.to_dict(),
            "generated_at": self.generated_at,
            "score": self.score,
            "status": self.status,
            "summary": self.summary,
            "mode": self.mode,
            "checks": [check.to_dict(advanced=advanced) for check in self.checks],
            "target_changes": {
                "important_changes": [change.to_dict() for change in self.target_metadata.important_changes],
                "known_risks": [risk.to_dict() for risk in self.target_metadata.known_risks],
            },
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
