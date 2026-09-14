"""Action Center state grouping and plain-language presentation helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

ACTION_CENTER_STATE_GROUPS = (
    ("needs_review", "Needs review"),
    ("ready", "Ready"),
    ("running", "Running"),
    ("waiting_restart", "Waiting for restart"),
    ("completed", "Completed"),
    ("failed", "Failed"),
)


@dataclass(frozen=True)
class ActionCenterDetails:
    """Visible safety facts plus progressively disclosed technical evidence."""

    summary_lines: tuple[str, ...]
    technical_lines: tuple[str, ...]
    risk: str
    scope: str
    requirements: str
    validation: str
    rollback: str


def action_center_group_for_state(state: str) -> str:
    """Map persisted plan/run states into the six established work groups."""
    if state in {"draft", "planned", "needs_review", "manual_only"}:
        return "needs_review"
    if state == "ready":
        return "ready"
    if state in {"running", "verifying"}:
        return "running"
    if state == "awaiting_reboot":
        return "waiting_restart"
    if state == "succeeded":
        return "completed"
    return "failed"


def lifecycle_presence_copy(
    group_label: str,
    count: int,
    translate: Callable[[str], object],
) -> tuple[str, str]:
    """Describe a non-empty work group without stale empty-state wording."""
    label = str(translate(group_label))
    title = str(translate("%1 changes")).replace("%1", label)
    if count == 1:
        message = str(translate("1 change is currently in %1. Select it to review its current state."))
        return title, message.replace("%1", label.lower())
    message = str(translate("%1 changes are currently in %2. Select one to review its current state."))
    return title, message.replace("%1", str(count)).replace("%2", label.lower())


def privilege_label(value: object, translate: Callable[[str], object]) -> str:
    normalized = str(value or "none").strip().lower()
    if normalized in {"pkexec", "root", "administrator"}:
        return str(translate("Administrator approval (pkexec)"))
    if normalized in {"", "none", "user"}:
        return str(translate("None"))
    return str(translate(normalized.replace("_", " ").title()))


def restart_label(
    reboot_policy: object,
    translate: Callable[[str], object],
    *,
    required: bool = False,
) -> str:
    if required:
        return str(translate("Required"))
    return str(
        {
            "none": translate("Not required"),
            "may_require": translate("May be required"),
            "required": translate("Required"),
        }.get(str(reboot_policy), translate("Shown after plan creation"))
    )


def candidate_details(item: Any, translate: Callable[[str], object]) -> ActionCenterDetails:
    def t(value: str) -> str:
        return str(translate(value))
    metadata = getattr(item, "metadata", {}) or {}
    command_preview = tuple(getattr(item, "command_preview", ()) or ())
    verification_command = tuple(getattr(item, "verification_command", ()) or ())
    command = " ".join(command_preview) if command_preview else t("Manual-only")
    verification = t("Required after execution") if verification_command else t("Manual verification guidance")
    resources = ", ".join(metadata.get("affected_resources", ())) or t("Shown after plan creation")
    reboot = restart_label(metadata.get("reboot_policy"), translate)
    privilege = privilege_label(getattr(item, "privilege", "none"), translate)
    rollback = str(getattr(item, "rollback_hint", ""))
    risk = t(str(getattr(item, "risk_level", "unknown")).replace("_", " ").title())
    return ActionCenterDetails(
        summary_lines=(
            f"{t('Intended outcome')}: {getattr(item, 'title', '')}",
            str(getattr(item, "description", "")),
            f"{t('Affected components')}: {resources}",
            f"{t('Privilege required')}: {privilege}",
            f"{t('Restart requirement')}: {reboot}",
            f"{t('Verification')}: {verification}",
            f"{t('Recovery guidance')}: {rollback}",
        ),
        technical_lines=(
            f"{t('Technical source')}: {getattr(item, 'source', '')}",
            f"{t('Definition')}: {getattr(item, 'id', '')}",
            f"{t('Risk')}: {getattr(item, 'risk_level', '')}",
            f"{t('Command preview')}: {command}",
            f"{t('Verification command')}: {' '.join(verification_command) or t('None')}",
        ),
        risk=risk,
        scope=resources,
        requirements=f"{privilege} · {t('Restart')}: {reboot}",
        validation=verification,
        rollback=rollback,
    )


def plan_details(plan: Any, title: str, translate: Callable[[str], object]) -> ActionCenterDetails:
    def t(value: str) -> str:
        return str(translate(value))
    context = getattr(plan, "finding_context", None)
    context_line = (
        f"{t('System Check')}: {context.check_result_id} / {context.finding_fingerprint[:12]}"
        if context is not None
        else f"{t('System Check')}: {t('not linked')}"
    )
    resources = ", ".join(plan.affected_resources) or t("System")
    privilege = privilege_label("pkexec" if plan.privileged else "none", translate)
    reboot = restart_label(plan.reboot_policy, translate)
    validation = f"{t('Preflight')}: {plan.policy_decision.explanation} · {t('Verification required after execution')}"
    risk = t(str(plan.risk_level).replace("_", " ").title())
    return ActionCenterDetails(
        summary_lines=(
            f"{t('Intended outcome')}: {title}",
            f"{t('Affected components')}: {resources}",
            f"{t('Privilege required')}: {privilege}",
            f"{t('Restart requirement')}: {reboot}",
            f"{t('Verification')}: {t('Required after execution')}",
            f"{t('Recovery guidance')}: {plan.recovery_guidance}",
        ),
        technical_lines=(
            f"{t('Plan')}: {plan.plan_id}",
            f"{t('Definition')}: {plan.action_id}",
            context_line,
            f"{t('State')}: {plan.state}",
            f"{t('Risk')}: {plan.risk_level}",
            f"{t('Preflight')}: {plan.policy_decision.reason_code} — {plan.policy_decision.explanation}",
            f"{t('Command preview')}: {' '.join(plan.preview) if plan.preview else t('Manual-only')}",
            f"{t('Expires')}: {plan.expires_at}",
        ),
        risk=risk,
        scope=resources,
        requirements=f"{privilege} · {t('Restart')}: {reboot}",
        validation=validation,
        rollback=str(plan.recovery_guidance),
    )


def preview_lines(
    item: Any,
    translate: Callable[[str], object],
    *,
    result_message: str = "",
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Build preview copy without implying that a plan exists."""
    def t(value: str) -> str:
        return str(translate(value))

    title = str(getattr(item, "title", ""))
    rollback = str(getattr(item, "rollback_hint", ""))
    risk = str(getattr(item, "risk_level", ""))
    command_preview = tuple(getattr(item, "command_preview", ()) or ())
    if str(getattr(item, "source", "")) == "catalog:v18":
        message = t("Create a plan to run fresh preflight and generate the exact command.")
        return (
            (f"{t('Preview')}: {title}", message, f"{t('Recovery guidance')}: {rollback}"),
            (
                f"{t('Preview')}: {title}",
                message,
                f"{t('Risk')}: {risk}",
                f"{t('Recovery')}: {rollback}",
            ),
        )
    command = " ".join(command_preview) if command_preview else t("Manual-only")
    return (
        (
            f"{t('Preview')}: {title}",
            f"{t('Result')}: {result_message}",
            f"{t('Recovery guidance')}: {rollback}",
        ),
        (
            f"{t('Preview')}: {title}",
            f"{t('Result')}: {result_message}",
            f"{t('Risk')}: {risk}",
            f"{t('Rollback')}: {rollback}",
            f"{t('Command')}: {command}",
        ),
    )


