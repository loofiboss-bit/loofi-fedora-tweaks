"""v17 Assurance action definitions for the five canonical workflows."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from core.actions.contracts import (
    ActionDefinition,
    ActionPlan,
    ActionRun,
    ActionRuntime,
    PolicyDecision,
    VerificationDecision,
)
from core.executor.action_result import ActionResult

_PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._-]{0,127}$")
_FLATPAK_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,255}$")
_DESCRIPTION_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]{1,80}$")
_ALLOWED_RETENTION = {7, 14, 30}
_ALLOWED_BACKENDS = {"timeshift", "snapper"}


def assurance_definitions() -> list[ActionDefinition]:
    """Return the bounded v17 catalog additions."""
    return [
        ActionDefinition(
            id="update-fedora-system",
            capability_id="updates.fedora.apply",
            title="Update Fedora",
            description="Apply the currently planned Fedora package or deployment update.",
            parameter_schema={}, risk_level="medium", privileged=True,
            confirmation_policy="explicit-no-rollback",
            recovery_guidance="Traditional systems retain package history; Atomic systems retain the previous deployment.",
            rollback_supported=False, command_renderer=_render_fedora_update,
            preflight_checker=_preflight_fedora_update, verifier=_verify_fedora_update,
        ),
        ActionDefinition(
            id="update-flatpaks",
            capability_id="updates.flatpak.apply",
            title="Update Flatpaks",
            description="Update the exact Flatpak refs discovered during preflight.",
            parameter_schema={}, risk_level="low", privileged=False,
            confirmation_policy="explicit", recovery_guidance="Review Flatpak history and application data if an update regresses.",
            rollback_supported=False, command_renderer=_render_flatpak_update,
            preflight_checker=_preflight_flatpak_update, verifier=_verify_flatpak_update,
        ),
        ActionDefinition(
            id="update-firmware",
            capability_id="updates.firmware.apply",
            title="Update firmware",
            description="Apply firmware updates reported by fwupd and verify device history.",
            parameter_schema={}, risk_level="high", privileged=True,
            confirmation_policy="explicit-no-rollback", recovery_guidance="Do not power off the device; follow vendor recovery guidance if verification fails.",
            rollback_supported=False, command_renderer=lambda _p, _r: ["fwupdmgr", "update", "-y"],
            preflight_checker=_preflight_firmware_update, verifier=_verify_firmware_update,
        ),
        _application_definition("install-application", installing=True),
        _application_definition("remove-application", installing=False),
        ActionDefinition(
            id="vacuum-journal",
            capability_id="maintenance.journal.vacuum",
            title="Vacuum system journal",
            description="Remove journal data older than an explicitly selected retention window.",
            parameter_schema={"days": {"type": "integer", "required": True}},
            risk_level="medium", privileged=True, confirmation_policy="explicit-no-rollback",
            recovery_guidance="Deleted journal entries cannot be restored.", rollback_supported=False,
            command_renderer=lambda p, _r: ["journalctl", f"--vacuum-time={int(p['days'])}d"],
            preflight_checker=_preflight_journal, verifier=_verify_journal,
            parameter_validator=_validate_journal,
        ),
        ActionDefinition(
            id="autoremove-packages",
            capability_id="maintenance.packages.autoremove",
            title="Remove unneeded packages",
            description="Remove the exact unneeded package set recorded during preflight.",
            parameter_schema={}, risk_level="medium", privileged=True,
            confirmation_policy="explicit-no-rollback", recovery_guidance="Reinstall removed packages explicitly if required.",
            rollback_supported=False, command_renderer=_render_autoremove,
            preflight_checker=_preflight_autoremove, verifier=_verify_autoremove,
        ),
        ActionDefinition(
            id="create-recovery-point",
            capability_id="recovery.snapshot.create",
            title="Create recovery point",
            description="Create and verify one Timeshift or Snapper recovery point.",
            parameter_schema={
                "backend": {"type": "string", "required": True},
                "description": {"type": "string", "required": True},
            },
            risk_level="low", privileged=True, confirmation_policy="explicit",
            recovery_guidance="Recovery-point creation does not restore or delete existing snapshots.",
            rollback_supported=True, command_renderer=_render_recovery_point,
            preflight_checker=_preflight_recovery_point, verifier=_verify_recovery_point,
            parameter_validator=_validate_recovery_point,
        ),
    ]


def _application_definition(action_id: str, *, installing: bool) -> ActionDefinition:
    verb = "Install" if installing else "Remove"
    return ActionDefinition(
        id=action_id,
        capability_id=f"applications.{'install' if installing else 'remove'}",
        title=f"{verb} application",
        description=f"{verb} one validated Fedora package or Flatpak application.",
        parameter_schema={
            "source": {"type": "string", "required": True},
            "package_id": {"type": "string", "required": True},
        },
        risk_level="low" if installing else "medium",
        privileged=False,
        confirmation_policy="explicit" if installing else "explicit-no-rollback",
        recovery_guidance="Remove the application again." if installing else "Reinstall the exact application if removal was unintended.",
        rollback_supported=installing,
        command_renderer=lambda p, r: _render_application(p, r, installing=installing),
        preflight_checker=lambda p, r: _preflight_application(p, r, installing=installing),
        verifier=lambda run, plan, runtime: _verify_application(run, plan, runtime, installing=installing),
        parameter_validator=_validate_application,
        privilege_resolver=lambda p, _r: p.get("source") == "fedora",
    )


def _validate_application(parameters: Mapping[str, Any]) -> PolicyDecision:
    source = parameters.get("source")
    package_id = parameters.get("package_id")
    if source not in {"fedora", "flatpak"}:
        return _blocked("invalid_application_source", "Only Fedora RPM and Flatpak sources are supported.")
    pattern = _FLATPAK_PATTERN if source == "flatpak" else _PACKAGE_PATTERN
    if not isinstance(package_id, str) or not pattern.fullmatch(package_id) or package_id.startswith("-"):
        return _blocked("invalid_package_id", "The application identifier is invalid or option-like.")
    return _allowed("parameters_valid", "Application parameters are valid.")


def _validate_journal(parameters: Mapping[str, Any]) -> PolicyDecision:
    days = parameters.get("days")
    if not isinstance(days, int) or isinstance(days, bool) or days not in _ALLOWED_RETENTION:
        return _blocked("invalid_retention", "Journal retention must be 7, 14, or 30 days.")
    return _allowed("parameters_valid", "Journal retention is valid.")


def _validate_recovery_point(parameters: Mapping[str, Any]) -> PolicyDecision:
    backend = parameters.get("backend")
    description = parameters.get("description")
    if backend not in _ALLOWED_BACKENDS:
        return _blocked("invalid_snapshot_backend", "Only Timeshift and Snapper are executable recovery backends.")
    if not isinstance(description, str) or not _DESCRIPTION_PATTERN.fullmatch(description.strip()):
        return _blocked("invalid_snapshot_description", "Description must contain 1-80 printable characters.")
    return _allowed("parameters_valid", "Recovery-point parameters are valid.")


def _render_fedora_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    if runtime.is_atomic():
        return ["rpm-ostree", "upgrade"]
    manager = runtime.package_manager()
    return [manager if manager in {"dnf", "dnf5"} else "dnf", "upgrade", "--refresh", "-y"]


def _preflight_fedora_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    if runtime.is_atomic():
        status = runtime.execute_read_only(["rpm-ostree", "status", "--json"], action_id="update-fedora-status", timeout=30)
        payload = _json_payload(status)
        deployments = payload.get("deployments", []) if isinstance(payload, dict) else []
        booted = next((item for item in deployments if isinstance(item, dict) and item.get("booted")), {})
        if not status.success or not booted:
            return _blocked("atomic_status_unavailable", "The current Atomic deployment could not be verified.")
        return _allowed("preflight_ok", "Atomic deployment state is ready.", atomic=True, booted_checksum=str(booted.get("checksum", "")))
    if runtime.package_manager_busy():
        return _blocked("package_manager_busy", "Another package operation may be active.")
    manager = runtime.package_manager()
    if manager not in {"dnf", "dnf5"}:
        return _blocked("unsupported_package_manager", f"Unsupported package manager: {manager}")
    query = runtime.execute_read_only(
        [manager, "repoquery", "--upgrades", "--qf", "%{name}|%{evr}|%{arch}"],
        action_id="update-fedora-candidates", timeout=90,
    )
    candidates = _lines(query.stdout)
    if not query.success:
        return _blocked("update_query_failed", "Fedora update candidates could not be resolved.")
    if not candidates:
        return _blocked("no_updates", "No Fedora package updates are currently available.")
    return _allowed("preflight_ok", f"{len(candidates)} Fedora package updates are ready.", atomic=False, manager=manager, candidates=candidates)


def _verify_fedora_update(run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    facts = plan.policy_decision.facts
    if facts.get("atomic"):
        status = runtime.execute_read_only(["rpm-ostree", "status", "--json"], action_id="update-fedora-verify-status", timeout=30)
        deployments = _json_payload(status).get("deployments", []) if status.success else []
        booted = next((item for item in deployments if isinstance(item, dict) and item.get("booted")), {})
        pending = _pending_deployment(deployments)
        expected = str(((run.verification_result or {}).get("data") or {}).get("expected_checksum", "")) or str(pending.get("checksum", ""))
        boot_id = _runtime_boot_id(runtime)
        if expected and boot_id != run.execution_boot_id and str(booted.get("checksum", "")) == expected:
            return VerificationDecision.succeeded("The staged Atomic deployment is now booted.", booted_checksum=expected)
        if expected:
            return VerificationDecision.awaiting_reboot("The Atomic update is staged and requires reboot verification.", expected_checksum=expected)
        return VerificationDecision.failed("No verifiable staged Atomic deployment was found.")
    candidates = [str(item) for item in facts.get("candidates", [])]
    missing = []
    for candidate in candidates:
        name = candidate.split("|", 1)[0]
        result = runtime.execute_read_only(
            ["rpm", "-q", "--qf", "%{name}|%{evr}|%{arch}\\n", name],
            action_id="update-fedora-verify-package",
            timeout=15,
        )
        if not result.success or candidate not in _lines(result.stdout):
            missing.append(candidate)
    manager = str(facts.get("manager", runtime.package_manager()))
    health = runtime.execute_read_only([manager, "check"], action_id="update-fedora-verify-health", timeout=120)
    if missing or not health.success:
        return VerificationDecision.failed("Fedora package verification failed.", missing_packages=sorted(set(missing)))
    return VerificationDecision.succeeded("Planned Fedora packages and package health were verified.", verified_packages=len(candidates))


def _preflight_flatpak_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    result, refs = _query_flatpak_updates(runtime)
    if not result.success:
        return _blocked("flatpak_query_failed", "Flatpak updates could not be queried.")
    if not refs:
        return _blocked("no_flatpak_updates", "No Flatpak updates are currently available.")
    return _allowed("preflight_ok", f"{len(refs)} Flatpak refs are ready.", refs=refs)


def _render_flatpak_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    result, refs = _query_flatpak_updates(runtime)
    if not result.success or not refs:
        raise ValueError("Flatpak update candidates are unavailable.")
    return ["flatpak", "update", "--noninteractive", "--assumeyes", *[item["id"] for item in refs]]


def _query_flatpak_updates(runtime: ActionRuntime) -> tuple[ActionResult, list[dict[str, str]]]:
    result = runtime.execute_read_only(
        ["flatpak", "remote-ls", "--updates", "--columns=ref,commit"],
        action_id="update-flatpaks-candidates",
        timeout=90,
    )
    return result, _tab_records(result.stdout)


def _verify_flatpak_update(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    failed = []
    for record in plan.policy_decision.facts.get("refs", []):
        if not isinstance(record, dict):
            continue
        ref, expected = str(record.get("id", "")), str(record.get("value", ""))
        result = runtime.execute_read_only(["flatpak", "info", "--show-commit", ref], action_id="update-flatpaks-verify-ref", timeout=30)
        if not result.success or (expected and result.stdout.strip() != expected):
            failed.append(ref)
    if failed:
        return VerificationDecision.failed("One or more planned Flatpak refs could not be verified.", failed_refs=failed)
    return VerificationDecision.succeeded("All planned Flatpak refs were verified.")


def _preflight_firmware_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    result = runtime.execute_read_only(["fwupdmgr", "get-updates", "--json"], action_id="update-firmware-candidates", timeout=90)
    devices = _firmware_records(_json_payload(result))
    if not result.success:
        return _blocked("firmware_query_failed", "Firmware updates could not be queried.")
    if not devices:
        return _blocked("no_firmware_updates", "No firmware updates are currently available.")
    return _allowed("preflight_ok", f"{len(devices)} firmware updates are ready.", devices=devices)


def _verify_firmware_update(run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    result = runtime.execute_read_only(["fwupdmgr", "get-history", "--json"], action_id="update-firmware-verify-history", timeout=60)
    if not result.success:
        return VerificationDecision.failed("Firmware history could not be queried.")
    history_text = json.dumps(_json_payload(result), sort_keys=True)
    missing = []
    for item in plan.policy_decision.facts.get("devices", []):
        if not isinstance(item, Mapping):
            continue
        identity = [str(item.get("guid", "")), str(item.get("version", ""))]
        checksum = str(item.get("checksum", ""))
        if not all(value and value in history_text for value in identity) or (checksum and checksum not in history_text):
            missing.append(dict(item))
    if not missing:
        return VerificationDecision.succeeded("Firmware history contains every planned update.")
    if _runtime_boot_id(runtime) == run.execution_boot_id:
        return VerificationDecision.awaiting_reboot("Firmware application is awaiting reboot verification.", pending_devices=missing)
    return VerificationDecision.failed("The expected firmware result was not recorded after reboot.", missing_devices=missing)


def _render_application(parameters: Mapping[str, Any], runtime: ActionRuntime, *, installing: bool) -> list[str]:
    package_id = str(parameters["package_id"])
    if parameters["source"] == "flatpak":
        action = "install" if installing else "uninstall"
        vector = ["flatpak", action, "--noninteractive", "--assumeyes"]
        if installing:
            vector.append("flathub")
        return [*vector, package_id]
    if runtime.is_atomic():
        return ["rpm-ostree", "install" if installing else "uninstall", package_id]
    manager = runtime.package_manager()
    return [manager if manager in {"dnf", "dnf5"} else "dnf", "install" if installing else "remove", "-y", package_id]


def _preflight_application(parameters: Mapping[str, Any], runtime: ActionRuntime, *, installing: bool) -> PolicyDecision:
    package_id, source = str(parameters["package_id"]), str(parameters["source"])
    if source == "flatpak":
        installed = runtime.execute_read_only(["flatpak", "info", package_id], action_id="application-installed", timeout=20).success
        target_commit = ""
        if installing:
            available = runtime.execute_read_only(
                ["flatpak", "remote-info", "--show-commit", "flathub", package_id],
                action_id="application-available",
                timeout=30,
            )
            if not available.success:
                return _blocked("application_unavailable", "The Flatpak application is unavailable from Flathub.")
            target_commit = available.stdout.strip()
        if installed == installing:
            return _blocked("application_state_unchanged", "The application already has the requested state.")
        return _allowed(
            "preflight_ok",
            "Flatpak application state is ready to change.",
            source=source,
            package_id=package_id,
            installed_before=installed,
            target_commit=target_commit,
        )
    if runtime.package_manager_busy():
        return _blocked("package_manager_busy", "Another package operation may be active.")
    installed_result = runtime.execute_read_only(
        ["rpm", "-q", "--qf", "%{name}|%{evr}|%{arch}\\n", package_id],
        action_id="application-installed",
        timeout=15,
    )
    installed = installed_result.success
    if installing:
        manager = runtime.package_manager()
        available = runtime.execute_read_only(
            [manager, "repoquery", "--available", "--latest-limit", "1", "--qf", "%{name}|%{evr}|%{arch}", package_id],
            action_id="application-available",
            timeout=60,
        )
        if not available.success or not available.stdout.strip():
            return _blocked("application_unavailable", "The Fedora package is unavailable from enabled repositories.")
    if installed == installing:
        return _blocked("application_state_unchanged", "The application already has the requested state.")
    return _allowed(
        "preflight_ok",
        "Fedora application state is ready to change.",
        source=source,
        package_id=package_id,
        installed_before=installed,
        atomic=runtime.is_atomic(),
        target_nevra=available.stdout.strip() if installing else "",
        installed_nevra=installed_result.stdout.strip() if installed else "",
    )


def _verify_application(run: ActionRun, plan: ActionPlan, runtime: ActionRuntime, *, installing: bool) -> VerificationDecision:
    package_id = str(plan.parameters["package_id"])
    if plan.parameters["source"] == "flatpak":
        result = runtime.execute_read_only(
            ["flatpak", "info", "--show-commit", package_id],
            action_id="application-verify",
            timeout=20,
        )
        expected = str(plan.policy_decision.facts.get("target_commit", ""))
        verified = result.success == installing and (not installing or not expected or result.stdout.strip() == expected)
        return VerificationDecision.succeeded("Flatpak application state was verified.") if verified else VerificationDecision.failed("Flatpak application state did not match the plan.")
    if runtime.is_atomic():
        status = runtime.execute_read_only(["rpm-ostree", "status", "--json"], action_id="application-verify-atomic", timeout=30)
        deployments = _json_payload(status).get("deployments", []) if status.success else []
        candidate = _pending_deployment(deployments)
        booted = next((item for item in deployments if isinstance(item, dict) and item.get("booted")), {})
        expected_checksum = str((((run.verification_result or {}).get("data") or {}).get("expected_checksum", "")))
        if _runtime_boot_id(runtime) == run.execution_boot_id:
            if not candidate or not candidate.get("checksum"):
                return VerificationDecision.failed("No staged Atomic deployment was found.")
            requested = set(str(item) for item in candidate.get("requested-packages", []))
            if (package_id in requested) != installing:
                return VerificationDecision.failed("The staged Atomic package request did not match the plan.")
            return VerificationDecision.awaiting_reboot(
                "The Atomic application change is staged.",
                package_id=package_id,
                expected_checksum=str(candidate.get("checksum", "")),
            )
        if expected_checksum and str(booted.get("checksum", "")) != expected_checksum:
            return VerificationDecision.awaiting_reboot("The expected Atomic deployment is not booted.", expected_checksum=expected_checksum)
    result = runtime.execute_read_only(
        ["rpm", "-q", "--qf", "%{name}|%{evr}|%{arch}\\n", package_id],
        action_id="application-verify-rpm",
        timeout=15,
    )
    expected_nevra = str(plan.policy_decision.facts.get("target_nevra", ""))
    verified = result.success == installing and (not installing or not expected_nevra or expected_nevra in _lines(result.stdout))
    return VerificationDecision.succeeded("Fedora application state was verified.") if verified else VerificationDecision.failed("Fedora application state did not match the plan.")


def _preflight_journal(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    result = runtime.execute_read_only(["journalctl", "--disk-usage", "--no-pager"], action_id="journal-usage-before", timeout=15)
    if not result.success:
        return _blocked("journal_usage_unavailable", "Journal usage could not be measured.")
    return _allowed("preflight_ok", "Journal usage was measured.", usage_bytes=_human_bytes(result.stdout))


def _verify_journal(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    result = runtime.execute_read_only(["journalctl", "--disk-usage", "--no-pager"], action_id="journal-usage-after", timeout=15)
    before, after = int(plan.policy_decision.facts.get("usage_bytes", 0)), _human_bytes(result.stdout)
    if not result.success or (before > 0 and after > before):
        return VerificationDecision.failed("Journal retention could not be verified.", before_bytes=before, after_bytes=after)
    return VerificationDecision.succeeded("Journal retention and usage were verified.", before_bytes=before, after_bytes=after)


def _preflight_autoremove(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    if runtime.is_atomic():
        return _blocked("atomic_manual_only", "Package autoremove remains manual-only on Atomic Fedora.")
    if runtime.package_manager_busy():
        return _blocked("package_manager_busy", "Another package operation may be active.")
    manager = runtime.package_manager()
    result = runtime.execute_read_only([manager, "repoquery", "--unneeded", "--installed", "--qf", "%{name}"], action_id="autoremove-candidates", timeout=60)
    packages = [item for item in _lines(result.stdout) if _PACKAGE_PATTERN.fullmatch(item)]
    if not result.success:
        return _blocked("autoremove_query_failed", "Unneeded packages could not be resolved.")
    if not packages:
        return _blocked("nothing_to_remove", "No unneeded packages are currently installed.")
    return _allowed("preflight_ok", f"{len(packages)} exact packages are ready for removal.", manager=manager, packages=packages)


def _render_autoremove(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    manager = runtime.package_manager()
    result = _preflight_autoremove({}, runtime)
    packages = [str(item) for item in result.facts.get("packages", [])]
    return [manager, "remove", "-y", *packages]


def _verify_autoremove(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    remaining = []
    for package in plan.policy_decision.facts.get("packages", []):
        if runtime.execute_read_only(["rpm", "-q", str(package)], action_id="autoremove-verify-package", timeout=15).success:
            remaining.append(str(package))
    manager = str(plan.policy_decision.facts.get("manager", runtime.package_manager()))
    health = runtime.execute_read_only([manager, "check"], action_id="autoremove-verify-health", timeout=120)
    if remaining or not health.success:
        return VerificationDecision.failed("Package removal verification failed.", remaining_packages=remaining)
    return VerificationDecision.succeeded("Every planned package removal was verified.")


def _render_recovery_point(parameters: Mapping[str, Any], _runtime: ActionRuntime) -> list[str]:
    backend, description = str(parameters["backend"]), str(parameters["description"]).strip()
    if backend == "timeshift":
        return ["timeshift", "--create", "--comments", description]
    return ["snapper", "create", "--description", description, "--type", "single"]


def _preflight_recovery_point(parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    backend = str(parameters["backend"])
    vector = [backend, "--list"] if backend == "timeshift" else [backend, "list"]
    result = runtime.execute_read_only(vector, action_id="recovery-point-before", timeout=30)
    if not result.success:
        return _blocked("snapshot_backend_unavailable", f"{backend} could not list recovery points.")
    return _allowed("preflight_ok", f"{backend} is ready.", backend=backend, before_lines=_lines(result.stdout))


def _verify_recovery_point(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    backend, description = str(plan.parameters["backend"]), str(plan.parameters["description"]).strip()
    vector = [backend, "--list"] if backend == "timeshift" else [backend, "list"]
    result = runtime.execute_read_only(vector, action_id="recovery-point-after", timeout=30)
    before, after = set(plan.policy_decision.facts.get("before_lines", [])), set(_lines(result.stdout))
    added = after - before
    if result.success and any(description in line for line in added):
        return VerificationDecision.succeeded("The recovery point was created and listed.", backend=backend, added=sorted(added))
    return VerificationDecision.failed("The new recovery point could not be identified after creation.")


def _allowed(code: str, explanation: str, **facts: Any) -> PolicyDecision:
    return PolicyDecision(True, code, explanation, facts=facts)


def _blocked(code: str, explanation: str) -> PolicyDecision:
    return PolicyDecision(False, code, explanation, "Review the current state and create a fresh plan.")


def _json_payload(result: ActionResult) -> dict[str, Any]:
    if not result.success:
        return {}
    try:
        payload = json.loads(result.stdout or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {"items": payload}


def _lines(value: str) -> list[str]:
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _tab_records(value: str) -> list[dict[str, str]]:
    records = []
    for line in _lines(value):
        parts = line.split("\t", 1)
        records.append({"id": parts[0], "value": parts[1] if len(parts) > 1 else ""})
    return records


def _firmware_records(payload: Any) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            guid = value.get("Guid") or value.get("DeviceId") or value.get("device_id")
            version = value.get("Version") or value.get("version")
            if guid and version:
                records.append({"guid": str(guid), "version": str(version), "checksum": str(value.get("Checksum") or value.get("checksum") or "")})
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    unique = {(item["guid"], item["version"]): item for item in records}
    return list(unique.values())


def _human_bytes(value: str) -> int:
    match = re.search(r"(\d+(?:\.\d+)?)\s*([KMGT]?)(?:i?B|bytes?)", str(value), re.IGNORECASE)
    if not match:
        return 0
    factor = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[match.group(2).upper()]
    return int(float(match.group(1)) * factor)


def _runtime_boot_id(runtime: ActionRuntime) -> str:
    reader = getattr(runtime, "boot_id", None)
    return str(reader() if callable(reader) else "").strip()


def _pending_deployment(deployments: Any) -> dict[str, Any]:
    if not isinstance(deployments, list):
        return {}
    for marker in ("staged", "pending"):
        candidate = next(
            (item for item in deployments if isinstance(item, dict) and item.get(marker) and not item.get("booted")),
            None,
        )
        if candidate is not None:
            return candidate
    return {}
