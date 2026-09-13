"""Public CLI entry point for Fedora Maintenance Core.

The CLI deliberately exposes a small, read-first command surface.  Legacy
specialist commands are no longer registered by :mod:`cli.parser`; keeping
their handlers imported here made the application look larger than it is and
caused retired code to load during every invocation.  Canonical handlers are
imported lazily where practical so ``loofi --help`` remains fast and safe on
minimal Fedora installations.
"""

from __future__ import annotations

import json as json_module
import logging
import os
import sys
import typing
from typing import Any, Dict, List, Optional

from cli.commands import readiness_commands as _readiness_commands
from cli.parser import build_parser
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from version import __version__, __version_codename__

logger = logging.getLogger(__name__)

# Preserve the small set of readiness helpers that older embedders import
# from ``cli.main`` without importing the retired command registry.
_cmd_readiness_action = _readiness_commands._cmd_readiness_action
_print_action_result = _readiness_commands._print_action_result
_print_readiness_report = _readiness_commands._print_readiness_report
_print_release_plan = _readiness_commands._print_release_plan
cmd_action_center = _readiness_commands.cmd_action_center
cmd_fedora44_readiness = _readiness_commands.cmd_fedora44_readiness
cmd_readiness = _readiness_commands.cmd_readiness
cmd_state = _readiness_commands.cmd_state

# Add the source root for installed/editable and direct-script execution.
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Global presentation flags are intentionally process-local.  The parser is
# rebuilt for each invocation, while command modules use these callbacks for a
# consistent text/JSON contract.
_json_output = False
_operation_timeout = 300
_dry_run = False


def _print(text: Any) -> Any:
    """Print text unless JSON output was requested."""
    if not _json_output:
        # CLI stdout is an explicit caller-facing response, not application logging.
        # codeql[py/clear-text-logging-sensitive-data]
        print(text)


def _output_json(data: Any) -> Any:
    """Serialize one caller-facing JSON response."""
    # CLI stdout is an explicit caller-facing response, not application logging.
    # codeql[py/clear-text-logging-sensitive-data]
    print(json_module.dumps(data, indent=2, default=str))


def run_operation(op_result: Any, timeout: Any = None) -> Any:
    """Fail closed for callers that still supply an unclassified operation.

    This compatibility helper is intentionally inert.  All mutations must be
    named Action Center definitions and pass through preview, confirmation,
    execution, and verification.
    """
    del op_result, timeout
    payload = {
        "schema_version": 4,
        "error": "closed_action_definition_required",
        "message": "Direct CLI command execution is disabled. Use a named Action Center definition.",
        "auto_apply": False,
    }
    if _json_output:
        _output_json(payload)
    else:
        _print(payload["message"])
    return False


def _create_action_center_plan(action_id: str, parameters: Dict[str, Any]) -> Any:
    """Create a reviewed Action Center plan for compatibility callers."""
    from core.actions import ActionCatalog, ActionCenterOrchestrator
    from core.actions.catalog import validate_parameters

    catalog = ActionCatalog()
    definition = catalog.get(action_id)
    if definition is None:
        raise ValueError(f"Unknown Action Center definition: {action_id}")
    parameter_decision = validate_parameters(definition, parameters)
    if not parameter_decision.allowed:
        raise ValueError(
            f"Invalid parameters for {action_id}: {parameter_decision.explanation}"
        )
    return ActionCenterOrchestrator(catalog=catalog).plan(action_id, parameters)


def _emit_legacy_plans(plans: Any) -> int:
    """Render plans for retained activity/recovery presentation adapters."""
    summaries = [
        {
            "plan_id": plan.plan_id,
            "state": plan.state,
            "definition_id": plan.action_id,
            "review_required": True,
            "auto_apply": False,
            "next_action": (
                f"loofi-fedora-tweaks --cli action-center apply {plan.plan_id} --confirm"
                if plan.state != "blocked"
                else plan.recovery_guidance
            ),
        }
        for plan in plans
    ]
    payload = {
        "schema_version": 4,
        "plans": [plan.to_dict() for plan in plans],
        "plan_summaries": summaries,
        "review_required": True,
        "auto_apply": False,
    }
    if _json_output:
        _output_json(payload)
    else:
        for plan, summary in zip(plans, summaries):
            _print(f"Plan {plan.plan_id}: {plan.action_id} [{plan.state}]")
            _print(f"  {plan.policy_decision.explanation}")
            _print(f"  Next: {summary['next_action']}")
    return 0


def cmd_info(_args: Any) -> Any:
    """Show Fedora deployment and package-manager information."""
    from cli.commands.system_commands import handle_info
    from core.executor.operations import TweakOps
    from services.system import SystemManager

    return handle_info(
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        version=__version__,
        codename=__version_codename__,
        system_manager_cls=SystemManager,
        tweak_ops_cls=TweakOps,
    )


