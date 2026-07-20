"""Deny-by-default catalog for audited first-party maintenance actions."""

from __future__ import annotations

import re
import platform
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.actions.contracts import ActionDefinition, ActionRun, ActionRuntime, PolicyDecision
from core.executor.action_result import ActionResult
from core.executor.command_facade import CommandFacade
from services.system.system import SystemManager

_UNIT_PATTERN = re.compile(r"^[A-Za-z0-9_.@:-]+$")
_TRIMMED_PATTERN = re.compile(r"^\s*\S.*:\s+.+(?:trimmed|bytes?)", re.IGNORECASE)


class SystemActionRuntime:
    """Read-only probe adapter backed by CommandFacade and SystemManager."""

    def __init__(self, facade: CommandFacade, system_manager: type[SystemManager] = SystemManager):
        self.facade = facade
        self.system_manager = system_manager

    def is_atomic(self) -> bool:
        return bool(self.system_manager.is_atomic())

    def package_manager(self) -> str:
        return str(self.system_manager.get_package_manager())

    def fedora_version(self) -> str:
        """Return the actual Fedora host version, or empty outside Fedora."""
        try:
            release = platform.freedesktop_os_release()
        except OSError:
            return ""
        if release.get("ID", "").lower() != "fedora":
            return ""
        return str(release.get("VERSION_ID", "")).strip()

    def boot_id(self) -> str:
        """Return the kernel boot identity without probing a subprocess."""
        try:
            return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def execute_read_only(self, vector: Sequence[str], *, action_id: str, timeout: int = 30) -> ActionResult:
        return self.facade.execute(vector, privileged=False, timeout=timeout, action_id=action_id)

    def package_manager_busy(self) -> bool:
        lock_paths = [
            "/var/lib/dnf/metadata_lock.pid",
            "/var/lib/dnf/lock",
            "/var/lib/rpm/.rpm.lock",
        ]
        probe = self.execute_read_only(
            ["fuser", *lock_paths],
            action_id="action-center-preflight-package-lock",
            timeout=10,
        )
        # fuser returns 0 when a process holds the file and 1 when no process does.
        # Unknown probe failures block conservatively.
        return probe.success or probe.exit_code not in {1}

    def failed_services(self) -> tuple[bool, list[str], str]:
        probe = self.execute_read_only(
            ["systemctl", "--failed", "--no-legend", "--no-pager", "--plain"],
            action_id="action-center-preflight-failed-services",
            timeout=15,
        )
        if not probe.success:
            return False, [], probe.message
        units: list[str] = []
        for line in probe.stdout.splitlines():
            parts = line.lstrip("● ").split()
            if parts and _UNIT_PATTERN.fullmatch(parts[0]):
                units.append(parts[0])
        return True, sorted(set(units)), ""

    def fstrim_support(self) -> tuple[bool, dict[str, Any], str]:
        version = self.execute_read_only(
            ["fstrim", "--version"],
            action_id="action-center-preflight-fstrim-version",
            timeout=10,
        )
        if not version.success:
            return False, {"fstrim_available": False, "discard_supported": False}, "fstrim is unavailable."
        discard = self.execute_read_only(
            ["lsblk", "-D", "-n", "-o", "DISC-MAX"],
            action_id="action-center-preflight-discard",
            timeout=10,
        )
        if not discard.success:
            return False, {"fstrim_available": True, "discard_supported": False}, "Discard capability could not be verified."
        supported = any(_nonzero_size(line) for line in discard.stdout.splitlines())
        facts = {"fstrim_available": True, "discard_supported": supported}
        if not supported:
            return False, facts, "No mounted block device reported discard support."
        return True, facts, ""


class ActionCatalog:
    """Fixed v17 catalog. Unknown, plugin, and free-form actions stay manual-only."""

    def __init__(self, definitions: Sequence[ActionDefinition] | None = None):
        if definitions is None:
            from core.actions.assurance import assurance_definitions

            selected = [*_first_party_definitions(), *assurance_definitions()]
        else:
            selected = list(definitions)
        self._definitions = {definition.id: definition for definition in selected}

    def get(self, action_id: str) -> ActionDefinition | None:
        return self._definitions.get(action_id)

    def list(self) -> list[ActionDefinition]:
        return [self._definitions[key] for key in sorted(self._definitions)]

    @staticmethod
    def denied(action_id: str) -> PolicyDecision:
        return PolicyDecision(
            allowed=False,
            reason_code="manual_only",
            explanation=f"Action '{action_id}' has no audited v17 first-party definition.",
            alternative="Review the recommendation and perform any follow-up manually.",
            facts={"action_id": action_id, "catalog": "v17-deny-by-default"},
        )


