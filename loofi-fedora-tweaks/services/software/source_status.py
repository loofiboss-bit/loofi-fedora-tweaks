"""Read-only status checks for the software sources shown in the GUI."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Final

from services.system.system import SystemManager


class SourceState(str, Enum):
    """Whether a known source is enabled, disabled, or could not be checked."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class SourceScope(str, Enum):
    """Configuration scope used by a software source."""

    SYSTEM = "system"
    USER = "user"


class SourceStatusReason(str, Enum):
    """Stable, presentation-neutral explanations for unknown status."""

    TOOL_UNAVAILABLE = "tool_unavailable"
    UNSUPPORTED_BACKEND = "unsupported_backend"
    TIMEOUT = "timeout"
    COMMAND_FAILED = "command_failed"
    INVALID_RESPONSE = "invalid_response"
    PROBE_FAILED = "probe_failed"


@dataclass(frozen=True)
class SourceStatus:
    """Local configuration state for one source and one installation scope."""

    source_id: str
    scope: SourceScope
    state: SourceState
    reason: SourceStatusReason | None = None
    exit_code: int | None = None


SOURCE_STATUS_KEYS: Final[tuple[tuple[str, SourceScope], ...]] = (
    ("rpmfusion-free", SourceScope.SYSTEM),
    ("rpmfusion-nonfree", SourceScope.SYSTEM),
    ("loofi-copr", SourceScope.SYSTEM),
    ("flathub", SourceScope.SYSTEM),
    ("flathub", SourceScope.USER),
)

_DNF_TIMEOUT_SECONDS = 20


def _unknown(
    source_id: str,
    scope: SourceScope,
    reason: SourceStatusReason,
    *,
    exit_code: int | None = None,
) -> SourceStatus:
    return SourceStatus(source_id, scope, SourceState.UNKNOWN, reason, exit_code)


def _parse_dnf_repositories(output: str) -> dict[str, bool]:
    """Parse the stable DNF5 JSON fields required for known-source status."""
    records = json.loads(output)
    if not isinstance(records, list):
        raise ValueError("Expected a repository list")

    repositories: dict[str, bool] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Expected a repository object")
        repository_id = record.get("id")
        enabled = record.get("is_enabled")
        if not isinstance(repository_id, str) or not repository_id or not isinstance(enabled, bool):
            raise ValueError("Repository record is incomplete")
        key = repository_id.casefold()
        if key in repositories:
            raise ValueError("Repository IDs must be unique")
        repositories[key] = enabled
    return repositories


def _source_state(repositories: dict[str, bool], prefix: str) -> SourceState:
    matching = [
        enabled
        for repository_id, enabled in repositories.items()
        if repository_id == prefix or repository_id.startswith(prefix + "-")
    ]
    return SourceState.ENABLED if any(matching) else SourceState.DISABLED


class SoftwareSourceStatusService:
    """Inspect configured source state without refreshing metadata or changing it."""

    def snapshot(self) -> tuple[SourceStatus, ...]:
        """Return status for RPM Fusion, Loofi COPR, and both Flathub scopes."""
        statuses = list(self._dnf_statuses())
        statuses.append(self._flatpak_status(SourceScope.SYSTEM))
        statuses.append(self._flatpak_status(SourceScope.USER))
        return tuple(statuses)

    def _dnf_statuses(self) -> tuple[SourceStatus, ...]:
        source_ids = ("rpmfusion-free", "rpmfusion-nonfree", "loofi-copr")
        try:
            package_manager = SystemManager.get_package_manager()
        except (OSError, RuntimeError, TypeError, ValueError):
            return tuple(
                _unknown(source_id, SourceScope.SYSTEM, SourceStatusReason.PROBE_FAILED)
                for source_id in source_ids
            )

        if package_manager != "dnf5":
            return tuple(
                _unknown(source_id, SourceScope.SYSTEM, SourceStatusReason.UNSUPPORTED_BACKEND)
                for source_id in source_ids
            )
        if shutil.which(package_manager) is None:
            return tuple(
                _unknown(source_id, SourceScope.SYSTEM, SourceStatusReason.TOOL_UNAVAILABLE)
                for source_id in source_ids
            )

        try:
            result = subprocess.run(
                [package_manager, "--cacheonly", "repolist", "--all", "--json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=_DNF_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            reason = SourceStatusReason.TIMEOUT
            return tuple(_unknown(source_id, SourceScope.SYSTEM, reason) for source_id in source_ids)
        except (OSError, subprocess.SubprocessError):
            reason = SourceStatusReason.PROBE_FAILED
            return tuple(_unknown(source_id, SourceScope.SYSTEM, reason) for source_id in source_ids)

        if result.returncode != 0:
            return tuple(
                _unknown(
                    source_id,
                    SourceScope.SYSTEM,
                    SourceStatusReason.COMMAND_FAILED,
                    exit_code=result.returncode,
                )
                for source_id in source_ids
            )

        try:
            repositories = _parse_dnf_repositories(result.stdout)
        except (TypeError, ValueError, json.JSONDecodeError):
            return tuple(
                _unknown(source_id, SourceScope.SYSTEM, SourceStatusReason.INVALID_RESPONSE)
                for source_id in source_ids
            )

        return (
            SourceStatus(
                "rpmfusion-free",
                SourceScope.SYSTEM,
                _source_state(repositories, "rpmfusion-free"),
            ),
            SourceStatus(
                "rpmfusion-nonfree",
                SourceScope.SYSTEM,
                _source_state(repositories, "rpmfusion-nonfree"),
            ),
            SourceStatus(
                "loofi-copr",
                SourceScope.SYSTEM,
                SourceState.ENABLED
                if repositories.get(
                    "copr:copr.fedorainfracloud.org:loofitheboss:loofi-fedora-tweaks",
                    repositories.get("loofi-fedora-tweaks", False),
                )
                else SourceState.DISABLED,
            ),
        )

    @staticmethod
    def _flatpak_status(scope: SourceScope) -> SourceStatus:
        if shutil.which("flatpak") is None:
            return _unknown("flathub", scope, SourceStatusReason.TOOL_UNAVAILABLE)
        try:
            enabled = SystemManager.is_flathub_enabled(scope=scope.value)
        except (OSError, RuntimeError, TypeError, ValueError):
            return _unknown("flathub", scope, SourceStatusReason.PROBE_FAILED)
        if enabled is None:
            return _unknown("flathub", scope, SourceStatusReason.PROBE_FAILED)
        return SourceStatus(
            "flathub",
            scope,
            SourceState.ENABLED if enabled else SourceState.DISABLED,
        )


__all__ = [
    "SOURCE_STATUS_KEYS",
    "SoftwareSourceStatusService",
    "SourceScope",
    "SourceState",
    "SourceStatus",
    "SourceStatusReason",
]
