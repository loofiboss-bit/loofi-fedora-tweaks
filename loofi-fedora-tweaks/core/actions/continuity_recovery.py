"""Conservative Fedora recovery workflows introduced by Continuity."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from core.actions.contracts import (
    ActionPlan,
    ActionRun,
    ActionRuntime,
    PolicyDecision,
    VerificationDecision,
)
from core.executor.action_result import ActionResult

_OSTREE_CHECKSUM_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _validate_transaction_id(parameters: Mapping[str, Any]) -> PolicyDecision:
    transaction_id = parameters.get("transaction_id")
    if (
        not isinstance(transaction_id, int)
        or isinstance(transaction_id, bool)
        or transaction_id <= 0
        or transaction_id > 2_147_483_647
    ):
        return _blocked(
            "invalid_transaction_id",
            "Transaction ID must be a positive bounded integer.",
        )
    return _allowed("parameters_valid", "Transaction ID is valid.")


def _validate_rpm_ostree_rollback(parameters: Mapping[str, Any]) -> PolicyDecision:
    expected = parameters.get("expected_deployment")
    rollback = parameters.get("rollback_deployment")
    if not isinstance(expected, str) or not _OSTREE_CHECKSUM_PATTERN.fullmatch(expected):
        return _blocked(
            "invalid_expected_deployment",
            "Expected deployment must be an exact rpm-ostree checksum.",
        )
    if not isinstance(rollback, str) or not _OSTREE_CHECKSUM_PATTERN.fullmatch(rollback):
        return _blocked(
            "invalid_rollback_deployment",
            "Rollback deployment must be an exact rpm-ostree checksum.",
        )
    if expected == rollback:
        return _blocked(
            "identical_deployments",
            "Current and rollback deployments must be different.",
        )
    return _allowed("parameters_valid", "Deployment checksums are valid.")


def _render_fedora_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    if runtime.is_atomic():
        manager = runtime.package_manager()
        if manager == "rpm-ostree":
            return ["rpm-ostree", "upgrade"]
        if manager == "bootc":
            return ["bootc", "upgrade"]
    # ``dnf`` is accepted only as a compatibility spelling for injected
    # legacy runtimes.  The real PlatformProfile always reports ``dnf5`` and
    # the command vector remains explicitly DNF5.
    if runtime.package_manager() in {"dnf", "dnf5"}:
        return ["dnf5", "upgrade", "--refresh", "-y", "--offline"]
    return []


def _preflight_fedora_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    manager = runtime.package_manager()
    if manager == "unknown":
        return _blocked(
            "platform_unknown",
            "The Fedora deployment backend could not be verified.",
        )
    if runtime.is_atomic():
        if manager == "bootc":
            return _blocked(
                "bootc_manual_only",
                "bootc image updates require a reviewed host workflow and are manual-only here.",
            )
        status = runtime.execute_read_only(["rpm-ostree", "status", "--json"], action_id="update-fedora-status", timeout=30)
        payload = _json_payload(status)
        raw_deployments = payload.get("deployments") if isinstance(payload, dict) else None
        deployments = raw_deployments if isinstance(raw_deployments, list) else []
        booted = next((item for item in deployments if isinstance(item, dict) and item.get("booted")), {})
        if (status.data or {}).get("evidence_unavailable") or status.success and not isinstance(raw_deployments, list):
            return _blocked("atomic_evidence_unavailable", "Atomic deployment JSON evidence is unavailable; refresh system status.")
        if not status.success or not booted:
            return _blocked("atomic_status_unavailable", "The current Atomic deployment could not be verified.")
        return _allowed("preflight_ok", "Atomic deployment state is ready.", atomic=True, booted_checksum=str(booted.get("checksum", "")))
    if manager not in {"dnf", "dnf5"}:
        return _blocked(
            "unsupported_package_manager",
            f"The detected package backend ({manager}) is not supported by this workflow.",
        )
    if runtime.package_manager_busy():
        return _blocked("package_manager_busy", "Another package operation may be active.")
    query = runtime.execute_read_only(
        ["dnf5", "repoquery", "--upgrades", "--qf", "%{name}|%{evr}|%{arch}"],
        action_id="update-fedora-candidates", timeout=90,
    )
    candidates = _lines(query.stdout)
    if not query.success:
        return _blocked(
            "dnf5_required",
            "DNF5 update candidates could not be resolved for an offline transaction.",
        )
    if not candidates:
        return _blocked("no_updates", "No Fedora package updates are currently available.")
    return _allowed(
        "preflight_ok",
        f"{len(candidates)} Fedora package updates are ready for offline staging.",
        atomic=False,
        manager="dnf5",
        candidates=candidates,
        offline=True,
    )


def _verify_fedora_update(run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    facts = plan.policy_decision.facts
    if facts.get("atomic"):
        status = runtime.execute_read_only(["rpm-ostree", "status", "--json"], action_id="update-fedora-verify-status", timeout=30)
        payload = _json_payload(status) if status.success else None
        if payload is None or not isinstance(payload.get("deployments"), list):
            return VerificationDecision.failed("Atomic deployment JSON evidence is unavailable or invalid.")
        deployments = payload["deployments"]
        booted = next((item for item in deployments if isinstance(item, dict) and item.get("booted")), {})
        pending = _pending_deployment(deployments)
        expected = str(((run.verification_result or {}).get("data") or {}).get("expected_checksum", "")) or str(pending.get("checksum", ""))
        boot_id = _runtime_boot_id(runtime)
        if expected and boot_id != run.execution_boot_id and str(booted.get("checksum", "")) == expected:
            return VerificationDecision.succeeded("The staged Atomic deployment is now booted.", booted_checksum=expected)
        if expected:
            return VerificationDecision.awaiting_reboot("The Atomic update is staged and requires reboot verification.", expected_checksum=expected)
        return VerificationDecision.failed("No verifiable staged Atomic deployment was found.")
    if _runtime_boot_id(runtime) == run.execution_boot_id:
        status = runtime.execute_read_only(
            ["dnf5", "offline", "status"],
            action_id="update-fedora-verify-offline-status",
            timeout=30,
        )
        if not status.success:
            return VerificationDecision.failed(
                "DNF5 did not report a prepared offline transaction."
            )
        return VerificationDecision.awaiting_reboot(
            "The Fedora update is prepared and requires a separate reboot.",
            offline_transaction=True,
        )

    candidates = [str(item) for item in facts.get("candidates", [])]
    history = _matching_fedora_history(run, candidates, runtime)
    if history is None:
        return VerificationDecision.failed(
            "DNF5 transaction history could not verify the planned update after reboot.",
            evidence_unavailable=True,
        )
    if not history:
        return VerificationDecision.failed(
            "No successful DNF5 history transaction contains the planned update after reboot.",
            evidence_unavailable=False,
        )
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
    health = runtime.execute_read_only(
        ["dnf5", "check"],
        action_id="update-fedora-verify-health",
        timeout=120,
    )
    if missing or not health.success:
        return VerificationDecision.failed("Fedora package verification failed.", missing_packages=sorted(set(missing)))
    return VerificationDecision.succeeded(
        "A successful DNF5 history transaction contains the planned packages and package health is clean.",
        transaction_id=history,
        verified_packages=len(candidates),
    )


def _render_fedora_offline_reboot(
    _parameters: Mapping[str, Any],
    _runtime: ActionRuntime,
) -> list[str]:
    return ["dnf5", "offline", "reboot"]


def _validate_fedora_offline_activation(parameters: Mapping[str, Any]) -> PolicyDecision:
    source_run_id = parameters.get("source_run_id")
    if not isinstance(source_run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", source_run_id):
        return _blocked("invalid_source_run", "A valid prepared update run must be selected.")
    return _allowed("parameters_valid", "A specific prepared update run is selected.")


def _preflight_fedora_offline_activation(
    parameters: Mapping[str, Any],
    runtime: ActionRuntime,
) -> PolicyDecision:
    if runtime.is_atomic() or runtime.package_manager() not in {"dnf", "dnf5"}:
        return _blocked("traditional_dnf5_required", "Offline activation is supported only for traditional Fedora with DNF5.")
    if runtime.package_manager_busy():
        return _blocked("package_manager_busy", "Another package operation may be active.")
    try:
        from core.actions.stores import ActionPlanStore, ActionRunStore

        source_run_id = str(parameters["source_run_id"])
        source_run = next(
            (run for run in ActionRunStore().list_read_only(limit=100, strict=True) if run.run_id == source_run_id),
            None,
        )
        if source_run is None or source_run.action_id != "update-fedora-system" or source_run.state != "awaiting_reboot":
            return _blocked("prepared_update_missing", "The selected Fedora update is no longer awaiting offline activation.")
        current_boot_id = _runtime_boot_id(runtime)
        if not source_run.execution_boot_id or not current_boot_id or source_run.execution_boot_id != current_boot_id:
            return _blocked("activation_already_pending", "The computer has rebooted since preparation; check the original update result in Activity.")
        source_plan = next(
            (plan for plan in ActionPlanStore().list_read_only() if plan.plan_id == source_run.plan_id),
            None,
        )
        if source_plan is None:
            return _blocked("prepared_update_plan_missing", "The reviewed update plan is unavailable; preserve its recorded state.")
        facts = source_plan.policy_decision.facts
        verification = source_run.verification_result or {}
        verification_data = verification.get("data", {}) if isinstance(verification, Mapping) else {}
        if facts.get("atomic") or facts.get("offline") is not True or not isinstance(verification_data, Mapping) or verification_data.get("offline_transaction") is not True:
            return _blocked("not_a_prepared_dnf5_update", "The selected result does not contain verified DNF5 offline update evidence.")
    except (OSError, RuntimeError, TypeError, ValueError):
        return _blocked("update_state_unavailable", "The selected update state could not be read safely.")
    status = runtime.execute_read_only(
        ["dnf5", "offline", "status"],
        action_id="update-fedora-activate-offline-status",
        timeout=30,
    )
    if not status.success or not status.stdout.strip():
        return _blocked("offline_transaction_unavailable", "DNF5 no longer reports a prepared offline transaction.")
    return _allowed(
        "preflight_ok",
        "A verified pending DNF5 update is ready for the separately confirmed reboot.",
        source_run_id=source_run_id,
        activation_command=["dnf5", "offline", "reboot"],
    )


def _verify_fedora_offline_activation(
    run: ActionRun,
    plan: ActionPlan,
    runtime: ActionRuntime,
) -> VerificationDecision:
    if _runtime_boot_id(runtime) == run.execution_boot_id:
        return VerificationDecision.awaiting_reboot(
            "DNF5 accepted the separate reboot request. The original Fedora update remains pending until its transaction history is checked after restart.",
            source_run_id=str(plan.parameters["source_run_id"]),
        )
    try:
        from core.actions.stores import ActionPlanStore, ActionRunStore

        source_run_id = str(plan.parameters["source_run_id"])
        source_run = next(
            (candidate for candidate in ActionRunStore().list_read_only(limit=100, strict=True) if candidate.run_id == source_run_id),
            None,
        )
        source_plan = next(
            (candidate for candidate in ActionPlanStore().list_read_only() if source_run and candidate.plan_id == source_run.plan_id),
            None,
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        return VerificationDecision.failed("The original update run could not be read for post-reboot verification.")
    if source_run is None or source_plan is None:
        return VerificationDecision.failed("The original update plan is unavailable for post-reboot verification.")
    result = _verify_fedora_update(source_run, source_plan, runtime)
    if result.state == "succeeded":
        return VerificationDecision.succeeded(
            "DNF5 transaction history verifies the prepared update after reboot.",
            source_run_id=source_run_id,
            **dict(result.data),
        )
    return result


def _matching_fedora_history(
    run: ActionRun,
    candidates: list[str],
    runtime: ActionRuntime,
) -> int | None:
    """Return the transaction that applied every planned package, or None if unavailable."""
    result = runtime.execute_read_only(
        ["dnf5", "history", "list", "--json"],
        action_id="update-fedora-verify-history-list",
        timeout=60,
    )
    payload = _json_payload(result)
    if not result.success or payload is None or not isinstance(payload.get("items"), list):
        return None
    transactions = [
        item for item in payload["items"]
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), int)
        and not isinstance(item.get("id"), bool)
        and item.get("id", 0) > 0
        and _history_time(item.get("start_time")) >= run.started_at
        and str(item.get("status", "")).casefold() in {"ok", "success", "succeeded"}
    ]
    for transaction in sorted(transactions, key=lambda item: _history_time(item.get("start_time")), reverse=True)[:20]:
        info = runtime.execute_read_only(
            ["dnf5", "history", "info", str(transaction["id"]), "--json"],
            action_id="update-fedora-verify-history-info",
            timeout=60,
        )
        details = _json_payload(info)
        if not info.success or details is None or not isinstance(details.get("items"), list):
            continue
        record = next(
            (
                item for item in details["items"]
                if isinstance(item, Mapping) and item.get("id") == transaction["id"]
            ),
            None,
        )
        if not isinstance(record, Mapping) or str(record.get("status", "")).casefold() not in {"ok", "success", "succeeded"}:
            continue
        packages = record.get("packages")
        if not isinstance(packages, list):
            continue
        if all(_planned_package_in_transaction(candidate, packages) for candidate in candidates):
            return int(transaction["id"])
    return 0


def _planned_package_in_transaction(candidate: str, packages: list[Any]) -> bool:
    parts = candidate.split("|")
    if len(parts) != 3:
        return False
    name, evr, arch = parts
    expected = {f"{name}-{evr}.{arch}"}
    if ":" not in evr:
        expected.add(f"{name}-0:{evr}.{arch}")
    return any(
        isinstance(package, Mapping)
        and str(package.get("action", "")).casefold().startswith(("upgrade", "install", "reinstall"))
        and str(package.get("nevra", "")) in expected
        for package in packages
    )


def _history_time(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return result if result >= 0 else 0.0


def _render_dnf5_history_undo(
    parameters: Mapping[str, Any],
    _runtime: ActionRuntime,
) -> list[str]:
    return [
        "dnf5",
        "history",
        "undo",
        str(int(parameters["transaction_id"])),
        "--offline",
    ]


def _dnf5_transaction(
    parameters: Mapping[str, Any],
    runtime: ActionRuntime,
) -> tuple[ActionResult, Mapping[str, Any]]:
    transaction_id = int(parameters.get("transaction_id", 0))
    result = runtime.execute_read_only(
        ["dnf5", "history", "info", str(transaction_id), "--json"],
        action_id="dnf5-history-undo-preflight",
        timeout=60,
    )
    payload = _json_payload(result)
    records = payload.get("items", []) if isinstance(payload, Mapping) else []
    record = next(
        (
            item
            for item in records
            if isinstance(item, Mapping) and int(item.get("id", 0)) == transaction_id
        ),
        {},
    )
    return result, record


def _preflight_dnf5_history_undo(
    parameters: Mapping[str, Any],
    runtime: ActionRuntime,
) -> PolicyDecision:
    if runtime.package_manager() not in {"dnf", "dnf5"}:
        return _blocked(
            "unsupported_package_manager",
            "DNF5 transaction recovery requires a verified DNF5 backend.",
        )
    if runtime.is_atomic():
        return _blocked(
            "traditional_only",
            "DNF5 transaction recovery is unavailable on Atomic Fedora.",
        )
    if runtime.package_manager_busy():
        return _blocked("package_manager_busy", "Another package operation may be active.")
    result, record = _dnf5_transaction(parameters, runtime)
    if not result.success or not record:
        return _blocked(
            "transaction_unavailable",
            "The exact DNF5 transaction could not be read.",
        )
    if str(record.get("status", "")).lower() not in {"ok", "success", "succeeded"}:
        return _blocked(
            "transaction_not_successful",
            "Only a successfully completed DNF5 transaction can be recovered.",
        )
    packages = record.get("packages", [])
    if not isinstance(packages, list) or not packages:
        return _blocked(
            "transaction_has_no_packages",
            "The DNF5 transaction has no verifiable package changes.",
        )
    normalized: list[dict[str, str]] = []
    for package in packages:
        if not isinstance(package, Mapping):
            return _blocked(
                "invalid_transaction_packages",
                "The DNF5 package history is incomplete.",
            )
        action = str(package.get("action", "")).lower()
        nevra = str(package.get("nevra", ""))
        if action not in {"install", "remove"} or not nevra:
            return _blocked(
                "unsupported_transaction_shape",
                "Recovery supports only install/remove transactions that can be verified exactly.",
            )
        normalized.append({"action": action, "nevra": nevra})
    return _allowed(
        "preflight_ok",
        f"DNF5 transaction {parameters['transaction_id']} can be prepared for offline recovery.",
        transaction_id=int(parameters["transaction_id"]),
        packages=normalized,
        offline=True,
    )


def _verify_dnf5_history_undo(
    run: ActionRun,
    plan: ActionPlan,
    runtime: ActionRuntime,
) -> VerificationDecision:
    if _runtime_boot_id(runtime) == run.execution_boot_id:
        status = runtime.execute_read_only(
            ["dnf5", "offline", "status"],
            action_id="dnf5-history-undo-verify-offline-status",
            timeout=30,
        )
        if not status.success:
            return VerificationDecision.failed(
                "DNF5 did not report a prepared offline recovery transaction."
            )
        return VerificationDecision.awaiting_reboot(
            "The DNF5 recovery is prepared and requires a separate reboot.",
            transaction_id=plan.parameters["transaction_id"],
        )

    failures: list[str] = []
    packages = plan.policy_decision.facts.get("packages", [])
    for package in packages if isinstance(packages, list) else []:
        if not isinstance(package, Mapping):
            failures.append("invalid-package-fact")
            continue
        action = str(package.get("action", ""))
        nevra = str(package.get("nevra", ""))
        name = _name_from_nevra(nevra)
        query = runtime.execute_read_only(
            ["rpm", "-q", "--qf", "%{nevra}\\n", name],
            action_id="dnf5-history-undo-verify-package",
            timeout=15,
        )
        if action == "install" and query.success:
            failures.append(nevra)
        elif action == "remove" and (
            not query.success or nevra not in _lines(query.stdout)
        ):
            failures.append(nevra)
    health = runtime.execute_read_only(
        ["dnf5", "check"],
        action_id="dnf5-history-undo-verify-health",
        timeout=120,
    )
    offline_log = runtime.execute_read_only(
        ["dnf5", "offline", "log", "--number=-1"],
        action_id="dnf5-history-undo-verify-log",
        timeout=60,
    )
    if failures or not health.success or not offline_log.success:
        return VerificationDecision.failed(
            "DNF5 recovery verification failed.",
            failed_packages=sorted(set(failures)),
        )
    return VerificationDecision.succeeded(
        "The exact DNF5 transaction inverse and package health were verified.",
        verified_packages=len(packages),
    )


def _name_from_nevra(nevra: str) -> str:
    base = nevra.rsplit(".", 1)[0]
    match = re.match(r"^(.+)-[^-]+-[^-]+$", base)
    return match.group(1) if match else nevra


def _rpm_ostree_deployments(
    runtime: ActionRuntime,
    *,
    action_id: str,
) -> tuple[ActionResult, list[Mapping[str, Any]]]:
    result = runtime.execute_read_only(
        ["rpm-ostree", "status", "--json"],
        action_id=action_id,
        timeout=30,
    )
    if not result.success:
        return result, []
    payload = _json_payload(result)
    raw = payload.get("deployments") if isinstance(payload, Mapping) else None
    if not isinstance(raw, list):
        return ActionResult(
            False,
            "Atomic deployment JSON evidence is unavailable or invalid.",
            exit_code=result.exit_code,
            action_id=action_id,
            data={"evidence_unavailable": "invalid_json"},
        ), []
    deployments = [item for item in raw if isinstance(item, Mapping)]
    return result, deployments


def _preflight_rpm_ostree_rollback(
    parameters: Mapping[str, Any],
    runtime: ActionRuntime,
) -> PolicyDecision:
    if not runtime.is_atomic():
        return _blocked(
            "atomic_only",
            "rpm-ostree rollback is available only on Atomic Fedora.",
        )
    result, deployments = _rpm_ostree_deployments(
        runtime,
        action_id="rpm-ostree-rollback-preflight",
    )
    if not result.success:
        if (result.data or {}).get("evidence_unavailable"):
            return _blocked("atomic_evidence_unavailable", "Atomic deployment JSON evidence is unavailable; review the current system status.")
        return _blocked(
            "atomic_status_unavailable",
            "The current Atomic deployment could not be verified.",
        )
    expected = str(parameters["expected_deployment"])
    rollback = str(parameters["rollback_deployment"])
    booted = next(
        (item for item in deployments if bool(item.get("booted", False))),
        {},
    )
    previous = next(
        (
            item
            for item in deployments
            if str(item.get("checksum", "")) == rollback
            and not bool(item.get("booted", False))
        ),
        {},
    )
    if str(booted.get("checksum", "")) != expected:
        return _blocked(
            "current_deployment_changed",
            "The booted deployment no longer matches the journal event.",
        )
    if not previous:
        return _blocked(
            "rollback_deployment_unavailable",
            "The exact previous deployment is no longer available.",
        )
    return _allowed(
        "preflight_ok",
        "The exact current and rollback deployments were freshly verified.",
        expected_deployment=expected,
        rollback_deployment=rollback,
    )


def _verify_rpm_ostree_rollback(
    run: ActionRun,
    plan: ActionPlan,
    runtime: ActionRuntime,
) -> VerificationDecision:
    result, deployments = _rpm_ostree_deployments(
        runtime,
        action_id="rpm-ostree-rollback-verify",
    )
    if not result.success:
        if (result.data or {}).get("evidence_unavailable"):
            return VerificationDecision.failed("Atomic deployment JSON evidence is unavailable or invalid.", evidence_unavailable=True)
        return VerificationDecision.failed(
            "Atomic deployment status could not be verified."
        )
    rollback = str(plan.parameters["rollback_deployment"])
    booted = next(
        (item for item in deployments if bool(item.get("booted", False))),
        {},
    )
    if (
        _runtime_boot_id(runtime) != run.execution_boot_id
        and str(booted.get("checksum", "")) == rollback
    ):
        return VerificationDecision.succeeded(
            "The exact rollback deployment is now booted.",
            booted_checksum=rollback,
        )
    pending = next(
        (
            item
            for item in deployments
            if str(item.get("checksum", "")) == rollback
            and not bool(item.get("booted", False))
        ),
        {},
    )
    if pending:
        return VerificationDecision.awaiting_reboot(
            "The exact rollback deployment is staged and requires reboot.",
            expected_checksum=rollback,
        )
    return VerificationDecision.failed(
        "The expected rollback deployment is no longer staged or booted."
    )


def _allowed(code: str, explanation: str, **facts: Any) -> PolicyDecision:
    return PolicyDecision(True, code, explanation, facts=facts)


def _blocked(code: str, explanation: str) -> PolicyDecision:
    return PolicyDecision(
        False,
        code,
        explanation,
        "Review the current state and create a fresh plan.",
    )


def _json_payload(result: ActionResult) -> dict[str, Any] | None:
    if not result.success:
        return None
    source = result.structured_output if result.structured_output is not None else result.stdout
    try:
        payload = json.loads(source or "{}")
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"items": payload}
    return None


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _runtime_boot_id(runtime: ActionRuntime) -> str:
    reader = getattr(runtime, "boot_id", None)
    return str(reader() if callable(reader) else "").strip()


def _pending_deployment(deployments: Any) -> dict[str, Any]:
    if not isinstance(deployments, list):
        return {}
    for marker in ("staged", "pending"):
        candidate = next(
            (
                item
                for item in deployments
                if isinstance(item, dict)
                and item.get(marker)
                and not item.get("booted")
            ),
            None,
        )
        if candidate is not None:
            return candidate
    return {}