def validate_parameters(definition: ActionDefinition, parameters: Mapping[str, Any]) -> PolicyDecision:
    """Validate the deliberately small v17 parameter schema without coercion."""
    unknown = sorted(set(parameters) - set(definition.parameter_schema))
    if unknown:
        return PolicyDecision(
            False,
            "invalid_parameters",
            f"Unknown parameters: {', '.join(unknown)}.",
            "Use only parameters declared by the action definition.",
            {"unknown_parameters": unknown},
        )
    for name, schema in definition.parameter_schema.items():
        value = parameters.get(name)
        if schema.get("required") and (value is None or value == ""):
            return PolicyDecision(False, "missing_parameter", f"Parameter '{name}' is required.", facts={"parameter": name})
        if value is not None and schema.get("type") == "string" and not isinstance(value, str):
            return PolicyDecision(False, "invalid_parameter_type", f"Parameter '{name}' must be a string.", facts={"parameter": name})
        if name == "service" and isinstance(value, str) and not _UNIT_PATTERN.fullmatch(value):
            return PolicyDecision(
                False,
                "invalid_service_unit",
                "The service unit contains rejected characters.",
                "Select an exact unit from the fresh failed-service list.",
                {"parameter": name},
            )
    if definition.parameter_validator is not None:
        return definition.parameter_validator(parameters)
    return PolicyDecision(True, "parameters_valid", "Parameters are valid.")


def _first_party_definitions() -> list[ActionDefinition]:
    return [
        ActionDefinition(
            id="dnf-clean-all",
            capability_id="maintenance.package-cache.clean",
            title="Clean package metadata cache",
            description="Clear Traditional Fedora package metadata and verify repository health.",
            parameter_schema={},
            risk_level="low",
            privileged=True,
            confirmation_policy="explicit",
            recovery_guidance="The package manager rebuilds metadata on the next repository query.",
            rollback_supported=True,
            command_renderer=_render_dnf_clean,
            preflight_checker=_preflight_dnf_clean,
            verifier=_verify_dnf_clean,
        ),
        ActionDefinition(
            id="restart-failed-service",
            capability_id="maintenance.service.restart-failed",
            title="Restart a failed service",
            description="Restart one exact unit selected from a fresh failed-service query.",
            parameter_schema={"service": {"type": "string", "required": True}},
            risk_level="medium",
            privileged=True,
            confirmation_policy="explicit-no-rollback",
            recovery_guidance="Inspect the unit journal and stop the service if restarting introduces a regression.",
            rollback_supported=False,
            command_renderer=_render_service_restart,
            preflight_checker=_preflight_service_restart,
            verifier=_verify_service_restart,
        ),
        ActionDefinition(
            id="fstrim-all",
            capability_id="maintenance.storage.trim",
            title="Trim supported filesystems",
            description="Issue discard for mounted filesystems only after discard support is verified.",
            parameter_schema={},
            risk_level="low",
            privileged=True,
            confirmation_policy="explicit",
            recovery_guidance="Discard is not reversible; review storage health if the command reports errors.",
            rollback_supported=False,
            command_renderer=lambda _parameters, _runtime: ["fstrim", "-av"],
            preflight_checker=_preflight_fstrim,
            verifier=_verify_fstrim,
        ),
    ]


