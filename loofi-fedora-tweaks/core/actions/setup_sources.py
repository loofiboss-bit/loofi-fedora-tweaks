"""Reviewed optional source activation and a bounded multimedia recipe."""
from __future__ import annotations

from functools import partial
from typing import Any, Mapping

from core.actions.contracts import ActionDefinition, ActionPlan, ActionRun, ActionRuntime, PolicyDecision, VerificationDecision
from services.software.setup_sources import CODEC_PACKAGES, SOURCES, SetupSourceService, preview_from_facts


def _source_parameters(parameters: Mapping[str, Any], *, flathub: bool) -> PolicyDecision:
    source_id = "flathub" if flathub else parameters.get("source_id")
    scope = parameters.get("scope") if flathub else "system"
    allowed = {"scope"} if flathub else {"source_id"}
    valid = (set(parameters).issubset(allowed) and isinstance(source_id, str) and source_id in SOURCES
             and (flathub or source_id != "flathub") and scope in SOURCES[source_id].scopes)
    return PolicyDecision(bool(valid), "parameters_valid" if valid else "source_selection_required",
                          "Review this exact source and installation scope." if valid else "Choose an approved source and scope explicitly.")


def _source_identity(parameters: Mapping[str, Any], flathub: bool) -> tuple[str, str]:
    return ("flathub", str(parameters["scope"])) if flathub else (str(parameters["source_id"]), "system")


def _source_preflight(parameters: Mapping[str, Any], runtime: ActionRuntime, *, flathub: bool) -> PolicyDecision:
    decision = _source_parameters(parameters, flathub=flathub)
    if not decision.allowed:
        return decision
    if not flathub and (runtime.is_atomic() or runtime.package_manager() != "dnf5"):
        return PolicyDecision(False, "unsupported_backend", "RPM Fusion setup requires traditional Fedora with DNF5.")
    snapshot = SetupSourceService().preview(*_source_identity(parameters, flathub))
    if not snapshot.available or snapshot.state not in {"absent", "key_import_required"}:
        return PolicyDecision(False, "source_already_enabled" if snapshot.state == "enabled" else "source_unavailable",
                              "This source is already enabled with its verified trust settings." if snapshot.state == "enabled" else snapshot.error,
                              facts={"setup_source": snapshot.to_dict()})
    return PolicyDecision(True, "ready", "Review the provider, exact URL, signing fingerprints and scope. No applications will be installed.",
                          facts={"setup_source": snapshot.to_dict()})


def _source_render(parameters: Mapping[str, Any], runtime: ActionRuntime, *, flathub: bool) -> list[str]:
    decision = _source_preflight(parameters, runtime, flathub=flathub)
    if not decision.allowed:
        raise ValueError(decision.explanation)
    return _source_evidence(parameters, runtime, decision)


def _source_evidence(_parameters: Mapping[str, Any], _runtime: ActionRuntime, decision: PolicyDecision) -> list[str]:
    return preview_from_facts(decision.facts.get("setup_source")).apply_vector()


def _source_verify(_run: ActionRun, plan: ActionPlan, _runtime: ActionRuntime) -> VerificationDecision:
    try:
        reviewed = preview_from_facts(plan.policy_decision.facts.get("setup_source"))
    except (ValueError, TypeError):
        return VerificationDecision.failed("Source trust evidence is unavailable; create a fresh review.")
    observed = SetupSourceService().preview(reviewed.source_id, reviewed.scope)
    if observed.available and observed.state == "enabled":
        return VerificationDecision.succeeded("The exact source URL, signing key and scope were independently verified.", source=observed.to_dict())
    return VerificationDecision.failed("The selected source could not be verified. Inspect its configuration before trying again.", source=observed.to_dict())


def _codec_validate(parameters: Mapping[str, Any]) -> PolicyDecision:
    valid = set(parameters).issubset({"removal_consent"}) and isinstance(parameters.get("removal_consent", False), bool)
    return PolicyDecision(valid, "parameters_valid" if valid else "invalid_codec_consent",
                          "Only the predefined FFmpeg/GStreamer recipe is supported.")