def run_details(
    run: Any,
    title: str,
    privilege: str,
    translate: Callable[[str], object],
) -> ActionCenterDetails:
    def t(value: str) -> str:
        return str(translate(value))
    verification = run.verification_result or {}
    context = getattr(run, "finding_context", None)
    context_line = (
        f"{t('System Check')}: {context.check_result_id} / {context.finding_fingerprint[:12]}"
        if context is not None
        else f"{t('System Check')}: {t('not linked')}"
    )
    resources = ", ".join(run.affected_resources) or t("System")
    reboot = restart_label(run.reboot_policy, translate, required=run.reboot_required)
    validation = str(verification.get("message", t("Pending")))
    resolution = (
        t("Finding resolution: requires a later compatible System Check")
        if context is not None
        else t("Finding resolution: not linked")
    )
    if run.state == "awaiting_reboot":
        next_step = t("Restart when convenient, then choose Check result.")
    elif run.state in {"running", "verifying"}:
        next_step = t("Wait for the operation to finish, then choose Check result.")
    elif run.state == "succeeded":
        next_step = t("No further step is required; review the recorded result if needed.")
    else:
        next_step = t("Review the recorded result and recovery guidance before retrying.")
    return ActionCenterDetails(
        summary_lines=(
            f"{t('Intended outcome')}: {title}",
            f"{t('Affected components')}: {resources}",
            f"{t('Privilege required')}: {privilege}",
            f"{t('Restart requirement')}: {reboot}",
            f"{t('What was checked')}: {validation}",
            f"{t('Next step')}: {next_step}",
            f"{t('Verification')}: {validation}",
            f"{t('Recovery guidance')}: {run.recovery_status}",
        ),
        technical_lines=(
            f"{t('Run')}: {run.run_id}",
            f"{t('Plan')}: {run.plan_id}",
            f"{t('Definition')}: {run.action_id}",
            context_line,
            f"{t('State')}: {run.state}",
            f"{t('Execution')}: {(run.execution_result or {}).get('message', '')}",
            f"{t('Verification attempts')}: {getattr(run, 'verification_attempts', 0)}",
            resolution,
        ),
        risk=t("Recorded in the reviewed plan"),
        scope=resources,
        requirements=f"{privilege} · {t('Restart')}: {reboot}",
        validation=validation,
        rollback=str(run.recovery_status),
    )


