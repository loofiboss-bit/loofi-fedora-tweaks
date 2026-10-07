"""Reviewed unused-runtime cleanup bound to exact local installation evidence."""
from __future__ import annotations

from typing import Any, Mapping

from core.actions.contracts import ActionDefinition, ActionPlan, ActionRun, ActionRuntime, PolicyDecision, VerificationDecision
from services.software.flatpak_maintenance import DIGEST_PATTERN, FlatpakMaintenanceService, helper_command, validate_helper_args

ACTION_ID = "remove-unused-flatpaks"


def _args(parameters: Mapping[str, Any]) -> list[str]:
    refs = parameters.get("refs")
    if not isinstance(refs, (list, tuple)) or not refs or any(not isinstance(ref, str) for ref in refs):
        raise ValueError("Select exact runtime refs.")
    installation = parameters.get("installation")
    digest = parameters.get("snapshot_digest")
    if not isinstance(installation, str) or not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
        raise ValueError("Invalid cleanup identity.")
    args = ["apply", "--installation", installation, "--snapshot-digest", digest]
    for ref in refs:
        args.extend(("--ref", ref))
    if not validate_helper_args(args):
        raise ValueError("Invalid cleanup command.")
    return args


def _validate(parameters: Mapping[str, Any]) -> PolicyDecision:
    try:
        _args(parameters)
    except (ValueError, TypeError):
        return PolicyDecision(False, "invalid_cleanup_identity", "Review an installation and select its exact unused runtime refs.")
    return PolicyDecision(True, "parameters_valid", "The cleanup selection is bound to one installation snapshot.")


def _snapshot(parameters: Mapping[str, Any]):
    return FlatpakMaintenanceService().unused(str(parameters["installation"]))


def _preflight(parameters: Mapping[str, Any], _runtime: ActionRuntime) -> PolicyDecision:
    validation = _validate(parameters)
    if not validation.allowed:
        return validation
    snapshot = _snapshot(parameters)
    if not snapshot.available:
        return PolicyDecision(False, "flatpak_evidence_unavailable", snapshot.error)
    if snapshot.digest != parameters["snapshot_digest"] or not set(parameters["refs"]).issubset({item.ref for item in snapshot.refs}):
        return PolicyDecision(False, "flatpak_snapshot_changed", "Candidates, commits or pins changed. Review a fresh unused-runtime snapshot.")
    return PolicyDecision(True, "ready", "Only the selected unused runtimes will be removed. Application data is preserved.", facts=snapshot.to_dict())


def _render(parameters: Mapping[str, Any], _runtime: ActionRuntime) -> list[str]:
    # The reviewed digest travels unchanged; neither rendering nor execution expands refs.
    return [helper_command(), *_args(parameters)]


def _verify(_run: ActionRun, plan: ActionPlan, _runtime: ActionRuntime) -> VerificationDecision:
    snapshot = _snapshot(plan.parameters)
    if not snapshot.available:
        return VerificationDecision.failed("Cleanup outcome could not be inspected.", observation_error=snapshot.error)
    selected = set(plan.parameters["refs"])
    before = {item["ref"] for item in plan.policy_decision.facts.get("installed", [])}
    after = {item.ref for item in snapshot.installed}
    removed, remaining = sorted(selected - after), sorted(selected & after)
    unexpected = sorted(before - selected - after)
    facts = {"removed_refs": removed, "remaining_refs": remaining, "unexpected_missing_refs": unexpected,
             "installation": snapshot.installation, "data_preserved": True}
    if remaining or unexpected:
        return VerificationDecision.failed("Cleanup was partial or installation state differed from the plan; review observed refs.", **facts)
    return VerificationDecision.succeeded("Selected runtimes are absent and every other installed ref remains. Application data was preserved.", **facts)


def flatpak_cleanup_definitions() -> list[ActionDefinition]:
    return [ActionDefinition(
        id=ACTION_ID, capability_id="maintenance.flatpak.unused", title="Remove unused Flatpak runtimes",
        description="Remove only reviewed unused runtimes from one exact installation, preserving application data.",
        parameter_schema={"installation": {"type": "string", "required": True}, "refs": {"type": "array", "required": True},
                          "snapshot_digest": {"type": "string", "required": True}},
        risk_level="medium", privileged=False, confirmation_policy="explicit-no-rollback", rollback_supported=False,
        recovery_guidance="Reinstall any removed runtime manually from its configured source if needed. Application data is preserved.",
        command_renderer=_render, preflight_checker=_preflight, verifier=_verify, parameter_validator=_validate,
        interaction_policy="review", affected_resources=("flatpak-runtimes",),
    )]