def _codec_preflight(parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    validation = _codec_validate(parameters)
    if not validation.allowed:
        return validation
    if runtime.is_atomic() or runtime.package_manager() != "dnf5":
        return PolicyDecision(False, "unsupported_backend", "The codec recipe requires traditional Fedora with DNF5.")
    source = SetupSourceService().preview("rpmfusion-free", "system")
    if not source.available or source.state != "enabled":
        return PolicyDecision(False, "codec_source_required", "Review and enable RPM Fusion Free first, verify it, then create a fresh codec review.")
    from services.software.rpm_transactions import RpmTransactionService

    transaction = RpmTransactionService(runtime).preview("codecs", CODEC_PACKAGES, allow_replacements=parameters.get("removal_consent", False))
    if not transaction.available:
        return PolicyDecision(False, "codec_transaction_unavailable", transaction.error or "The codec transaction could not be safely resolved.")
    incoming = {(item["name"], item["nevra"].rpartition(".")[2]) for item in transaction.operations if item["action"] in {"Install", "Upgrade", "Reinstall"}}
    removals = [item for item in transaction.operations if item.get("action") in {"Remove", "Replaced"}
                and not (item["action"] == "Replaced" and (item["name"], item["nevra"].rpartition(".")[2]) in incoming)]
    if removals and not parameters.get("removal_consent", False):
        return PolicyDecision(False, "codec_removal_consent_required", "Codec replacements require separate removal consent and a fresh complete review.")
    return PolicyDecision(True, "ready", "Review the complete multimedia transaction, including every permitted replacement.",
                          facts={"rpm_transaction": transaction.to_dict(), "setup_source": source.to_dict()})


def _codec_evidence(_parameters: Mapping[str, Any], _runtime: ActionRuntime, decision: PolicyDecision) -> list[str]:
    from services.software.rpm_transactions import preview_from_facts as rpm_preview_from_facts

    return rpm_preview_from_facts(decision.facts.get("rpm_transaction")).apply_vector()


def _codec_render(parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    decision = _codec_preflight(parameters, runtime)
    if not decision.allowed:
        raise ValueError(decision.explanation)
    return _codec_evidence(parameters, runtime, decision)


def _codec_verify(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    from services.software.rpm_transactions import preview_from_facts as rpm_preview_from_facts, verify_preview

    try:
        return verify_preview(rpm_preview_from_facts(plan.policy_decision.facts.get("rpm_transaction")), runtime)
    except (ValueError, TypeError):
        return VerificationDecision.failed("Codec transaction evidence is invalid; inspect RPM inventory and review again.")


def setup_source_definitions() -> tuple[ActionDefinition, ...]:
    result = []
    for flathub, action_id, title, capability in (
        (True, "enable-flathub", "Enable Flathub", "software.flathub.enable"),
        (False, "enable-rpm-fusion", "Enable RPM Fusion source", "software.rpmfusion.enable"),
    ):
        result.append(ActionDefinition(
            id=action_id, capability_id=capability, title=title,
            description="Add one optional source with pinned signing trust and explicit installation scope.",
            parameter_schema={"scope": {"type": "string", "required": True}} if flathub else {"source_id": {"type": "string", "required": True}},
            risk_level="medium", privileged=not flathub, confirmation_policy="explicit-no-rollback", rollback_supported=False,
            recovery_guidance="Source activation preserves installed apps and data. Inspect source configuration before disabling it manually.",
            command_renderer=partial(_source_render, flathub=flathub),
            evidence_renderer=_source_evidence,
            preflight_checker=partial(_source_preflight, flathub=flathub),
            parameter_validator=partial(_source_parameters, flathub=flathub),
            privilege_resolver=(lambda p, _r: p.get("scope") == "system") if flathub else None,
            verifier=_source_verify, interaction_policy="review", affected_resources=("software-sources",),
            supported_variants=frozenset({"traditional", "atomic"}) if flathub else frozenset({"traditional"}),
        ))
    result.append(ActionDefinition(
        id="install-multimedia-codecs", capability_id="software.codecs.install", title="Install multimedia codecs",
        description="Review a fixed FFmpeg/GStreamer recipe after separately verifying its source.",
        parameter_schema={"removal_consent": {"type": "boolean", "required": False}},
        risk_level="medium", privileged=True, confirmation_policy="explicit-no-rollback", rollback_supported=False,
        recovery_guidance="Application data is preserved. Reinstall the previous package versions manually if needed; no automatic rollback is available.",
        parameter_validator=_codec_validate, preflight_checker=_codec_preflight, command_renderer=_codec_render,
        evidence_renderer=_codec_evidence, verifier=_codec_verify, interaction_policy="review",
        supported_variants=frozenset({"traditional"}), affected_resources=("rpm-packages", "multimedia"),
    ))
    return tuple(result)
