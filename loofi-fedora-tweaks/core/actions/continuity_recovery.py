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
        return ["rpm-ostree", "upgrade"]
    return ["dnf5", "upgrade", "--refresh", "-y", "--offline"]


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
    offline_log = runtime.execute_read_only(
        ["dnf5", "offline", "log", "--number=-1"],
        action_id="update-fedora-verify-offline-log",
        timeout=60,
    )
    if missing or not health.success or not offline_log.success:
        return VerificationDecision.failed("Fedora package verification failed.", missing_packages=sorted(set(missing)))
    return VerificationDecision.succeeded("Planned Fedora packages and package health were verified.", verified_packages=len(candidates))


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
    payload = _json_payload(result)
    raw = payload.get("deployments", []) if isinstance(payload, Mapping) else []
    deployments = [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
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


def _json_payload(result: ActionResult) -> dict[str, Any]:
    if not result.success:
        return {}
    try:
        payload = json.loads(result.stdout or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {"items": payload}


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
