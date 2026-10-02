"""Daily maintenance overview probes for "My Fedora Today" surfaces."""

from __future__ import annotations

import re
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
    error_reason_code: str = ""

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
        return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)

    def _probe(
        self, cmd: list[str], timeout: int, card_id: str, title: str,
    ) -> subprocess.CompletedProcess[str] | MaintenanceCard:
        try:
            result = self._runner(cmd, timeout)
        except subprocess.TimeoutExpired:
            reason, message = "probe-timeout", "The query timed out."
        except PermissionError:
            reason, message = "probe-permission-denied", "Permission to query this source was denied."
        except FileNotFoundError:
            reason, message = "probe-unavailable", "The required query tool is unavailable."
        except (OSError, subprocess.SubprocessError):
            reason, message = "probe-failed", "The query could not be completed."
        else:
            if result is not None and result.returncode == 0:
                return result
            if result is None:
                reason, message = "probe-unavailable", "The query returned no result."
            elif re.search(r"permission denied|access denied|not permitted", result.stderr or "", re.IGNORECASE):
                reason, message = "probe-permission-denied", "Permission to query this source was denied."
            else:
                reason, message = "probe-failed", f"The query exited with status {result.returncode}."
        return MaintenanceCard(card_id, title, "error", message, cmd, error_reason_code=reason)

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
        result = self._probe(["flatpak", "remote-list"], 10, "flatpak-updates", "Flatpak Updates")
        if isinstance(result, MaintenanceCard):
            return result
        return MaintenanceCard("flatpak-updates", "Flatpak Updates", "success", "Flatpak remotes can be queried.", ["flatpak", "update", "--appstream"])

    def _firmware_card(self) -> MaintenanceCard:
        if not shutil.which("fwupdmgr"):
            return MaintenanceCard("firmware", "Firmware", "unsupported", "fwupd is not installed.", requires_package="fwupd")
        return MaintenanceCard("firmware", "Firmware", "success", "Firmware checks are available.", ["fwupdmgr", "get-updates"])

    def _failed_services_card(self) -> MaintenanceCard:
        result = self._probe(["systemctl", "--failed", "--no-legend"], 10, "failed-services", "Failed Services")
        if isinstance(result, MaintenanceCard):
            return result
        output = (result.stdout or "").strip()
        failed = [line for line in output.splitlines() if line.strip()]
        if failed and not all(re.search(r"(?:^|\s)[A-Za-z0-9_.@:-]+\.(?:service|socket|mount|target|path|scope|slice|automount|swap|timer)(?:\s|$)", line) for line in failed):
            return MaintenanceCard("failed-services", "Failed Services", "error", "The query returned an invalid failed service list.", ["systemctl", "--failed"], error_reason_code="probe-invalid-output")
        return MaintenanceCard(
            id="failed-services",
            title="Failed Services",
            state="warning" if failed else "success",
            summary=f"{len(failed)} failed service(s) detected." if failed else "No failed services detected.",
            command_preview=["systemctl", "--failed"],
            details="\n".join(failed[:10]),
        )

    def _journal_card(self) -> MaintenanceCard:
        result = self._probe(["journalctl", "-p", "4", "-n", "20", "--no-pager"], 10, "journal-warnings", "Recent Journal Warnings")
        if isinstance(result, MaintenanceCard):
            return result
        output = (result.stdout or "").strip()
        if output == "-- No entries --":
            output = ""
        return MaintenanceCard(
            id="journal-warnings",
            title="Recent Journal Warnings",
            state="warning" if output else "success",
            summary="Recent warning/error lines are present." if output else "No recent warning/error lines returned.",
            command_preview=["journalctl", "-p", "4", "-n", "20", "--no-pager"],
            details=output[:1200],
        )

    def _disk_card(self) -> MaintenanceCard:
        result = self._probe(["df", "-h", "/"], 8, "disk-usage", "Disk Usage")
        if isinstance(result, MaintenanceCard):
            return result
        output = (result.stdout or "").strip()
        if root_usage_percent(output) is None:
            return MaintenanceCard("disk-usage", "Disk Usage", "error", "The query returned invalid root filesystem usage.", ["df", "-h", "/"], error_reason_code="probe-invalid-output")
        return MaintenanceCard("disk-usage", "Disk Usage", "success", "Root filesystem usage is available.", ["df", "-h", "/"], details=output)

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


def root_usage_percent(details: str) -> float | None:
    """Read only the root mount's integer Use% field from bounded df output."""
    values: list[float] = []
    for line in str(details).splitlines():
        columns = line.split()
        if len(columns) < 2 or columns[-1] != "/":
            continue
        match = re.fullmatch(r"(\d{1,3})%", columns[-2])
        if match is None or not 0 <= int(match.group(1)) <= 100:
            return None
        values.append(float(match.group(1)))
    return values[0] if len(values) == 1 else None