def cmd_activity(args: Any) -> int:
    """Inspect the Trusted Change Journal and recovery guidance."""
    from cli.commands.activity_commands import handle_activity

    return handle_activity(
        args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        create_plan=_create_action_center_plan,
        emit_plans=_emit_legacy_plans,
    )


def cmd_check(args: Any) -> Any:
    """Run the explicit, read-only System Check."""
    setattr(args, "health_action", "check")
    return cmd_health(args)


def cmd_changes(args: Any) -> int:
    """Route the public ``changes`` grammar to the Action Center."""
    action = getattr(args, "changes_action", None) or getattr(args, "action", "list")
    # ``changes list`` is a recorded history view.  Readiness candidates are
    # exposed only by the internal Action Center command so users do not
    # confuse available recommendations with completed changes.
    if action == "list":
        action = "history"
    setattr(args, "action", action)

    if hasattr(args, "id"):
        setattr(args, "action_id", args.id)
        setattr(args, "target", FEDORA_RELEASE_POLICY.stable_target)
    elif action == "apply" and hasattr(args, "target"):
        # The positional action/plan identifier must be captured before the
        # optional Fedora release target replaces ``args.target``.
        setattr(args, "action_id", args.target)
        setattr(
            args,
            "target",
            getattr(args, "release_target", FEDORA_RELEASE_POLICY.stable_target),
        )
        setattr(args, "confirm", getattr(args, "yes", False) is True)
    elif action == "verify" and hasattr(args, "run_id"):
        # Verification operates on the persisted run, never on a plan ID.
        setattr(args, "action_id", args.run_id)
        setattr(args, "target", FEDORA_RELEASE_POLICY.stable_target)
    elif not hasattr(args, "target"):
        setattr(args, "target", FEDORA_RELEASE_POLICY.stable_target)
    return cmd_action_center(args)


def cmd_troubleshoot(args: Any) -> int:
    """Run or inspect one bounded troubleshooting session."""
    from cli.commands.troubleshooting_commands import handle_troubleshoot
    from utils.journal import JournalManager

    return handle_troubleshoot(
        args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        journal_manager_cls=JournalManager,
    )


def cmd_health(args: Any) -> Any:
    """Run/read canonical checks and retained observability aliases."""
    action = getattr(args, "health_action", None)
    if action == "check":
        from core.system_check.presentation import PRESENTATION_SCHEMA_ID, PRESENTATION_SCHEMA_VERSION
        from core.system_check.service import SystemCheckService

        result = SystemCheckService().run()
        payload = {
            "schema_id": PRESENTATION_SCHEMA_ID,
            "schema_version": PRESENTATION_SCHEMA_VERSION,
            "command": "check",
            "data": {"result": result.to_dict()},
        }
        if _json_output:
            _output_json(payload)
        else:
            _print(f"System Check: {result.state}")
            _print(f"Findings: {len(result.findings)}")
            if result.source_errors:
                _print("Unavailable sources: " + ", ".join(error.source_id for error in result.source_errors))
        return 0 if result.state in {"completed", "partial"} else 1

    if action in {"findings", "history"}:
        from core.system_check.presentation import SystemCheckPresentationService

        state = SystemCheckPresentationService().load(history_limit=getattr(args, "limit", 10))
        state_data = state.to_dict()
        if action == "findings":
            data = {
                "latest_check_id": state.latest_check_id,
                "latest_state": state.latest_state,
                "latest_completed_at": state.latest_completed_at,
                "findings": state_data["findings"],
                "unavailable_sources": list(state.unavailable_sources),
                "snapshot_error": state.snapshot_error,
            }
        else:
            data = {
                "history": state_data["history"],
                "metrics": state_data["metrics"],
                "snapshot_error": state.snapshot_error,
                "metric_error": state.metric_error,
            }
        payload = {
            "schema_id": state.schema_id,
            "schema_version": state.schema_version,
            "command": action,
            "data": data,
        }
        if _json_output:
            _output_json(payload)
        elif action == "findings":
            _print("Current System Check findings")
            if not state.findings:
                _print("No saved findings.")
            for finding in state.findings:
                _print(f"- [{finding.severity}] {finding.title}: {finding.summary}")
        else:
            _print("System Check history")
            if not state.history:
                _print("No saved history.")
            for item in state.history:
                _print(
                    f"- {item.timestamp}: {item.source} [{item.state}] "
                    f"findings={item.finding_count} new={item.new_count} resolved={item.resolved_count}"
                )
        return 0

    if action == "comparison":
        from cli.commands.system_check_commands import handle_health_comparison

        return handle_health_comparison(
            json_output=_json_output,
            output_json=_output_json,
            print_fn=_print,
        )

    if action == "snapshot":
        from core.observability import MaintenanceTrendAnalyzer, ObservabilityService

        service = ObservabilityService()
        snapshot = service.collect_snapshot(
            target=getattr(args, "target", FEDORA_RELEASE_POLICY.stable_target),
            source="cli",
        )
        timeline = service.snapshots.load()
        snapshot_payload: dict[str, Any] = {
            "schema_version": 1,
            "snapshot": snapshot.to_dict(),
            "trend_summary": MaintenanceTrendAnalyzer(timeline).analyze().to_dict(),
        }
        if _json_output:
            _output_json(snapshot_payload)
        else:
            _print("My Fedora Today snapshot recorded.")
            _print(str(snapshot_payload["trend_summary"]["summary"]))
        return 0

    if action == "timeline":
        from core.observability import HealthTimelineStore

        timeline_payload = HealthTimelineStore().export(limit=getattr(args, "limit", 10))
        if _json_output:
            _output_json(timeline_payload)
        else:
            _print("Health Timeline")
            _print(f"Snapshots: {timeline_payload['count']}")
            _print(str(timeline_payload["trend_summary"]["summary"]))
            for snapshot in timeline_payload["snapshots"]:
                _print(f"- {snapshot['timestamp']}: {snapshot['app_version']} {snapshot['app_codename']}")
        return 0

    # The compatibility alias is intentionally lazy: the canonical parser
    # exposes ``check`` and the dedicated maintenance destinations instead.
    from cli.commands.system_commands import handle_health
    from core.executor.operations import TweakOps
    from services.hardware import DiskManager
    from services.system import SystemManager
    from utils.monitor import SystemMonitor

    return handle_health(
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        system_monitor_cls=SystemMonitor,
        disk_manager_cls=DiskManager,
        tweak_ops_cls=TweakOps,
        system_manager_cls=SystemManager,
    )