def _render_dnf_clean(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    manager = runtime.package_manager()
    return [manager if manager in {"dnf", "dnf5"} else "dnf", "clean", "all"]


def _preflight_dnf_clean(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    atomic = runtime.is_atomic()
    manager = runtime.package_manager()
    if atomic:
        return PolicyDecision(
            False,
            "atomic_manual_only",
            "dnf-clean-all is not executable on Atomic Fedora.",
            "Use rpm-ostree status and documented cleanup guidance without translating this action automatically.",
            {"atomic": True, "package_manager": manager},
        )
    if manager not in {"dnf", "dnf5"}:
        return PolicyDecision(
            False,
            "unsupported_package_manager",
            f"Unsupported package manager: {manager}.",
            facts={"atomic": False, "package_manager": manager},
        )
    busy = runtime.package_manager_busy()
    if busy:
        return PolicyDecision(
            False,
            "package_manager_busy",
            "Another package operation may be active.",
            "Wait for the active package operation to finish, then create a new plan.",
            {"atomic": False, "package_manager": manager, "package_manager_busy": True},
        )
    return PolicyDecision(
        True,
        "preflight_ok",
        "Traditional Fedora package manager is idle.",
        facts={"atomic": False, "package_manager": manager, "package_manager_busy": False},
    )


def _verify_dnf_clean(_run: ActionRun, _plan: object, runtime: ActionRuntime) -> ActionResult:
    manager = runtime.package_manager()
    if manager not in {"dnf", "dnf5"}:
        return ActionResult.fail("Package manager changed after execution.", action_id="dnf-clean-all")
    repo = runtime.execute_read_only([manager, "repolist", "--enabled"], action_id="dnf-clean-all-verify-repos", timeout=60)
    if not repo.success:
        return ActionResult.fail("Enabled repository health check failed.", exit_code=repo.exit_code, action_id="dnf-clean-all")
    packages = runtime.execute_read_only([manager, "check"], action_id="dnf-clean-all-verify-packages", timeout=120)
    if not packages.success:
        return ActionResult.fail("Installed package health check failed.", exit_code=packages.exit_code, action_id="dnf-clean-all")
    return ActionResult.ok(
        "Repository and package health checks passed.",
        data={"repository_health": "passed", "package_health": "passed"},
        action_id="dnf-clean-all",
    )


def _render_service_restart(parameters: Mapping[str, Any], _runtime: ActionRuntime) -> list[str]:
    return ["systemctl", "restart", str(parameters.get("service", ""))]


def _preflight_service_restart(parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    selected = str(parameters.get("service", ""))
    success, units, error = runtime.failed_services()
    facts = {"service": selected, "failed_services": units}
    if not success:
        return PolicyDecision(
            False,
            "failed_service_probe_failed",
            f"Failed services could not be queried: {error}",
            "Inspect systemctl --failed manually.",
            facts,
        )
    if selected not in units:
        return PolicyDecision(
            False,
            "service_not_freshly_failed",
            f"{selected} is not present in the fresh failed-service list.",
            "Refresh the finding and select an exact failed unit.",
            facts,
        )
    return PolicyDecision(True, "preflight_ok", f"{selected} is currently failed.", facts=facts)


def _verify_service_restart(run: ActionRun, _plan: object, runtime: ActionRuntime) -> ActionResult:
    service = str(run.parameters.get("service", ""))
    if not service or not _UNIT_PATTERN.fullmatch(service):
        return ActionResult.fail("The persisted service parameter is invalid.", action_id="restart-failed-service")
    active = runtime.execute_read_only(
        ["systemctl", "is-active", service],
        action_id="restart-failed-service-verify-active",
        timeout=30,
    )
    queried, failed, error = runtime.failed_services()
    if not active.success or not queried or service in failed:
        detail = error or "Service is not active or remains in the failed list."
        return ActionResult.fail(detail, exit_code=active.exit_code, action_id="restart-failed-service")
    return ActionResult.ok(
        f"{service} is active and no longer failed.",
        data={"service": service, "active": True, "still_failed": False},
        action_id="restart-failed-service",
    )


def _preflight_fstrim(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    supported, facts, explanation = runtime.fstrim_support()
    if not supported:
        return PolicyDecision(
            False,
            "fstrim_unsupported",
            explanation,
            "Keep this action manual-only and inspect block-device discard capabilities.",
            facts,
        )
    return PolicyDecision(True, "preflight_ok", "fstrim and discard support were verified.", facts=facts)


def _verify_fstrim(run: ActionRun, _plan: object, _runtime: ActionRuntime) -> ActionResult:
    execution = run.execution_result or {}
    output = str(execution.get("stdout", ""))
    validated = [line.strip() for line in output.splitlines() if _TRIMMED_PATTERN.search(line)]
    if not bool(execution.get("success", False)) or execution.get("exit_code") != 0 or not validated:
        return ActionResult.fail(
            "fstrim did not report a validated filesystem result.",
            action_id="fstrim-all",
            data={"validated_filesystem_count": 0},
        )
    return ActionResult.ok(
        "fstrim reported at least one validated filesystem result.",
        action_id="fstrim-all",
        data={"validated_filesystem_count": len(validated)},
    )


def _nonzero_size(value: str) -> bool:
    normalized = value.strip().replace(" ", "")
    match = re.match(r"^(\d+(?:\.\d+)?)", normalized)
    return bool(match and float(match.group(1)) > 0)
