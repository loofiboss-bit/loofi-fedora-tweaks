"""Audited removal of one exact Flatpak installation, preserving app data."""
from __future__ import annotations

import re
from typing import Any, Mapping

from core.actions.contracts import ActionDefinition, ActionPlan, ActionRun, ActionRuntime, PolicyDecision, VerificationDecision
from services.software.installed_applications import InstalledApplicationService, installation_flag, validate_ref

ACTION_ID = "remove-installed-flatpak"


def _validate(parameters: Mapping[str, Any]) -> PolicyDecision:
    try:
        installation_flag(parameters.get("installation", ""))
        if not validate_ref(parameters.get("ref", "")):
            raise ValueError("An exact installed Flatpak app ref is required.")
    except (ValueError, TypeError):
        return PolicyDecision(False, "invalid_flatpak_identity", "Select an exact Flatpak ref and installation.")
    return PolicyDecision(True, "parameters_valid", "Exact installation identity is valid.")


def _inventory(runtime: ActionRuntime):
    return InstalledApplicationService(probe=lambda vector: runtime.execute_read_only(vector, action_id=ACTION_ID, timeout=15)).flatpaks()


def _preflight(parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    validation = _validate(parameters)
    if not validation.allowed:
        return validation
    inventory = _inventory(runtime)
    if inventory.errors:
        return PolicyDecision(False, "inventory_unknown", inventory.errors[0])
    target = next((app for app in inventory.applications if app.ref == parameters["ref"] and app.installation == parameters["installation"]), None)
    if target is None:
        return PolicyDecision(False, "not_installed", "The selected ref is no longer installed in this installation.")
    running = runtime.execute_read_only(("flatpak", "ps", "--columns=application"), action_id=ACTION_ID, timeout=15)
    if not running.success:
        return PolicyDecision(False, "running_state_unknown", "Running Flatpak applications could not be checked.")
    running_ids = tuple(line.strip() for line in running.stdout.splitlines() if line.strip())
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,255}", app_id) for app_id in running_ids):
        return PolicyDecision(False, "running_state_unknown", "Flatpak returned an invalid running application list.")
    if target.app_id in running_ids:
        return PolicyDecision(False, "application_running", "Close this application before removing it.")
    return PolicyDecision(True, "ready", "Remove only this installed ref; application data is preserved.", facts={"installation": target.installation, "ref": target.ref})


def _render(parameters: Mapping[str, Any], _runtime: ActionRuntime):
    if not _validate(parameters).allowed:
        raise ValueError("Invalid Flatpak identity.")
    return ("flatpak", "uninstall", installation_flag(parameters["installation"]), "--assumeyes", "--noninteractive", "--no-related", parameters["ref"])


def _verify(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    inventory = _inventory(runtime)
    if inventory.errors:
        return VerificationDecision.failed("Removal could not be verified: installation inventory is unreadable.")
    if any(app.ref == plan.parameters["ref"] and app.installation == plan.parameters["installation"] for app in inventory.applications):
        return VerificationDecision.failed("The selected Flatpak ref is still installed.")
    return VerificationDecision.succeeded("The selected ref was removed. Application data was preserved.")


def installed_application_definitions() -> list[ActionDefinition]:
    return [ActionDefinition(
        id=ACTION_ID, capability_id="applications.flatpak.remove-installed", title="Remove installed Flatpak",
        description="Remove one exact app ref in one installation, preserving its user data.",
        parameter_schema={"ref": {"type": "string", "required": True}, "installation": {"type": "string", "required": True}},
        risk_level="medium", privileged=False, confirmation_policy="explicit-no-rollback", rollback_supported=False,
        recovery_guidance="Reinstall the application from its configured source. User data remains available.",
        command_renderer=_render, preflight_checker=_preflight, verifier=_verify, parameter_validator=_validate,
        interaction_policy="review", affected_resources=("flatpak-applications",),
    )]