def cmd_maintenance(args: Any) -> Any:
    """Show the daily maintenance snapshot and safe next action."""
    action = getattr(args, "maintenance_action", "today")
    if action != "today":
        payload = {"schema_version": 1, "error": "unknown_maintenance_command", "action": action}
        if _json_output:
            _output_json(payload)
        else:
            _print(f"Unknown maintenance command: {action}")
        return 1

    from core.actions import ActionCenterService
    from core.diagnostics.daily_maintenance import DailyMaintenanceService
    from core.observability import HealthSnapshot, HealthTimelineStore, MaintenanceTrendAnalyzer

    target = getattr(args, "target", FEDORA_RELEASE_POLICY.stable_target)
    report = DailyMaintenanceService().collect()
    action_items = ActionCenterService().candidates_from_readiness(target)
    snapshot = HealthSnapshot.from_daily_maintenance(
        report,
        action_center_items=action_items,
        fedora_target=target,
    )
    timeline = [*HealthTimelineStore().load(), snapshot]
    maintenance_payload: dict[str, Any] = {
        "schema_version": 1,
        "daily_maintenance": report.to_dict(),
        "snapshot": snapshot.to_dict(),
        "trend_summary": MaintenanceTrendAnalyzer(timeline).analyze().to_dict(),
    }
    if _json_output or getattr(args, "json", False):
        _output_json(maintenance_payload)
    else:
        _print("My Fedora Today")
        _print(str(maintenance_payload["trend_summary"]["summary"]))
        _print(report.recommended_action)
        for card in report.cards:
            _print(f"- {card.title}: {card.state} - {card.summary}")
    return 0


def cmd_doctor(_args: Any) -> Any:
    """Run read-only platform and dependency diagnostics."""
    from cli.commands.diagnostic_commands import handle_doctor
    from services.system.system import cached_which

    return handle_doctor(_json_output, _output_json, _print, which_fn=cached_which)


def cmd_updates(args: Any) -> Any:
    """Inspect DNF5, rpm-ostree, or bootc update state."""
    from cli.commands.update_commands import handle_updates
    from utils.update_manager import UpdateManager

    return handle_updates(args, _json_output, _output_json, _print, run_operation, UpdateManager)


def cmd_support_bundle(_args: Any) -> Any:
    """Export a redacted support bundle."""
    from cli.commands.diagnostic_commands import handle_support_bundle
    from utils.journal import JournalManager

    return handle_support_bundle(_json_output, _output_json, _print, JournalManager)


def _command_handlers() -> dict[str, typing.Callable[[Any], Any]]:
    """Return exactly the eight canonical v27 command handlers."""
    return {
        "info": cmd_info,
        "check": cmd_check,
        "updates": cmd_updates,
        "troubleshoot": cmd_troubleshoot,
        "changes": cmd_changes,
        "activity": cmd_activity,
        "doctor": cmd_doctor,
        "support-bundle": cmd_support_bundle,
    }


def main(argv: Optional[List[str]] = None) -> Any:
    """Parse one CLI invocation and dispatch its canonical handler."""
    parser = build_parser()
    args = parser.parse_args(argv)

    globals()["_json_output"] = bool(getattr(args, "json", False))
    globals()["_operation_timeout"] = int(getattr(args, "timeout", 300))
    globals()["_dry_run"] = bool(getattr(args, "dry_run", False))

    if args.command is None:
        parser.print_help()
        return 0

    handler = _command_handlers().get(args.command)
    return handler(args) if handler else 0


if __name__ == "__main__":
    sys.exit(main())
