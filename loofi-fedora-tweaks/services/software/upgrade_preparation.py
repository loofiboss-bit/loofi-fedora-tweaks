"""Bounded local observations for a manual Fedora release upgrade."""
from __future__ import annotations

import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Event
from typing import Any

from core.actions.contracts import ActionRuntime
from core.executor.action_result import ActionResult

from core.executor.command_facade import CommandFacade
from core.fedora_release_policy import FEDORA_RELEASE_POLICY, FedoraReleasePolicy
from core.platform.profile import DeploymentBackend, PlatformProfile
from services.software.update_overview import OverviewCancelled, OverviewRuntime
from services.software.source_status import _parse_dnf_repositories, _source_state
from services.software.restart_advice import RESTART_QUERY, parse_restart_result

UPGRADE_DOCUMENTATION = "https://docs.fedoraproject.org/en-US/quick-docs/upgrading-fedora-offline/"
ATOMIC_DOCUMENTATION = "https://fedoraproject.org/atomic-desktops/"
LIMITATION = "Local observations do not predict the next release transaction. No upgrade is downloaded or applied."


class UpgradePreparationRuntime(OverviewRuntime):
    """Only closed, cache-only DNF5 inspection vectors are permitted."""

    _QUERIES = {
        ("dnf5", "--cacheonly", "check", "--dependencies"),
        ("dnf5", "--cacheonly", "repolist", "--all", "--json"),
        ("dnf5", "--cacheonly", "needs-restarting", "--json"),
    }


@dataclass(frozen=True)
class UpgradePreparationReport:
    """Versioned observation report; never an upgrade authorization."""

    target: str
    target_state: str
    platform: dict[str, Any]
    release_policy: dict[str, Any]
    checked_at: str
    package_database: dict[str, Any]
    sources: dict[str, Any]
    disks: tuple[dict[str, Any], ...]
    reboot: dict[str, Any]
    state: str = "completed"
    schema: str = "loofi.upgrade-preparation/v1"
    limitation: str = LIMITATION
    documentation: str = UPGRADE_DOCUMENTATION
    backup: str = "Manual checklist only; Loofi has not verified a backup."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class UpgradePreparationService:
    """Explicit checks with one 25-second budget and cancellable bounded output."""

    def __init__(self, *, profile: PlatformProfile | None = None, policy: FedoraReleasePolicy = FEDORA_RELEASE_POLICY,
                 runtime: ActionRuntime | None = None) -> None:
        self.profile = profile
        self.policy = policy
        self._cancelled = Event()
        self.runtime = runtime or UpgradePreparationRuntime(CommandFacade(), cancelled=self._cancelled, output_limit=65536)

    def cancel(self) -> None:
        self._cancelled.set()

    def reset_cancel(self) -> None:
        self._cancelled.clear()

    def _target_state(self, target: str, profile: PlatformProfile) -> str:
        if target not in self.policy.action_targets:
            return "invalid"
        if not profile.is_fedora:
            return "unknown_host"
        major = int(target.split("-", 1)[0])
        if profile.fedora_version is None:
            return "unknown_host"
        if major < profile.fedora_version:
            return "downgrade"
        if major == profile.fedora_version:
            return "current_release"
        if self.policy.is_preview_target(target):
            return "preview"
        if profile.support_status == "unknown":
            return "unknown_host"
        return "stable"

    def prepare(self, target: str | None = None) -> UpgradePreparationReport:
        profile = self.profile or PlatformProfile.detect()
        target = str(target or self.policy.stable_target)
        target_state = self._target_state(target, profile)
        deadline = time.monotonic() + 25
        unknown: dict[str, Any] = {"state": "unknown", "reason": "unsupported_backend"}
        database, sources, reboot = dict(unknown), dict(unknown), dict(unknown)
        disks: list[dict[str, Any]] = []
        for mount in ("/", "/boot"):
            if self._cancelled.is_set():
                raise OverviewCancelled()
            try:
                usage = shutil.disk_usage(mount)
                disks.append({"mount": mount, "state": "observed", "free_bytes": usage.free, "total_bytes": usage.total})
            except OSError:
                disks.append({"mount": mount, "state": "unknown"})
        can_probe = (profile.is_fedora and not profile.is_atomic and profile.deployment_backend is DeploymentBackend.DNF5
                     and profile.package_manager_name == "dnf5" and target_state != "invalid")
        if can_probe:
            def query(vector: tuple[str, ...]) -> ActionResult | None:
                if self._cancelled.is_set():
                    raise OverviewCancelled()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                return self.runtime.execute_read_only(vector, action_id="upgrade-preparation", timeout=min(8, remaining))

            result = query(("dnf5", "--cacheonly", "check", "--dependencies"))
            database = {"state": "observed" if result and result.success else "unknown",
                        "healthy": True if result and result.success else None,
                        "reason": "local_check_passed" if result and result.success else "local_check_failed",
                        "exit_code": result.exit_code if result else None}
            result = query(("dnf5", "--cacheonly", "repolist", "--all", "--json"))
            sources = {"state": "unknown", "reason": "source_probe_failed"}
            if result and result.success:
                try:
                    repositories = _parse_dnf_repositories(result.stdout)
                    known = {source: _source_state(repositories, source).value
                             for source in ("rpmfusion-free", "rpmfusion-nonfree")}
                    loofi_enabled = repositories.get(
                        "copr:copr.fedorainfracloud.org:loofitheboss:loofi-fedora-tweaks",
                        repositories.get("loofi-fedora-tweaks", False))
                    known["loofi-copr"] = "enabled" if loofi_enabled else "disabled"
                    sources = {"state": "observed", "enabled_count": sum(repositories.values()),
                               "known_sources": known, "reason": "local_configuration_only"}
                except (ValueError, TypeError):
                    sources = {"state": "unknown", "reason": "invalid_response"}
            advice = parse_restart_result(query(RESTART_QUERY))
            reboot = {"state": advice.state, "reason": advice.reason, "packages": list(advice.packages)}
        if self._cancelled.is_set():
            raise OverviewCancelled()
        partial = any(item["state"] == "unknown" for item in (database, sources, reboot)) or any(disk["state"] == "unknown" for disk in disks)
        return UpgradePreparationReport(target, target_state, profile.to_dict(), asdict(self.policy), datetime.now(timezone.utc).isoformat(),
                                        database, sources, tuple(disks), reboot, state="partial" if partial else "completed",
                                        documentation=ATOMIC_DOCUMENTATION if profile.is_atomic else UPGRADE_DOCUMENTATION)
