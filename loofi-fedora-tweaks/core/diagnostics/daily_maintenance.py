"""Daily maintenance overview probes for "My Fedora Today" surfaces."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable

from services.package.dnf5_health import DNF5HealthReport, DNF5HealthService
from services.system.system import SystemManager


@dataclass(frozen=True)
class MaintenanceCard:
    """One bounded daily-maintenance signal."""

    id: str
    title: str
    state: str
    summary: str
    command_preview: list[str] = field(default_factory=list)
    requires_package: str = ""
    details: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state,
            "summary": self.summary,
            "command_preview": list(self.command_preview),
            "requires_package": self.requires_package,
            "details": self.details,
        }


@dataclass(frozen=True)
class DailyMaintenanceReport:
    """Aggregated maintenance dashboard payload."""

    generated_at: float
    atomic: bool
    cards: list[MaintenanceCard]
    recommended_action: str

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "atomic": self.atomic,
            "cards": [card.to_dict() for card in self.cards],
            "recommended_action": self.recommended_action,
        }


class DailyMaintenanceService:
    """Read-only, bounded probes for the daily maintenance dashboard."""

    def __init__(
        self,
        *,
        runner: Callable[[list[str], int], subprocess.CompletedProcess[str] | None] | None = None,
        package_service: type[DNF5HealthService] = DNF5HealthService,
    ):
        self._runner = runner or self._run
        self._package_service = package_service

    @staticmethod
    def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
            return None

    def collect(self) -> DailyMaintenanceReport:
        atomic = SystemManager.is_atomic()
        package = self._package_service.collect()
        cards = [
            self._system_updates_card(atomic, package),
            self._flatpak_card(),
            self._firmware_card(),
            self._failed_services_card(),
            self._journal_card(),
            self._disk_card(),
            self._package_health_card(atomic, package),
            self._rollback_card(atomic),
        ]
        return DailyMaintenanceReport(
            generated_at=time.time(),
            atomic=atomic,
            cards=cards,
            recommended_action=self._recommended_action(cards),
        )

    def collect_quick(self) -> DailyMaintenanceReport:
        """Collect the closed System Check subset using the existing probes."""
        atomic = SystemManager.is_atomic()
        package = self._package_service.collect()
        cards = [
            self._system_updates_card(atomic, package),
            self._failed_services_card(),
            self._disk_card(),
            self._package_health_card(atomic, package),
            self._rollback_card(atomic),
        ]
        return DailyMaintenanceReport(
            generated_at=time.time(),
            atomic=atomic,
            cards=cards,
            recommended_action=self._recommended_action(cards),
        )

    def _system_updates_card(self, atomic: bool, package: DNF5HealthReport) -> MaintenanceCard:
        if atomic:
            return MaintenanceCard(
                id="system-updates",
                title="System Updates",
                state="preview_only",
                summary="Atomic Fedora updates are handled through rpm-ostree deployments.",
                command_preview=["rpm-ostree", "upgrade", "--check"],
            )
        return MaintenanceCard(
            id="system-updates",
            title="System Updates",
            state="success" if package.repo_probe_ok and not package.dnf_locked else "warning",
            summary="Package metadata is reachable." if package.repo_probe_ok else "Repository metadata needs review.",
            command_preview=[package.package_manager, "check-update"] if package.package_manager != "Unknown" else [],
        )

    def _flatpak_card(self) -> MaintenanceCard:
        if not shutil.which("flatpak"):
            return MaintenanceCard("flatpak-updates", "Flatpak Updates", "unsupported", "Flatpak is not installed.", requires_package="flatpak")
        result = self._runner(["flatpak", "remote-list"], 10)
        state = "success" if result and result.returncode == 0 else "warning"
        return MaintenanceCard("flatpak-updates", "Flatpak Updates", state, "Flatpak remotes can be queried." if state == "success" else "Flatpak remote state needs review.", ["flatpak", "update", "--appstream"])

    def _firmware_card(self) -> MaintenanceCard:
        if not shutil.which("fwupdmgr"):
            return MaintenanceCard("firmware", "Firmware", "unsupported", "fwupd is not installed.", requires_package="fwupd")
        return MaintenanceCard("firmware", "Firmware", "success", "Firmware checks are available.", ["fwupdmgr", "get-updates"])

    def _failed_services_card(self) -> MaintenanceCard:
        result = self._runner(["systemctl", "--failed", "--no-legend"], 10)
        if result is None or result.returncode != 0:
            return MaintenanceCard(
                id="failed-services",
                title="Failed Services",
                state="error",
                summary="Unable to query failed services.",
            )
        output = (result.stdout if result else "").strip()
        failed = [line for line in output.splitlines() if line.strip()]
        return MaintenanceCard(
            id="failed-services",
            title="Failed Services",
            state="warning" if failed else "success",
            summary=f"{len(failed)} failed service(s) detected." if failed else "No failed services detected.",
            command_preview=["systemctl", "--failed"],
            details="\n".join(failed[:10]),
        )

    def _journal_card(self) -> MaintenanceCard:
        result = self._runner(["journalctl", "-p", "4", "-n", "20", "--no-pager"], 10)
        output = (result.stdout if result else "").strip()
        return MaintenanceCard(
            id="journal-warnings",
            title="Recent Journal Warnings",
            state="warning" if output else "success",
            summary="Recent warning/error lines are present." if output else "No recent warning/error lines returned.",
            command_preview=["journalctl", "-p", "4", "-n", "20", "--no-pager"],
            details=output[:1200],
        )

    def _disk_card(self) -> MaintenanceCard:
        result = self._runner(["df", "-h", "/"], 8)
        output = (result.stdout if result else "").strip()
        return MaintenanceCard("disk-usage", "Disk Usage", "success" if output else "error", "Root filesystem usage is available." if output else "Unable to read disk usage.", ["df", "-h", "/"], details=output)

    @staticmethod
    def _package_health_card(atomic: bool, package: DNF5HealthReport) -> MaintenanceCard:
        if atomic:
            return MaintenanceCard(
                "package-health",
                "Package Manager Health",
                "success",
                "Atomic package health is managed through rpm-ostree deployments.",
                ["rpm-ostree", "status"],
            )
        if package.dnf_locked:
            return MaintenanceCard("package-health", "Package Manager Health", "blocked", "Package manager lock detected.", ["fuser", "/var/lib/dnf/metadata_lock.pid", "/var/lib/rpm/.rpm.lock"], details=package.lock_detail)
        return MaintenanceCard("package-health", "Package Manager Health", "success" if package.repo_probe_ok else "warning", package.repo_probe_detail or "Package manager health collected.", [package.package_manager, "repolist", "--enabled"] if package.package_manager != "Unknown" else [])

    @staticmethod
    def _rollback_card(atomic: bool) -> MaintenanceCard:
        if atomic:
            return MaintenanceCard("rollback", "Rollback Status", "success", "rpm-ostree rollback guidance is available.", ["rpm-ostree", "status"])
        if shutil.which("snapper"):
            return MaintenanceCard("rollback", "Rollback Status", "success", "Snapper is available for snapshots.", ["snapper", "list"])
        if shutil.which("timeshift"):
            return MaintenanceCard("rollback", "Rollback Status", "success", "Timeshift is available for snapshots.", ["timeshift", "--list"])
        return MaintenanceCard("rollback", "Rollback Status", "warning", "No supported snapshot tool was detected.")

    @staticmethod
    def _recommended_action(cards: list[MaintenanceCard]) -> str:
        for state in ("blocked", "error", "warning"):
            card = next((item for item in cards if item.state == state), None)
            if card:
                return f"Review {card.title}: {card.summary}"
        return "No immediate maintenance action is required."
