"""Explicit, bounded DNF5 restart observations shared by GUI and CLI."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from threading import Event
from typing import Callable

from core.actions.contracts import ActionRuntime
from core.executor.action_result import ActionResult
from core.executor.command_facade import CommandFacade
from core.platform.profile import DeploymentBackend, PlatformProfile
from core.tasks.update_flow import STALE_SECONDS
from services.software.update_overview import OverviewCancelled, OverviewRuntime

RESTART_QUERY = ("dnf5", "--cacheonly", "needs-restarting", "--json")


class RestartAdviceRuntime(OverviewRuntime):
    """Allow only the existing cache-only restart inspection vector."""

    _QUERIES = {RESTART_QUERY}


@dataclass(frozen=True)
class RestartAdvice:
    """Session observation; this does not authorize or perform a restart."""

    state: str = "unknown"
    checked_at: str = ""
    packages: tuple[str, ...] = ()
    reason: str = "not_checked"
    stale: bool = True

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["packages"] = list(self.packages)
        return payload


def parse_restart_result(result: ActionResult | None, *, checked_at: str = "") -> RestartAdvice:
    """Accept DNF5's exit code and reboot JSON only when they agree."""
    unknown = RestartAdvice(checked_at=checked_at, reason="tool_unavailable_or_probe_failed", stale=not bool(checked_at))
    if result is None or result.exit_code not in (0, 1):
        return replace(unknown, reason="timeout" if result and result.exit_code == -1 else unknown.reason)
    try:
        rows = json.loads(result.stdout)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError("Invalid reboot response")
        row = rows[0]
        required, packages = row.get("reboot_required"), row.get("packages")
        if row.get("type") != "reboot" or type(required) is not bool or required != (result.exit_code == 1):
            raise ValueError("Inconsistent reboot response")
        if not isinstance(packages, list) or len(packages) > 500 or any(
            not isinstance(package, str) or not re.fullmatch(r"[A-Za-z0-9_.+:-]{1,256}", package) for package in packages
        ):
            raise ValueError("Invalid package names")
        return RestartAdvice("required" if required else "not_required", checked_at, tuple(packages), "dnf5_local_hint", not bool(checked_at))
    except (ValueError, TypeError):
        return replace(unknown, reason="invalid_response")


class RestartAdviceService:
    """Manual observation retained in memory only, with cancellable execution."""

    def __init__(self, *, profile: PlatformProfile | None = None, runtime: ActionRuntime | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.profile = profile
        self._cancelled = Event()
        self.runtime = runtime or RestartAdviceRuntime(CommandFacade(), cancelled=self._cancelled, output_limit=65536)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._advice = RestartAdvice()

    def cancel(self) -> None:
        self._cancelled.set()

    def reset_cancel(self) -> None:
        self._cancelled.clear()

    def load(self) -> RestartAdvice:
        stale = True
        if self._advice.checked_at:
            age = (self._clock() - datetime.fromisoformat(self._advice.checked_at)).total_seconds()
            stale = age < 0 or age >= STALE_SECONDS
        return replace(self._advice, stale=stale)

    def check(self) -> RestartAdvice:
        if self._cancelled.is_set():
            raise OverviewCancelled()
        profile = self.profile or PlatformProfile.detect()
        checked = self._clock().isoformat()
        if not (profile.is_fedora and not profile.is_atomic and profile.deployment_backend is DeploymentBackend.DNF5
                and profile.package_manager_name == "dnf5"):
            advice = RestartAdvice(checked_at=checked, reason="unsupported_backend", stale=False)
        else:
            result = self.runtime.execute_read_only(RESTART_QUERY, action_id="restart-advice", timeout=8)
            advice = parse_restart_result(result, checked_at=self._clock().isoformat())
        if self._cancelled.is_set():
            raise OverviewCancelled()
        self._advice = advice
        return self.load()
