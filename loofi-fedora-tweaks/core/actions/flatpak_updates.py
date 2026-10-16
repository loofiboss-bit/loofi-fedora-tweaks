"""Reviewed updates with installation and complete transaction authority."""
from __future__ import annotations

from typing import Any, Mapping

from core.actions.contracts import ActionDefinition, ActionPlan, ActionRun, ActionRuntime, PolicyDecision, VerificationDecision
from services.software.flatpak_maintenance import DIGEST_PATTERN, INSTALLATION_PATTERN, REF_PATTERN, FlatpakMaintenanceService, helper_command
from services.software.flatpak_updates import FlatpakUpdatesService, apply_vector, snapshot_from_facts


def _validate(parameters: Mapping[str, Any]) -> PolicyDecision:
    installation, refs = parameters.get("installation"), parameters.get("refs", [])
    valid = ((installation is None or (isinstance(installation, str) and INSTALLATION_PATTERN.fullmatch(installation)))
             and isinstance(refs, (tuple, list)) and len(refs) <= 256
             and all(isinstance(ref, str) and REF_PATTERN.fullmatch(ref) for ref in refs))
    if valid and len(set(refs)) == len(refs):
        return PolicyDecision(True, "parameters_valid", "Exact Flatpak installations and refs will be reviewed.")
    return PolicyDecision(False, "invalid_flatpak_identity", "Select valid full refs and an installation.")


def _snapshot(parameters: Mapping[str, Any]):
    return FlatpakUpdatesService().preview(parameters.get("installation"), tuple(parameters.get("refs", ())))


def _preflight(parameters: Mapping[str, Any], _runtime: ActionRuntime) -> PolicyDecision:
    validation = _validate(parameters)
    if not validation.allowed:
        return validation
    snapshot = _snapshot(parameters)
    if not snapshot.available or any(not item.available for item in snapshot.installations):
        return PolicyDecision(False, "flatpak_updates_unavailable", "Every selected installation requires complete update evidence.", facts={"flatpak_updates": snapshot.review_facts()})
    if not snapshot.candidates:
        return PolicyDecision(False, "no_flatpak_updates", "No Flatpak updates are currently available.")
    return PolicyDecision(True, "ready", "Review selected apps and all required runtime and extension operations.", facts={"flatpak_updates": snapshot.review_facts()})


def _render(parameters: Mapping[str, Any], _runtime: ActionRuntime) -> list[str]:
    return apply_vector(_snapshot(parameters))


def _render_evidence(_parameters: Mapping[str, Any], _runtime: ActionRuntime, decision: PolicyDecision) -> list[str]:
    return apply_vector(snapshot_from_facts(decision.facts.get("flatpak_updates")))


def _verify(run: ActionRun, plan: ActionPlan, _runtime: ActionRuntime) -> VerificationDecision:
    evidence = plan.policy_decision.facts.get("flatpak_updates", {})
    scopes = evidence.get("installations") if isinstance(evidence, dict) else None
    if not isinstance(evidence, dict) or evidence.get("evidence_version") != 1 or not isinstance(scopes, list) or not scopes:
        return VerificationDecision.failed("Legacy update evidence has no installation identity; create a fresh review.")
    results = []
    for scope in scopes:
        if not isinstance(scope, dict) or not isinstance(scope.get("operations"), (list, tuple)):
            return VerificationDecision.failed("Update operation evidence is invalid.")
        name = scope.get("installation")
        if not isinstance(name, str) or not INSTALLATION_PATTERN.fullmatch(name):
            return VerificationDecision.failed("Update installation evidence is invalid.")
        for operation in scope.get("operations", []):
            if not isinstance(operation, dict):
                return VerificationDecision.failed("Update operation evidence is invalid.")
            ref, expected = operation.get("ref", ""), operation.get("expected_commit", "")
            if not isinstance(ref, str) or not isinstance(expected, str) or not REF_PATTERN.fullmatch(ref) or not DIGEST_PATTERN.fullmatch(expected):
                return VerificationDecision.failed("Update commit evidence is invalid.")
            # Reuse details's exact installation lookup, with explicit commit readback.
            payload = FlatpakMaintenanceService._probe((helper_command(), "update-state", "--installation", name, "--ref", ref))
            observed = payload.get("commit", "") if payload.get("available") and payload.get("installation") == name and payload.get("ref") == ref else None
            status = "verified" if observed == expected else "unverified" if observed is None else "cancelled" if run.state == "cancelled" else "unverified" if run.state == "interrupted" else "failed"
            results.append({"installation": name, "ref": ref, "expected_commit": expected, "observed_commit": observed, "status": status})
    if not results or any(item["status"] != "verified" for item in results):
        return VerificationDecision.failed("Some Flatpak commits could not be verified; review each observed result.", results=results)
    return VerificationDecision.succeeded("All reviewed app and dependency commits were verified in their exact installations.", results=results)


def flatpak_update_definition() -> ActionDefinition:
    return ActionDefinition(id="update-flatpaks", capability_id="updates.flatpak.apply", title="Update Flatpaks",
                            description="Update reviewed apps and dependencies within their exact installations.",
                            parameter_schema={"installation": {"type": "string", "required": False}, "refs": {"type": "array", "required": False}},
                            risk_level="low", privileged=False, confirmation_policy="explicit", rollback_supported=False,
                            recovery_guidance="Review Activity and Flatpak history if an update regresses. Application data is preserved.",
                            command_renderer=_render, evidence_renderer=_render_evidence, preflight_checker=_preflight, verifier=_verify, parameter_validator=_validate,
                            interaction_policy="confirm", affected_resources=("flatpak-applications", "flatpak-runtimes"))