def run_banner_facts(run: Any, translate: Callable[[str], object]) -> tuple[str, str, str]:
    """Provide level, title, and descriptive message for a saved run's current state."""
    state = str(getattr(run, "state", ""))

    def t(value: str) -> str:
        return str(translate(value))

    mapping: dict[str, tuple[str, str, str]] = {
        "succeeded": (
            "success",
            t("Completed and verified"),
            t("The recorded result matches the reviewed change."),
        ),
        "awaiting_reboot": (
            "warning",
            t("Waiting for restart"),
            t("Restart when convenient, then choose Check result. The change is not yet verified."),
        ),
        "verifying": (
            "info",
            t("Result needs checking"),
            t("Choose Check result to verify the completed execution."),
        ),
        "verification_failed": (
            "warning",
            t("Verification failed"),
            t("Review the verification details and recovery guidance before taking another action."),
        ),
        "running": (
            "info",
            t("Maintenance in progress"),
            t("This saved run has not recorded a final result yet."),
        ),
    }
    return mapping.get(
        state,
        ("warning", t("Result cannot be confirmed"), t("Review the execution details and recovery guidance.")),
    )


def filter_lifecycle_records(
    group_id: str,
    plans: list[Any],
    runs: list[Any],
    requested_action_id: str,
    items: list[Any],
    adapters: dict[str, str],
) -> list[tuple[str, Any]]:
    """Collect plans, runs, or candidates matching a specific lifecycle group."""
    records: list[tuple[str, Any]] = []
    if group_id == "needs_review":
        records.extend(
            ("plan", plan)
            for plan in plans
            if action_center_group_for_state(str(plan.state)) == group_id
        )
        if requested_action_id:
            records.extend(
                ("candidate", item)
                for item in items
                if adapters.get(getattr(item, "id", ""), getattr(item, "id", "")) == requested_action_id
            )
    elif group_id == "ready":
        records.extend(
            ("plan", plan)
            for plan in plans
            if action_center_group_for_state(str(plan.state)) == group_id
        )
    else:
        if group_id == "failed":
            records.extend(
                ("plan", plan)
                for plan in plans
                if action_center_group_for_state(str(plan.state)) == group_id
            )
        records.extend(
            ("run", run)
            for run in runs
            if action_center_group_for_state(str(run.state)) == group_id
        )
    return records


def format_history_records(
    plans: list[Any],
    runs: list[Any],
    history: list[dict[str, Any]],
) -> list[str]:
    """Build technical history line items from plans, runs, and audit events."""
    lines: list[str] = []
    for plan in reversed(plans):
        lines.append(f"{plan.plan_id}: {plan.action_id} [{plan.state}]")
    for run in reversed(runs):
        lines.append(f"{run.run_id}: {run.action_id} [{run.state}]")
    for entry in history:
        event = entry.get("event", "event")
        action = entry.get("action", {})
        title = action.get("title", action.get("id", "unknown")) if isinstance(action, dict) else "unknown"
        lines.append(f"{event}: {title}")
    return lines


__all__ = [
    "ACTION_CENTER_STATE_GROUPS",
    "ActionCenterDetails",
    "action_center_group_for_state",
    "candidate_details",
    "filter_lifecycle_records",
    "format_history_records",
    "lifecycle_presence_copy",
    "plan_details",
    "preview_lines",
    "privilege_label",
    "restart_label",
    "run_banner_facts",
    "run_details",
]
