"""Read-only status checks for the software sources shown in the GUI."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final

from services.system.system import SystemManager
from core.privacy import redact_text


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


@dataclass(frozen=True)
class DnfRepository:
    """One configured repository, with display-safe local metadata."""

    source_id: str
    name: str
    enabled: bool


@dataclass(frozen=True)
class DnfSourceSnapshot:
    """A single local observation; failure is distinct from an empty list."""

    observed_at: str
    repositories: tuple[DnfRepository, ...] = ()
    reason: SourceStatusReason | None = None
    exit_code: int | None = None

    @property
    def success(self) -> bool:
        return self.reason is None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "observed_at": self.observed_at,
            "reason": self.reason.value if self.reason else None,
            "exit_code": self.exit_code,
            "repositories": [
                {"id": redact_text(repo.source_id), "name": redact_text(repo.name), "enabled": repo.enabled}
                for repo in self.repositories
            ],
        }


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous duplicate JSON fields instead of silently overwriting."""
    record: dict[str, Any] = {}
    for key, value in pairs:
        if key in record:
            raise ValueError("Repository JSON fields must be unique")
        record[key] = value
    return record


def _dnf_records(output: str) -> list[dict[str, Any]]:
    records = json.loads(output, object_pairs_hook=_unique_json_object)
    if not isinstance(records, list):
        raise ValueError("Expected a repository list")
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Expected a repository object")
        repository_id = record.get("id")
        enabled = record.get("is_enabled")
        if not isinstance(repository_id, str) or not repository_id.strip() or not isinstance(enabled, bool):
            raise ValueError("Repository record is incomplete")
        if repository_id.casefold() in seen:
            raise ValueError("Repository IDs must be unique")
        seen.add(repository_id.casefold())
    return records


def _parse_dnf_repositories(output: str) -> dict[str, bool]:
    """Preserve the ID/enabled parser contract used by upgrade preparation."""
    return {record["id"].casefold(): record["is_enabled"] for record in _dnf_records(output)}


def _parse_dnf_source_records(output: str) -> tuple[DnfRepository, ...]:
    """Require complete named records for the configured-source overview."""
    repositories = []
    for record in _dnf_records(output):
        name = record.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Repository name is incomplete")
        repositories.append(DnfRepository(record["id"], name, record["is_enabled"]))
    return tuple(sorted(repositories, key=lambda repo: repo.source_id.casefold()))


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

    def combined_snapshot(self) -> tuple[DnfSourceSnapshot, tuple[SourceStatus, ...]]:
        """Share a single DNF observation with legacy badges and Flatpak scopes."""
        observation = self.sources_snapshot()
        statuses = list(self.badges_from_sources(observation))
        statuses.append(self._flatpak_status(SourceScope.SYSTEM))
        statuses.append(self._flatpak_status(SourceScope.USER))
        return observation, tuple(statuses)

    def sources_snapshot(self) -> DnfSourceSnapshot:
        """Read all configured DNF5 sources without network metadata refresh."""
        observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        def unknown(reason: SourceStatusReason, exit_code: int | None = None) -> DnfSourceSnapshot:
            return DnfSourceSnapshot(observed_at, reason=reason, exit_code=exit_code)
        try:
            package_manager = SystemManager.get_package_manager()
        except (OSError, RuntimeError, TypeError, ValueError):
            return unknown(SourceStatusReason.PROBE_FAILED)
        if package_manager != "dnf5":
            return unknown(SourceStatusReason.UNSUPPORTED_BACKEND)
        if shutil.which(package_manager) is None:
            return unknown(SourceStatusReason.TOOL_UNAVAILABLE)
        try:
            result = subprocess.run(
                [package_manager, "--cacheonly", "repo", "list", "--all", "--json"],
                capture_output=True, text=True, check=False, timeout=_DNF_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return unknown(SourceStatusReason.TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            return unknown(SourceStatusReason.PROBE_FAILED)
        if result.returncode != 0:
            return unknown(SourceStatusReason.COMMAND_FAILED, result.returncode)
        try:
            repositories = _parse_dnf_source_records(result.stdout)
        except (TypeError, ValueError, json.JSONDecodeError):
            return unknown(SourceStatusReason.INVALID_RESPONSE)
        return DnfSourceSnapshot(observed_at, repositories)

    def _dnf_statuses(self) -> tuple[SourceStatus, ...]:
        return self.badges_from_sources(self.sources_snapshot())

    @staticmethod
    def badges_from_sources(snapshot: DnfSourceSnapshot) -> tuple[SourceStatus, ...]:
        """Derive known-source badges from the overview's exact observation."""
        source_ids = ("rpmfusion-free", "rpmfusion-nonfree", "loofi-copr")
        if not snapshot.success:
            return tuple(
                _unknown(source_id, SourceScope.SYSTEM, snapshot.reason or SourceStatusReason.PROBE_FAILED, exit_code=snapshot.exit_code)
                for source_id in source_ids
            )
        repositories = {repo.source_id.casefold(): repo.enabled for repo in snapshot.repositories}

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
    "DnfRepository",
    "DnfSourceSnapshot",
    "SoftwareSourceStatusService",
    "SourceScope",
    "SourceState",
    "SourceStatus",
    "SourceStatusReason",
]
