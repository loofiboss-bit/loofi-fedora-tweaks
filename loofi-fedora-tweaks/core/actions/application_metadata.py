"""Explicit source-bound metadata refresh through the shared Action Center."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from core.actions.contracts import ActionDefinition, ActionPlan, ActionRun, ActionRuntime, PolicyDecision, VerificationDecision
from services.software.installed_applications import installation_flag

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _validate(parameters: Mapping[str, Any]) -> PolicyDecision:
    source = parameters.get("source")
    valid = source == "fedora" and set(parameters) == {"source"}
    if source == "flatpak":
        valid = set(parameters) == {"source", "installation", "remote"} and all(isinstance(parameters.get(key), str) and _ID.fullmatch(parameters[key]) for key in ("installation", "remote"))
    return PolicyDecision(bool(valid), "parameters_valid" if valid else "invalid_metadata_source", "Refresh one explicitly selected configured metadata source." if valid else "Select an exact metadata source and installation.")


def _identity(parameters: Mapping[str, Any], runtime: ActionRuntime) -> str:
    if parameters["source"] == "fedora":
        from services.software.rpm_transactions import helper_command
        result = runtime.execute_read_only([helper_command(), "sources"], action_id="metadata-configured-repositories", timeout=20)
    else:
        scope = installation_flag(str(parameters["installation"]))
        result = runtime.execute_read_only(["flatpak", "remotes", scope, "--columns=name,url,options"], action_id="metadata-configured-remotes", timeout=20)
    if not result.success:
        return ""
    if parameters["source"] == "flatpak":
        matches = [line for line in result.stdout.splitlines() if line.split("\t", 1)[0] == parameters["remote"]]
        if len(matches) != 1 or len(matches[0].split("\t")) != 3 or "disabled" in matches[0].split("\t")[2].split(","):
            return ""
        text = matches[0]
    else:
        import json
        try:
            records = json.loads(result.stdout)
            if (not isinstance(records, dict) or records.get("available") is not True
                    or not isinstance(records.get("enabled_count"), int) or records["enabled_count"] < 1
                    or not isinstance(records.get("repository_digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", records["repository_digest"])):
                return ""
            text = records["repository_digest"]
        except (TypeError, ValueError):
            return ""
    return hashlib.sha256(text.encode()).hexdigest()


def _preflight(parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    validation = _validate(parameters)
    if not validation.allowed:
        return validation
    if parameters["source"] == "fedora" and (runtime.is_atomic() or runtime.package_manager() != "dnf5"):
        return PolicyDecision(False, "unsupported_metadata_backend", "RPM metadata refresh requires traditional Fedora with DNF5.")
    if parameters["source"] == "fedora" and runtime.package_manager_busy():
        return PolicyDecision(False, "package_manager_busy", "Wait for the current package operation to finish.")
    identity = _identity(parameters, runtime)
    if not identity:
        return PolicyDecision(False, "metadata_source_unavailable", "The exact enabled metadata source could not be verified.")
    message = "Download metadata only; no applications are installed or updated."
    if parameters["source"] == "fedora":
        message = "Refresh DNF metadata only; no packages are installed or updated. Packaged RPM AppStream catalogs require a separate reviewed package update."
    return PolicyDecision(True, "metadata_refresh_ready", message, facts={"metadata_evidence_version": 1, "configured_identity": identity, "metadata_source": dict(parameters)})


def _render(parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    if parameters["source"] == "fedora":
        return [runtime.package_manager(), "--assumeno", "makecache", "--refresh"]
    return ["flatpak", "update", "--appstream", "--noninteractive", installation_flag(str(parameters["installation"])), str(parameters["remote"])]


def _verify(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    facts = plan.policy_decision.facts
    if facts.get("metadata_evidence_version") != 1 or facts.get("metadata_source") != dict(plan.parameters):
        return VerificationDecision.failed("Metadata source evidence is missing; create a fresh review.")
    identity = _identity(plan.parameters, runtime)
    if not identity or identity != facts.get("configured_identity"):
        return VerificationDecision.failed("The selected metadata source changed or could not be verified.")
    if plan.parameters["source"] == "fedora":
        vector = [runtime.package_manager(), "--cacheonly", "repoquery", "--available", "--queryformat", "%{name}\t%{repoid}\n", "--whatprovides", "system-release"]
    else:
        vector = ["flatpak", "remote-ls", "--cached", "--app", installation_flag(str(plan.parameters["installation"])), "--columns=application,branch,arch", str(plan.parameters["remote"])]
    result = runtime.execute_read_only(vector, action_id="metadata-cache-readback", timeout=30)
    if not result.success or not result.stdout.strip():
        return VerificationDecision.failed("The refreshed source has no independently readable application metadata.")
    if plan.parameters["source"] == "fedora":
        from services.software.application_discovery import rpm_appstream_catalog_available
        if not rpm_appstream_catalog_available():
            return VerificationDecision.failed("The DNF cache is readable, but the RPM AppStream catalog is missing or invalid. Review installation or update of appstream-data separately; this metadata-only operation installs no packages.")
        return VerificationDecision.succeeded("DNF metadata was refreshed and a local RPM AppStream catalog is readable. The packaged AppStream catalog is updated separately through a reviewed package transaction.", configured_identity=identity)
    return VerificationDecision.succeeded("Metadata refresh completed and the selected source's local cache is readable.", configured_identity=identity)


def metadata_refresh_definition() -> ActionDefinition:
    return ActionDefinition(
        id="refresh-application-metadata", capability_id="applications.metadata.refresh", title="Refresh application metadata",
        description="Download metadata from one configured source. No package installation, update or removal is started.",
        parameter_schema={"source": {"type": "string", "required": True}, "installation": {"type": "string", "required": False}, "remote": {"type": "string", "required": False}},
        risk_level="low", privileged=False, privilege_resolver=lambda p, _r: p.get("source") == "fedora", confirmation_policy="explicit", rollback_supported=False,
        recovery_guidance="Reload local metadata in Apps. If a download fails, check the connection and retry explicitly.",
        command_renderer=_render, preflight_checker=_preflight, parameter_validator=_validate, verifier=_verify,
        affected_resources=("application-metadata",), interaction_policy="automatic",
    )
