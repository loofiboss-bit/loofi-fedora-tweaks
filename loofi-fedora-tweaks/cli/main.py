"""
Loofi CLI - Command-line interface for Loofi Fedora Tweaks.
Enables headless operation and scripting.
"""

import argparse
import json as json_module
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, cast

from core.executor.operations import AdvancedOps, CleanupOps, NetworkOps, TweakOps

logger = logging.getLogger(__name__)

from core.diagnostics import HealthTimeline  # noqa: E402
from services.hardware import (
    BluetoothManager,  # noqa: E402
    DiskManager,  # noqa: E402
    TemperatureManager,  # noqa: E402
)
from services.network import (
    NetworkMonitor,  # noqa: E402
    PortAuditor,  # noqa: E402
)
from services.security import FirewallManager  # noqa: E402
from services.system import (
    ProcessManager,  # noqa: E402
    SystemManager,  # noqa: E402
)
from services.system.system import cached_which  # noqa: E402
from cli.commands.system_commands import (  # noqa: E402
    handle_disk,
    handle_health,
    handle_info,
    handle_netmon,
    handle_processes,
    handle_temperature,
)
from cli.commands.ops_commands import (  # noqa: E402
    handle_advanced,
    handle_cleanup,
    handle_network,
    handle_tweak,
)
from cli.commands.user_commands import (  # noqa: E402
    handle_focus_mode,
    handle_preset,
    handle_profile,
)
from cli.commands.insight_commands import (  # noqa: E402
    handle_ai_models,
    handle_security_audit,
)
from cli.commands.diagnostic_commands import (  # noqa: E402
    handle_audit_log,
    handle_doctor,
    handle_support_bundle,
)
from cli.commands.hardware_commands import (  # noqa: E402
    handle_bluetooth,
    handle_hardware,
    handle_storage,
    handle_vfio,
    handle_vm,
)
from cli.commands.update_commands import (  # noqa: E402
    handle_self_update,
    handle_updates,
)
from cli.commands.plugin_commands import (  # noqa: E402
    handle_plugin_marketplace,
    handle_plugins,
)
from cli.commands.network_mesh_commands import (  # noqa: E402
    handle_mesh,
    handle_teleport,
)
from cli.commands.tuning_commands import (  # noqa: E402
    handle_boot,
    handle_snapshot,
)
from cli.commands.service_package_commands import (  # noqa: E402
    handle_extension,
    handle_flatpak_manage,
    handle_package,
    handle_service,
)
from cli.commands.firewall_commands import handle_firewall  # noqa: E402
from cli.commands.agent_commands import handle_agent  # noqa: E402
from utils.focus_mode import FocusMode  # noqa: E402
from utils.journal import JournalManager  # noqa: E402
from utils.monitor import SystemMonitor  # noqa: E402
from utils.package_explorer import PackageExplorer  # noqa: E402
from utils.plugin_base import PluginLoader  # noqa: E402
from utils.plugin_installer import PluginInstaller  # noqa: E402
from utils.plugin_marketplace import PluginMarketplace  # noqa: E402
from utils.presets import PresetManager  # noqa: E402
from utils.profiles import ProfileManager  # noqa: E402
from utils.service_explorer import ServiceExplorer  # noqa: E402
from utils.storage import StorageManager  # noqa: E402
from utils.update_checker import UpdateChecker  # noqa: E402
from version import __version__, __version_codename__  # noqa: E402

# Add parent to path for imports
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# Global flag for JSON output
_json_output = False

# Global operation timeout (default 300s, configurable via --timeout)
_operation_timeout = 300

# Global dry-run flag (v35.0 Fortress)
_dry_run = False

# Keep the original timeline class reference so tests can patch either
# cli.main.HealthTimeline or utils.health_timeline.HealthTimeline.
_DEFAULT_HEALTH_TIMELINE_CLASS = HealthTimeline


def _print(text):
    """Print text (suppressed in JSON mode)."""
    if not _json_output:
        print(text)


def _output_json(data):
    """Output JSON data and exit."""
    print(json_module.dumps(data, indent=2, default=str))


def run_operation(op_result, timeout=None):
    """Execute an operation tuple (cmd, args, description).

    Args:
        op_result: Tuple of (cmd, args, description) from utils operations.
        timeout: Override timeout in seconds. Defaults to global _operation_timeout (300s).
    """
    cmd, args, desc = op_result
    full_cmd = [cmd] + args

    # Dry-run mode: show command without executing, audit-log it
    if _dry_run:
        _print(f"🔍 [DRY-RUN] Would execute: {' '.join(full_cmd)}")
        _print(f"   Description: {desc}")
        try:
            from services.security import AuditLogger

            AuditLogger().log(
                action=f"cli.{cmd}",
                params={"cmd": full_cmd, "description": desc},
                exit_code=None,
                dry_run=True,
            )
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as e:
            logger.debug("Failed to log dry-run audit entry: %s", e)
        if _json_output:
            _output_json({"dry_run": True, "command": full_cmd, "description": desc})
        return True

    _print(f"🔄 {desc}")

    op_timeout = timeout if timeout is not None else _operation_timeout

    try:
        result = subprocess.run(
            [cmd] + args,
            capture_output=True,
            text=True,
            check=False,
            timeout=op_timeout,
        )
        if result.returncode == 0:
            _print("✅ Success")
            if result.stdout.strip():
                _print(result.stdout)
        else:
            _print(f"❌ Failed (exit code {result.returncode})")
            if result.stderr.strip():
                _print(result.stderr)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        _print(f"❌ Timed out after {op_timeout}s")
        return False
    except (subprocess.SubprocessError, OSError) as e:
        _print(f"❌ Error: {e}")
        return False


def cmd_cleanup(args):
    """Handle cleanup subcommand."""
    return handle_cleanup(args=args, run_operation=run_operation, cleanup_ops_cls=CleanupOps)


def cmd_tweak(args):
    """Handle tweak subcommand."""
    return handle_tweak(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        run_operation=run_operation,
        tweak_ops_cls=TweakOps,
        system_manager_cls=SystemManager,
    )


def cmd_advanced(args):
    """Handle advanced subcommand."""
    return handle_advanced(args=args, print_fn=_print, advanced_ops_cls=AdvancedOps)


def cmd_network(args):
    """Handle network subcommand."""
    return handle_network(args=args, print_fn=_print, network_ops_cls=NetworkOps)


def cmd_info(_args):
    """Show system information."""
    return handle_info(
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        version=__version__,
        codename=__version_codename__,
        system_manager_cls=SystemManager,
        tweak_ops_cls=TweakOps,
    )


def cmd_health(args):
    """Show system health overview."""
    action = getattr(args, "health_action", None)
    if action == "snapshot":
        from core.observability import MaintenanceTrendAnalyzer, ObservabilityService

        service = ObservabilityService()
        snapshot = service.collect_snapshot(target=getattr(args, "target", "44"), source="cli")
        timeline = service.snapshots.load()
        payload = {
            "schema_version": 1,
            "snapshot": snapshot.to_dict(),
            "trend_summary": MaintenanceTrendAnalyzer(timeline).analyze().to_dict(),
        }
        if _json_output:
            _output_json(payload)
        else:
            _print("My Fedora Today snapshot recorded.")
            _print(payload["trend_summary"]["summary"])
        return 0

    if action == "timeline":
        from core.observability import HealthTimelineStore

        payload = HealthTimelineStore().export(limit=getattr(args, "limit", 10))
        if _json_output:
            _output_json(payload)
        else:
            _print("Health Timeline")
            _print(f"Snapshots: {payload['count']}")
            _print(str(payload["trend_summary"]["summary"]))
            for snapshot in payload["snapshots"]:
                _print(f"- {snapshot['timestamp']}: {snapshot['app_version']} {snapshot['app_codename']}")
        return 0

    return handle_health(
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        system_monitor_cls=SystemMonitor,
        disk_manager_cls=DiskManager,
        tweak_ops_cls=TweakOps,
        system_manager_cls=SystemManager,
    )


def cmd_maintenance(args):
    """Show v12 daily maintenance health payloads."""
    action = getattr(args, "maintenance_action", "today")
    if action != "today":
        if _json_output:
            _output_json({"schema_version": 1, "error": "unknown_maintenance_command", "action": action})
        else:
            _print(f"Unknown maintenance command: {action}")
        return 1

    from core.actions import ActionCenterService
    from core.diagnostics.daily_maintenance import DailyMaintenanceService
    from core.observability import HealthSnapshot, HealthTimelineStore, MaintenanceTrendAnalyzer

    report = DailyMaintenanceService().collect()
    action_items = ActionCenterService().candidates_from_readiness(getattr(args, "target", "44"))
    snapshot = HealthSnapshot.from_daily_maintenance(report, action_center_items=action_items, fedora_target=getattr(args, "target", "44"))
    timeline = [*HealthTimelineStore().load(), snapshot]
    payload = {
        "schema_version": 1,
        "daily_maintenance": report.to_dict(),
        "snapshot": snapshot.to_dict(),
        "trend_summary": MaintenanceTrendAnalyzer(timeline).analyze().to_dict(),
    }
    if _json_output or getattr(args, "json", False):
        _output_json(payload)
    else:
        _print("My Fedora Today")
        _print(str(payload["trend_summary"]["summary"]))
        _print(report.recommended_action)
        for card in report.cards:
            _print(f"- {card.title}: {card.state} - {card.summary}")
    return 0


def cmd_disk(args):
    """Show disk usage information."""
    return handle_disk(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        disk_manager_cls=DiskManager,
    )


def cmd_processes(args):
    """Show top processes."""
    return handle_processes(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        process_manager_cls=ProcessManager,
    )


def cmd_temperature(_args):
    """Show temperature readings."""
    return handle_temperature(
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        temperature_manager_cls=TemperatureManager,
    )


def cmd_netmon(args):
    """Show network interface stats."""
    return handle_netmon(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        network_monitor_cls=NetworkMonitor,
    )


def cmd_doctor(_args):
    """Run system diagnostics and check dependencies."""
    return handle_doctor(_json_output, _output_json, _print, which_fn=cached_which)


def cmd_hardware(_args):
    """Show detected hardware profile."""
    from services.hardware.hardware_profiles import detect_hardware_profile
    return handle_hardware(_json_output, _output_json, _print, detect_hardware_profile)


def cmd_self_update(args):
    """Check and run self-update flow."""
    return handle_self_update(
        args, _json_output, _output_json, _print, SystemManager, UpdateChecker, __version__
    )


def cmd_plugins(args):
    """Manage plugins."""
    return handle_plugins(args, _json_output, _output_json, _print, PluginLoader)


def cmd_plugin_marketplace(args):
    """Plugin marketplace operations."""
    import json as json_module
    return handle_plugin_marketplace(args, _json_output, _output_json, _print, json_module, PluginMarketplace, PluginInstaller)


def cmd_support_bundle(_args):
    """Export support bundle ZIP."""
    return handle_support_bundle(_json_output, _output_json, _print, JournalManager)


def cmd_state(args):
    """Read-only state diagnostics and explicit backup/restore flows."""
    from pathlib import Path

    from core.state import StateArchiveService, StateDoctor

    if args.state_action == "doctor":
        payload = StateDoctor().run()
    elif args.state_action == "backup":
        payload = StateArchiveService().backup(Path(args.output).expanduser())
    elif args.state_action == "restore":
        service = StateArchiveService()
        archive = Path(args.archive).expanduser()
        if args.restore_action == "plan":
            payload = service.plan_restore(archive)
        elif not args.plan_id:
            _print("--plan-id is required for restore apply")
            return 2
        else:
            payload = service.apply_restore(archive, args.plan_id)
    else:
        _print("Choose doctor, backup, or restore")
        return 2
    _output_json(payload)
    return 1 if payload.get("status") == "error" else 0


def _print_readiness_report(report, *, advanced: bool) -> int:
    """Print a readiness report in CLI text or JSON mode."""
    if _json_output:
        _output_json(report.to_dict(advanced=advanced))
        return 0 if report.status in {"ready", "preview"} else 1

    _print("═══════════════════════════════════════════")
    _print(f"   {report.target} Readiness")
    _print("═══════════════════════════════════════════")
    _print(f"\nScore: {report.score}/100")
    _print(report.summary)
    for check in report.checks:
        marker = "OK" if check.status == "pass" else check.status.upper()
        _print(f"\n[{marker}] {check.title}")
        _print(f"  {check.summary}")
        _print(f"  {check.beginner_guidance}")
        if check.recommendation:
            _print(f"  Recommendation: {check.recommendation.title}")
        if advanced:
            if check.command_preview:
                _print(f"  Command: {' '.join(check.command_preview)}")
            if check.advanced_detail:
                _print(f"  Detail: {check.advanced_detail[:600]}")
    return 0 if report.status in {"ready", "preview"} else 1


def _print_release_plan(report) -> int:
    """Print a guided release plan in CLI text or JSON mode."""
    from core.diagnostics.release_readiness import ReleaseReadiness

    plan = cast(Dict[str, Any], ReleaseReadiness.build_release_plan(report))
    if _json_output:
        _output_json(plan)
        return 0

    _print("═══════════════════════════════════════════")
    _print(f"   {report.target} Upgrade Plan")
    _print("═══════════════════════════════════════════")
    _print(f"\nScore: {report.score}/100")
    _print(str(plan["summary"]))
    _print(f"Next action: {plan['next_action']}")

    changes = cast(Dict[str, Any], plan.get("target_changes", {}))
    important = cast(List[Dict[str, Any]], changes.get("important_changes", []))
    risks = cast(List[Dict[str, Any]], changes.get("known_risks", []))
    if important:
        _print("\nWhat changed:")
        for change in important:
            _print(f"- {change.get('title')}: {change.get('summary')}")
    if risks:
        _print("\nKnown risks:")
        for risk in risks:
            _print(f"- {risk.get('title')}: {risk.get('summary')}")

    attention = cast(List[Dict[str, Any]], plan.get("attention", []))
    if attention:
        _print("\nNeeds review:")
        for check in attention:
            _print(f"- {check.get('id')}: {check.get('summary')}")
    return 0


def cmd_readiness(args):
    """Run release readiness diagnostics."""
    from core.diagnostics.release_readiness import ReleaseReadiness

    readiness_action = getattr(args, "readiness_action", None)
    if readiness_action:
        if isinstance(readiness_action, str):
            return _cmd_readiness_action(args)

    target = getattr(args, "target", "44")
    report = ReleaseReadiness.run(target)
    return _print_readiness_report(report, advanced=getattr(args, "advanced", False))


def cmd_fedora44_readiness(args):
    """Run Fedora KDE 44 readiness diagnostics (compatibility alias)."""
    from core.diagnostics.release_readiness import ReleaseReadiness

    report = ReleaseReadiness.run("44")
    return _print_readiness_report(report, advanced=getattr(args, "advanced", False))


def _print_action_result(result) -> int:
    """Print an action result in text or JSON form."""
    payload = result.to_dict()
    if _json_output:
        _output_json(payload)
    else:
        status = "OK" if result.success else "FAILED"
        _print(f"[{status}] {result.message}")
        candidate = (result.data or {}).get("candidate") if result.data else None
        if candidate:
            command_preview = candidate.get("command_preview") or []
            if command_preview:
                _print(f"Command preview: {' '.join(command_preview)}")
            _print(f"Risk: {candidate.get('risk_level')}  Privileged: {candidate.get('privileged')}  Manual only: {candidate.get('manual_only')}")
            if candidate.get("revert_hint"):
                _print(f"Rollback: {candidate.get('revert_hint')}")
    return 0 if result.success else 1


def _cmd_readiness_action(args) -> int:
    """Handle nested readiness action commands."""
    from core.diagnostics.readiness_actions import ReadinessActionService

    target = getattr(args, "target", "44")
    action = getattr(args, "readiness_action", "")
    action_id = getattr(args, "action_id", "")

    if action == "actions":
        plan = ReadinessActionService.build_plan(target)
        if _json_output:
            _output_json(plan.to_dict())
        else:
            _print(f"{plan.target} Action Inbox")
            if not plan.candidates:
                _print("No readiness actions are currently available.")
            for plan_candidate in plan.candidates:
                mode = "manual" if plan_candidate.manual_only else "executable"
                _print(f"- {plan_candidate.id}: {plan_candidate.title} [{plan_candidate.risk_level}, {mode}]")
                _print(f"  {plan_candidate.explanation}")
                if plan_candidate.command_preview:
                    _print(f"  Preview: {' '.join(plan_candidate.command_preview)}")
        return 0

    if action == "plan":
        from core.diagnostics.release_readiness import ReleaseReadiness

        report = ReleaseReadiness.run(target, mode="upgrade-plan")
        return _print_release_plan(report)

    if action == "explain":
        from core.diagnostics.release_readiness import ReleaseReadiness

        explanation = ReleaseReadiness.explain_check(action_id, target, mode="upgrade-plan")
        if explanation is None:
            if _json_output:
                _output_json({"error": "not_found", "check_id": action_id})
            else:
                _print(f"Readiness check not found: {action_id}")
            return 1
        if _json_output:
            _output_json(explanation)
        else:
            check = cast(Dict[str, Any], explanation["check"])
            _print(f"{check['title']} ({check['id']})")
            _print(check["summary"])
            _print(check["beginner_guidance"])
            if check.get("command_preview"):
                _print(f"Command: {' '.join(check['command_preview'])}")
            if check.get("advanced_detail"):
                _print(f"Detail: {str(check['advanced_detail'])[:1000]}")
        return 0

    if action == "export":
        from core.export.support_bundle_v10 import SupportBundleV10

        path = getattr(args, "path", None) or f"loofi-readiness-{target}.json"
        if _json_output:
            _output_json(SupportBundleV10.generate_bundle(target=target))
            return 0
        SupportBundleV10.save_json(path, target=target)
        _print(f"Exported readiness support bundle: {path}")
        return 0

    if action == "action-info":
        candidate = ReadinessActionService.get_candidate(action_id, target)
        if candidate is None:
            if _json_output:
                _output_json({"error": "not_found", "action_id": action_id})
            else:
                _print(f"Readiness action not found: {action_id}")
            return 1
        if _json_output:
            _output_json(candidate.to_dict())
        else:
            _print(f"{candidate.title} ({candidate.id})")
            _print(candidate.explanation)
            _print(f"Related check: {candidate.related_check_id}")
            _print(f"Risk: {candidate.risk_level}")
            _print(f"Privileged: {candidate.privileged}")
            _print(f"Manual only: {candidate.manual_only}")
            if candidate.command_preview:
                _print(f"Command preview: {' '.join(candidate.command_preview)}")
            if candidate.revert_hint:
                _print(f"Rollback: {candidate.revert_hint}")
            if candidate.verification_command:
                _print(f"Verify: {' '.join(candidate.verification_command)}")
            if candidate.docs_link:
                _print(f"Docs: {candidate.docs_link}")
        return 0

    if action == "action-preview":
        return _print_action_result(ReadinessActionService.preview(action_id, target))

    if action == "action-run":
        result = ReadinessActionService.run(
            action_id,
            target_key=target,
            confirm=getattr(args, "confirm", False),
        )
        return _print_action_result(result)

    if action == "action-verify":
        return _print_action_result(ReadinessActionService.verify(action_id, target))

    if _json_output:
        _output_json({"error": "unknown_readiness_action", "action": action})
    else:
        _print(f"Unknown readiness action command: {action}")
    return 1


def cmd_action_center(args) -> int:
    """Plan, apply, verify, and inspect Action Center maintenance."""
    from core.actions import (
        ActionCenterBusyError,
        ActionCenterError,
        ActionCenterOrchestrator,
        ActionCenterService,
        ActionPlanRejectedError,
        ActionPlanStore,
        ActionRunStore,
    )

    target = getattr(args, "target", "44")
    action = getattr(args, "action", "list")

    def emit(payload: Dict[str, Any], lines: List[str]) -> None:
        if _json_output:
            _output_json(payload)
        else:
            for line in lines:
                _print(line)

    if action in {"plan", "show", "apply", "verify"}:
        identifier = str(getattr(args, "action_id", "") or "")
        orchestrator = ActionCenterOrchestrator()
        try:
            if action == "plan":
                parameters = {}
                service_unit = getattr(args, "service", None)
                if service_unit:
                    parameters["service"] = service_unit
                plan = orchestrator.plan(identifier, parameters, target=target)
                payload = {
                    "schema_version": 1,
                    "plan": plan.to_dict(),
                    "policy_decision": plan.policy_decision.to_dict(),
                }
                emit(
                    payload,
                    [
                        f"Plan {plan.plan_id}: {plan.action_id} [{plan.state}]",
                        f"Policy: {plan.policy_decision.reason_code} - {plan.policy_decision.explanation}",
                        f"Preview: {' '.join(plan.preview) if plan.preview else 'manual-only'}",
                        f"Expires: {plan.expires_at}",
                    ],
                )
                return 0 if plan.state != "blocked" else 1

            if action == "show":
                plan = orchestrator.get_plan(identifier)
                payload = {
                    "schema_version": 1,
                    "plan": plan.to_dict(),
                    "policy_decision": plan.policy_decision.to_dict(),
                }
                emit(
                    payload,
                    [
                        f"Plan {plan.plan_id}: {plan.action_id} [{plan.state}]",
                        f"Risk: {plan.risk_level}; privileged: {plan.privileged}",
                        f"Policy: {plan.policy_decision.reason_code} - {plan.policy_decision.explanation}",
                        f"Preview: {' '.join(plan.preview) if plan.preview else 'manual-only'}",
                        f"Recovery: {plan.recovery_guidance}",
                    ],
                )
                return 0

            if action == "apply":
                plan = orchestrator.get_plan(identifier)
                run = orchestrator.apply(
                    identifier,
                    confirmed=bool(getattr(args, "confirm", False)),
                    accept_no_rollback=bool(getattr(args, "accept_no_rollback", False)),
                    timeout=_operation_timeout,
                )
                payload = {
                    "schema_version": 1,
                    "run": run.to_dict(),
                    "policy_decision": plan.policy_decision.to_dict(),
                }
                emit(
                    payload,
                    [
                        f"Run {run.run_id}: {run.action_id} [{run.state}]",
                        "Execution recorded. Run the separate verify command if state is verifying.",
                        f"Recovery: {run.recovery_status}",
                    ],
                )
                return 0 if run.state == "verifying" else 1

            run = orchestrator.verify(identifier)
            plan = orchestrator.get_plan(run.plan_id)
            payload = {
                "schema_version": 1,
                "run": run.to_dict(),
                "policy_decision": plan.policy_decision.to_dict(),
            }
            emit(
                payload,
                [
                    f"Run {run.run_id}: {run.action_id} [{run.state}]",
                    f"Recovery: {run.recovery_status}",
                ],
            )
            return 0 if run.state == "succeeded" else 1
        except ActionPlanRejectedError as exc:
            payload = {
                "schema_version": 1,
                "error": "action_plan_rejected",
                "policy_decision": exc.decision.to_dict(),
            }
            emit(payload, [f"Action blocked: {exc.decision.reason_code} - {exc.decision.explanation}"])
            return 1
        except ActionCenterBusyError as exc:
            payload = {"schema_version": 1, "error": "action_center_busy", "message": str(exc)}
            emit(payload, [str(exc)])
            return 1
        except ActionCenterError as exc:
            payload = {"schema_version": 1, "error": "action_center_error", "message": str(exc)}
            emit(payload, [str(exc)])
            return 1

    service = ActionCenterService()
    candidates = service.candidates_from_readiness(target)

    if action == "list":
        payload = {"target": target, "candidates": [item.to_dict() for item in candidates]}
        if _json_output:
            _output_json(payload)
            return 0
        _print(f"{target} Action Center")
        if not candidates:
            _print("No action candidates are currently available.")
        for item in candidates:
            _print(f"- {item.id}: {item.title} [{item.state}, {item.risk_level}]")
            _print(f"  {item.description}")
            if item.command_preview:
                _print(f"  Preview: {' '.join(item.command_preview)}")
            if item.rollback_hint:
                _print(f"  Rollback: {item.rollback_hint}")
        return 0

    if action == "recommendations":
        recommendations = service.recommendations_from_timeline(limit=getattr(args, "limit", 25))
        payload = {"schema_version": 1, "recommendations": [item.to_dict() for item in recommendations]}
        if _json_output:
            _output_json(payload)
        else:
            if not recommendations:
                _print("No Action Center recommendations from the health timeline.")
            for item in recommendations:
                _print(f"- {item.id}: {item.title} [{item.risk_level}]")
                _print(f"  Why: {item.why_this_matters}")
                _print(f"  Safe next step: {item.safe_next_step}")
        return 0

    if action == "preview":
        action_id = getattr(args, "action_id", "")
        preview_item = next((candidate for candidate in candidates if candidate.id == action_id), None)
        if preview_item is None:
            if _json_output:
                _output_json({"error": "not_found", "action_id": action_id})
            else:
                _print(f"Action Center item not found: {action_id}")
            return 1
        return _print_action_result(service.preview(preview_item))

    if action == "history":
        limit = getattr(args, "limit", 25)
        legacy_history = service.recent_history(limit=limit)
        plan_history = [plan.to_dict() for plan in ActionPlanStore().list(limit=min(limit, 50))]
        run_history = [run.to_dict() for run in ActionRunStore().list(limit=min(limit, 100))]
        payload = {
            "schema_version": 1,
            "history": legacy_history,
            "plans": plan_history,
            "runs": run_history,
        }
        if _json_output:
            _output_json(payload)
        else:
            if not legacy_history and not run_history:
                _print("No Action Center history recorded.")
            for entry in legacy_history:
                _print(json_module.dumps(entry, default=str))
            for run_entry in run_history:
                _print(f"{run_entry['run_id']}: {run_entry['action_id']} [{run_entry['state']}]")
        return 0

    if _json_output:
        _output_json({"error": "unknown_action_center_command", "action": action})
    else:
        _print(f"Unknown Action Center command: {action}")
    return 1


# ==================== v11.5 / v12.0 COMMANDS ====================


def cmd_vm(args):
    """Handle VM subcommand."""
    from services.virtualization import VMManager
    return handle_vm(args, _json_output, _output_json, _print, VMManager)


def cmd_vfio(args):
    """Handle VFIO GPU passthrough subcommand."""
    from services.virtualization import VFIOAssistant
    return handle_vfio(args, _json_output, _output_json, _print, VFIOAssistant)


def cmd_mesh(args):
    """Handle mesh networking subcommand."""
    from services.network import MeshDiscovery
    return handle_mesh(args, _json_output, _output_json, _print, MeshDiscovery)


def cmd_teleport(args):
    """Handle state teleport subcommand."""
    from services.storage import StateTeleportManager
    return handle_teleport(args, _json_output, _output_json, _print, StateTeleportManager)


def cmd_ai_models(args):
    """Handle AI models subcommand."""
    from core.ai import RECOMMENDED_MODELS, AIModelManager
    return handle_ai_models(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        ai_model_manager_cls=AIModelManager,
        recommended_models=RECOMMENDED_MODELS,
    )


def cmd_preset(args):
    """Handle preset subcommand."""
    return handle_preset(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        json_module=json_module,
        preset_manager_cls=PresetManager,
    )


def cmd_focus_mode(args):
    """Handle focus-mode subcommand."""
    return handle_focus_mode(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        focus_mode_cls=FocusMode,
    )


def cmd_security_audit(_args):
    """Handle security-audit subcommand."""
    return handle_security_audit(
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        port_auditor_cls=PortAuditor,
    )


def cmd_profile(args):
    """Handle profile subcommand."""
    return handle_profile(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        profile_manager_cls=ProfileManager,
    )


def cmd_health_history(args):
    """Handle health-history subcommand."""
    timeline_cls = HealthTimeline
    if timeline_cls is _DEFAULT_HEALTH_TIMELINE_CLASS:
        from utils import health_timeline as health_timeline_module

        timeline_cls = health_timeline_module.HealthTimeline
    timeline = timeline_cls()

    if args.action == "show":
        summary = timeline.get_summary(hours=24)
        if _json_output:
            _output_json({"summary": summary})
        else:
            _print("═══════════════════════════════════════════")
            _print("   Health Timeline (24h Summary)")
            _print("═══════════════════════════════════════════")
            if not summary:
                _print("\n(no metrics recorded)")
                _print("Run 'loofi health-history record' to capture a snapshot.")
            else:
                metric_labels = {
                    "cpu_temp": ("CPU Temp", "C"),
                    "ram_usage": ("RAM Usage", "%"),
                    "disk_usage": ("Disk Usage", "%"),
                    "load_avg": ("Load Avg", ""),
                }
                for metric_type, data in summary.items():
                    label, unit = metric_labels.get(metric_type, (metric_type, ""))
                    _print(f"\n  {label}:")
                    _print(f"      Min: {data['min']:.1f}{unit}")
                    _print(f"      Max: {data['max']:.1f}{unit}")
                    _print(f"      Avg: {data['avg']:.1f}{unit}")
                    _print(f"      Samples: {data['count']}")
        return 0

    elif args.action == "record":
        result = timeline.record_snapshot()
        if _json_output:
            _output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            _print(f"{icon} {result.message}")
        return 0 if result.success else 1

    elif args.action == "export":
        if not args.path:
            _print("❌ Export path required")
            return 1
        # Determine format from extension
        if args.path.lower().endswith(".csv"):
            format_type = "csv"
        else:
            format_type = "json"
        result = timeline.export_metrics(args.path, format=format_type)
        if _json_output:
            _output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            _print(f"{icon} {result.message}")
        return 0 if result.success else 1

    elif args.action == "prune":
        result = timeline.prune_old_data()
        if _json_output:
            _output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            _print(f"{icon} {result.message}")
        return 0 if result.success else 1

    return 1


# ==================== v15.0 Nebula CLI commands ====================


def cmd_tuner(args):
    """Handle tuner subcommand."""
    from utils.auto_tuner import AutoTuner

    if args.action == "analyze":
        workload = AutoTuner.detect_workload()
        rec = AutoTuner.recommend(workload)
        current = AutoTuner.get_current_settings()
        if _json_output:
            _output_json(
                {
                    "workload": vars(workload),
                    "recommendation": vars(rec),
                    "current_settings": current,
                }
            )
        else:
            _print("═══════════════════════════════════════════")
            _print("   Performance Auto-Tuner")
            _print("═══════════════════════════════════════════")
            _print(f"\n  Workload Detected: {workload.name}")
            _print(f"  CPU: {workload.cpu_percent:.1f}%  Memory: {workload.memory_percent:.1f}%")
            _print(f"  Description: {workload.description}")
            _print("\n  Current Settings:")
            for k, v in current.items():
                _print(f"    {k}: {v}")
            _print("\n  Recommendations:")
            _print(f"    Governor: {rec.governor}")
            _print(f"    Swappiness: {rec.swappiness}")
            _print(f"    I/O Scheduler: {rec.io_scheduler}")
            _print(f"    THP: {rec.thp}")
            _print(f"    Reason: {rec.reason}")
        return 0

    elif args.action == "apply":
        rec = AutoTuner.recommend()
        _print(f"🔄 Applying: governor={rec.governor}, swappiness={rec.swappiness}")
        success = run_operation(AutoTuner.apply_recommendation(rec))
        if success:
            run_operation(AutoTuner.apply_swappiness(rec.swappiness))
        return 0 if success else 1

    elif args.action == "history":
        history = AutoTuner.get_tuning_history()
        if _json_output:
            _output_json([vars(h) for h in history])
        else:
            _print("═══════════════════════════════════════════")
            _print("   Tuning History")
            _print("═══════════════════════════════════════════")
            if not history:
                _print("\n  (no tuning history)")
            else:
                import time

                for entry in history[-10:]:
                    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.timestamp))
                    _print(f"\n  {ts} — {entry.workload} (applied: {entry.applied})")
        return 0

    return 1


def cmd_snapshot(args):
    """Handle snapshot subcommand."""
    from utils.snapshot_manager import SnapshotManager
    return handle_snapshot(args, _json_output, _output_json, _print, run_operation, SnapshotManager)


def cmd_logs(args):
    """Handle logs subcommand."""
    from utils.smart_logs import SmartLogViewer

    if args.action == "show":
        entries = SmartLogViewer.get_logs(
            unit=args.unit,
            priority=args.priority,
            since=args.since,
            lines=args.lines,
        )
        if _json_output:
            _output_json([vars(e) for e in entries])
        else:
            for e in entries:
                marker = "⚠️ " if e.pattern_match else ""
                _print(f"  {e.timestamp} [{e.priority_label}] {e.unit}: {marker}{e.message[:120]}")
                if e.pattern_match:
                    _print(f"    ↳ {e.pattern_match}")
        return 0

    elif args.action == "errors":
        summary = SmartLogViewer.get_error_summary(since=args.since or "24h ago")
        if _json_output:
            _output_json(vars(summary))
        else:
            _print("═══════════════════════════════════════════")
            _print("   Log Error Summary")
            _print("═══════════════════════════════════════════")
            _print(f"  Total entries: {summary.total_entries}")
            _print(f"  Critical: {summary.critical_count}")
            _print(f"  Errors: {summary.error_count}")
            _print(f"  Warnings: {summary.warning_count}")
            if summary.top_units:
                _print("\n  Top Units:")
                for unit, count in summary.top_units:
                    _print(f"    {unit}: {count}")
            if summary.detected_patterns:
                _print("\n  Detected Patterns:")
                for pattern, count in summary.detected_patterns:
                    _print(f"    {pattern}: {count}")
        return 0

    elif args.action == "export":
        if not args.path:
            _print("❌ Export path required")
            return 1
        entries = SmartLogViewer.get_logs(since=args.since, lines=args.lines or 500)
        fmt = "json" if args.path.endswith(".json") else "text"
        success = SmartLogViewer.export_logs(entries, args.path, format=fmt)
        icon = "✅" if success else "❌"
        _print(f"{icon} Exported {len(entries)} entries to {args.path}")
        return 0 if success else 1

    return 1


# ===== v16.0 Horizon commands =====


def cmd_service(args):
    """Handle service subcommand."""
    return handle_service(args, _json_output, _output_json, _print, run_operation, ServiceExplorer)


def cmd_package(args):
    """Handle package subcommand."""
    return handle_package(args, _json_output, _output_json, _print, run_operation, PackageExplorer)


def cmd_firewall(args):
    """Handle firewall subcommand."""
    return handle_firewall(args, _json_output, _output_json, _print, run_operation, FirewallManager)


# ==================== v17.0 Atlas ====================


def cmd_bluetooth(args):
    """Handle bluetooth subcommand."""
    return handle_bluetooth(args, _json_output, _output_json, _print, BluetoothManager)


# ==================== v18.0 Sentinel ====================


def cmd_agent(args):
    """Handle agent subcommand."""
    from core.agents import AgentRegistry, AgentScheduler, AgentPlanner, AgentNotifier
    return handle_agent(args, _json_output, _output_json, _print, run_operation, AgentRegistry, AgentScheduler, AgentPlanner, AgentNotifier)


def cmd_storage(args):
    """Handle storage subcommand."""
    return handle_storage(args, _json_output, _output_json, _print, StorageManager)


def cmd_audit_log(args):
    """Show recent audit log entries."""
    from services.security import AuditLogger
    return handle_audit_log(args, _json_output, _output_json, _print, AuditLogger)


# ==================== v37.0 Pinnacle ====================


def cmd_updates(args):
    """Handle smart updates subcommand."""
    from utils.update_manager import UpdateManager
    return handle_updates(args, _json_output, _output_json, _print, run_operation, UpdateManager)


def cmd_extension(args):
    """Handle extension management subcommand."""
    from utils.extension_manager import ExtensionManager
    return handle_extension(args, _json_output, _output_json, _print, run_operation, ExtensionManager)


def cmd_flatpak_manage(args):
    """Handle Flatpak management subcommand."""
    from services.software import FlatpakManager
    return handle_flatpak_manage(args, _json_output, _output_json, _print, run_operation, FlatpakManager)


def cmd_boot(args):
    """Handle boot configuration subcommand."""
    from utils.boot_config import BootConfigManager
    return handle_boot(args, _json_output, _output_json, _print, run_operation, BootConfigManager)


def cmd_display(args):
    """Handle display configuration subcommand."""
    from services.desktop import WaylandDisplayManager

    if args.action == "list":
        displays = WaylandDisplayManager.get_displays()
        if _json_output:
            _output_json(
                [
                    {
                        "name": d.name,
                        "resolution": d.resolution,
                        "scale": d.scale,
                        "refresh": d.refresh_rate,
                        "primary": d.primary,
                    }
                    for d in displays
                ]
            )
        else:
            for d in displays:
                primary = " ★" if d.primary else ""
                _print(f"  {d.name}: {d.resolution} @{d.scale}x {d.refresh_rate}Hz{primary}")
        return 0

    elif args.action == "session":
        info = WaylandDisplayManager.get_session_info()
        if _json_output:
            _output_json(info)
        else:
            for k, v in info.items():
                _print(f"  {k}: {v}")
        return 0

    elif args.action == "fractional-on":
        return 0 if run_operation(WaylandDisplayManager.enable_fractional_scaling()) else 1

    elif args.action == "fractional-off":
        return 0 if run_operation(WaylandDisplayManager.disable_fractional_scaling()) else 1

    return 1


def cmd_backup(args):
    """Handle backup subcommand."""
    from utils.backup_wizard import BackupWizard

    if args.action == "detect":
        tool = BackupWizard.detect_backup_tool()
        available = BackupWizard.get_available_tools()
        if _json_output:
            _output_json({"active": tool, "available": available})
        else:
            _print(f"  Active tool: {tool}")
            _print(f"  Available: {', '.join(available)}")
        return 0

    elif args.action == "create":
        desc = getattr(args, "description", None) or "CLI backup"
        tool = getattr(args, "tool", None)
        return 0 if run_operation(BackupWizard.create_snapshot(tool=tool, description=desc)) else 1

    elif args.action == "list":
        tool = getattr(args, "tool", None)
        snapshots = BackupWizard.list_snapshots(tool=tool)
        if _json_output:
            _output_json(
                [
                    {
                        "id": s.id,
                        "date": s.date,
                        "description": s.description,
                        "tool": s.tool,
                    }
                    for s in snapshots
                ]
            )
        else:
            if not snapshots:
                _print("  No snapshots found.")
            for s in snapshots:
                _print(f"  [{s.tool}] {s.id}: {s.description} ({s.date})")
        return 0

    elif args.action == "restore":
        snap_id = getattr(args, "snapshot_id", None)
        if not snap_id:
            _print("❌ Snapshot ID required")
            return 1
        tool = getattr(args, "tool", None)
        return 0 if run_operation(BackupWizard.restore_snapshot(snap_id, tool=tool)) else 1

    elif args.action == "delete":
        snap_id = getattr(args, "snapshot_id", None)
        if not snap_id:
            _print("❌ Snapshot ID required")
            return 1
        tool = getattr(args, "tool", None)
        return 0 if run_operation(BackupWizard.delete_snapshot(snap_id, tool=tool)) else 1

    elif args.action == "status":
        status = BackupWizard.get_backup_status()
        if _json_output:
            _output_json(status)
        else:
            for k, v in status.items():
                _print(f"  {k}: {v}")
        return 0

    return 1


def main(argv: Optional[List[str]] = None):
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="loofi",
        description=f'Loofi Fedora Tweaks v{__version__} "{__version_codename__}" - System management CLI',
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f'{__version__} "{__version_codename__}"',
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format (for scripting)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Operation timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show commands without executing them (v35.0)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Info command
    subparsers.add_parser("info", help="Show system information")

    # Health command
    health_parser = subparsers.add_parser("health", help="System health check overview")
    health_subparsers = health_parser.add_subparsers(dest="health_action", help="Health timeline commands")
    health_snapshot_parser = health_subparsers.add_parser("snapshot", help="Record a My Fedora Today health snapshot")
    health_snapshot_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")
    health_timeline_parser = health_subparsers.add_parser("timeline", help="Show persisted health snapshots")
    health_timeline_parser.add_argument("--limit", type=int, default=10, help="Snapshot limit")

    maintenance_parser = subparsers.add_parser("maintenance", help="Daily maintenance health commands")
    maintenance_subparsers = maintenance_parser.add_subparsers(dest="maintenance_action", help="Maintenance commands")
    maintenance_today_parser = maintenance_subparsers.add_parser("today", help="Show My Fedora Today maintenance state")
    maintenance_today_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")
    maintenance_today_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # Disk command
    disk_parser = subparsers.add_parser("disk", help="Disk usage information")
    disk_parser.add_argument("--details", action="store_true", help="Show large directories")

    # Process monitor command
    proc_parser = subparsers.add_parser("processes", help="Show top processes")
    proc_parser.add_argument("-n", "--count", type=int, default=10, help="Number of processes to show")
    proc_parser.add_argument("--sort", choices=["cpu", "memory"], default="cpu", help="Sort by")

    # Temperature command
    subparsers.add_parser("temperature", help="Show temperature readings")

    # Network monitor command
    netmon_parser = subparsers.add_parser("netmon", help="Network interface monitoring")
    netmon_parser.add_argument("--connections", action="store_true", help="Show active connections")

    # Cleanup subcommand
    cleanup_parser = subparsers.add_parser("cleanup", help="System cleanup operations")
    cleanup_parser.add_argument(
        "action",
        choices=["all", "dnf", "journal", "trim", "autoremove", "rpmdb"],
        default="all",
        nargs="?",
        help="Cleanup action to perform",
    )
    cleanup_parser.add_argument("--days", type=int, default=14, help="Days to keep journal")

    # Tweak subcommand
    tweak_parser = subparsers.add_parser("tweak", help="Hardware tweaks (power, audio, battery)")
    tweak_parser.add_argument("action", choices=["power", "audio", "battery", "status"], help="Tweak action")
    tweak_parser.add_argument(
        "--profile",
        choices=["performance", "balanced", "power-saver"],
        default="balanced",
        help="Power profile",
    )
    tweak_parser.add_argument("--limit", type=int, default=80, help="Battery limit (50-100)")

    # Advanced subcommand
    adv_parser = subparsers.add_parser("advanced", help="Advanced optimizations")
    adv_parser.add_argument(
        "action",
        choices=["dnf-tweaks", "bbr", "gamemode", "swappiness"],
        help="Optimization action",
    )
    adv_parser.add_argument("--value", type=int, default=10, help="Value for swappiness")

    # Network subcommand
    net_parser = subparsers.add_parser("network", help="Network configuration")
    net_parser.add_argument("action", choices=["dns"], help="Network action")
    net_parser.add_argument(
        "--provider",
        choices=["cloudflare", "google", "quad9", "opendns"],
        default="cloudflare",
        help="DNS provider",
    )

    # v10.0 new commands
    subparsers.add_parser("doctor", help="Check system dependencies and diagnostics")
    subparsers.add_parser("hardware", help="Show detected hardware profile")

    # Plugin management
    plugin_parser = subparsers.add_parser("plugins", help="Manage plugins")
    plugin_parser.add_argument("action", choices=["list", "enable", "disable"], help="Plugin action")
    plugin_parser.add_argument("name", nargs="?", help="Plugin name for enable/disable")

    # v26.0 - Plugin marketplace
    marketplace_parser = subparsers.add_parser("plugin-marketplace", help="Plugin marketplace operations")
    marketplace_parser.add_argument(
        "action",
        choices=[
            "search",
            "install",
            "uninstall",
            "update",
            "info",
            "list-installed",
            "reviews",
            "review-submit",
            "rating",
        ],
        help="Marketplace action",
    )
    marketplace_parser.add_argument("plugin", nargs="?", help="Plugin name or ID")
    marketplace_parser.add_argument("--category", help="Filter by category")
    marketplace_parser.add_argument("--query", help="Search query")
    marketplace_parser.add_argument("--limit", type=int, default=20, help="Review fetch limit (for reviews)")
    marketplace_parser.add_argument("--offset", type=int, default=0, help="Review fetch offset (for reviews)")
    marketplace_parser.add_argument("--reviewer", help="Reviewer name (for review-submit)")
    marketplace_parser.add_argument("--rating", type=int, help="Rating 1-5 (for review-submit)")
    marketplace_parser.add_argument("--title", help="Review title (for review-submit)")
    marketplace_parser.add_argument("--comment", help="Review comment (for review-submit)")
    marketplace_parser.add_argument(
        "--accept-permissions",
        action="store_true",
        help="Auto-accept permissions (non-interactive)",
    )

    # Support bundle
    subparsers.add_parser("support-bundle", help="Export support bundle ZIP")

    state_parser = subparsers.add_parser("state", help="Inspect, back up, and recover Loofi state")
    state_subparsers = state_parser.add_subparsers(dest="state_action")
    state_subparsers.add_parser("doctor", help="Validate state without changing it")
    state_backup_parser = state_subparsers.add_parser("backup", help="Create a privacy-safe state archive")
    state_backup_parser.add_argument("--output", required=True, help="Destination ZIP path")
    state_restore_parser = state_subparsers.add_parser("restore", help="Plan or explicitly apply a restore")
    state_restore_subparsers = state_restore_parser.add_subparsers(dest="restore_action")
    state_restore_plan = state_restore_subparsers.add_parser("plan", help="Validate and preview an archive")
    state_restore_plan.add_argument("archive")
    state_restore_apply = state_restore_subparsers.add_parser("apply", help="Apply an existing restore plan")
    state_restore_apply.add_argument("archive")
    state_restore_apply.add_argument("--plan-id", required=True)

    readiness_parser = subparsers.add_parser("readiness", help="Run release readiness diagnostics")
    readiness_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")
    readiness_parser.add_argument("--advanced", action="store_true", help="Show raw command and status details")
    readiness_subparsers = readiness_parser.add_subparsers(dest="readiness_action", help="Readiness action commands")

    readiness_actions_parser = readiness_subparsers.add_parser("actions", help="List safe readiness action candidates")
    readiness_actions_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")

    readiness_plan_parser = readiness_subparsers.add_parser("plan", help="Show guided release upgrade plan")
    readiness_plan_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")

    readiness_explain_parser = readiness_subparsers.add_parser("explain", help="Explain one readiness check")
    readiness_explain_parser.add_argument("action_id", help="Readiness check ID")
    readiness_explain_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")

    readiness_export_parser = readiness_subparsers.add_parser("export", help="Export readiness support bundle")
    readiness_export_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")
    readiness_export_parser.add_argument("--path", help="Output JSON path")

    readiness_info_parser = readiness_subparsers.add_parser("action-info", help="Show one readiness action candidate")
    readiness_info_parser.add_argument("action_id", help="Readiness action ID")
    readiness_info_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")

    readiness_preview_parser = readiness_subparsers.add_parser("action-preview", help="Preview one readiness action")
    readiness_preview_parser.add_argument("action_id", help="Readiness action ID")
    readiness_preview_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")

    readiness_run_parser = readiness_subparsers.add_parser("action-run", help="Run a confirmed readiness action")
    readiness_run_parser.add_argument("action_id", help="Readiness action ID")
    readiness_run_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")
    readiness_run_parser.add_argument("--confirm", action="store_true", help="Confirm the selected mutating action")

    readiness_verify_parser = readiness_subparsers.add_parser("action-verify", help="Verify one readiness action")
    readiness_verify_parser.add_argument("action_id", help="Readiness action ID")
    readiness_verify_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")

    action_center_parser = subparsers.add_parser("action-center", help="Plan, verify, and inspect guided maintenance actions")
    action_center_parser.add_argument(
        "action",
        choices=["list", "preview", "history", "recommendations", "plan", "show", "apply", "verify"],
        nargs="?",
        default="list",
        help="Action Center command",
    )
    action_center_parser.add_argument("action_id", nargs="?", help="Action ID, plan ID, or run ID for the selected command")
    action_center_parser.add_argument("--target", choices=["44", "45-preview"], default="44", help="Readiness target profile")
    action_center_parser.add_argument("--limit", type=int, default=25, help="History entry limit")
    action_center_parser.add_argument("--service", help="Exact failed systemd unit for restart-failed-service")
    action_center_parser.add_argument("--confirm", action="store_true", help="Explicitly confirm application of the reviewed plan")
    action_center_parser.add_argument(
        "--accept-no-rollback",
        action="store_true",
        help="Explicitly accept a medium/high-risk action without supported rollback",
    )

    fedora44_parser = subparsers.add_parser("fedora44-readiness", help="Compatibility alias for 'readiness --target 44'")
    fedora44_parser.add_argument("--advanced", action="store_true", help="Show raw command and status details")

    # ==================== v11.5 / v12.0 subparsers ====================

    # VM management
    vm_parser = subparsers.add_parser("vm", help="Virtual machine management")
    vm_parser.add_argument("action", choices=["list", "status", "start", "stop"], help="VM action")
    vm_parser.add_argument("name", nargs="?", help="VM name (for status/start/stop)")

    # VFIO GPU passthrough
    vfio_parser = subparsers.add_parser("vfio", help="GPU passthrough assistant")
    vfio_parser.add_argument("action", choices=["check", "gpus", "plan"], help="VFIO action")

    # Mesh networking
    mesh_parser = subparsers.add_parser("mesh", help="Loofi Link mesh networking")
    mesh_parser.add_argument("action", choices=["discover", "status"], help="Mesh action")

    # State Teleport
    teleport_parser = subparsers.add_parser("teleport", help="State Teleport workspace capture/restore")
    teleport_parser.add_argument("action", choices=["capture", "list", "restore"], help="Teleport action")
    teleport_parser.add_argument("--path", help="Workspace path for capture")
    teleport_parser.add_argument("--target", default="unknown", help="Target device name")
    teleport_parser.add_argument("package_id", nargs="?", help="Package ID for restore")

    # AI Models
    ai_models_parser = subparsers.add_parser("ai-models", help="AI model management")
    ai_models_parser.add_argument("action", choices=["list", "recommend"], help="AI models action")

    # Preset management
    preset_parser = subparsers.add_parser("preset", help="Manage system presets")
    preset_parser.add_argument("action", choices=["list", "apply", "export"], help="Preset action")
    preset_parser.add_argument("name", nargs="?", help="Preset name (for apply/export)")
    preset_parser.add_argument("path", nargs="?", help="Export path (for export)")

    # Focus mode
    focus_parser = subparsers.add_parser("focus-mode", help="Focus mode distraction blocking")
    focus_parser.add_argument("action", choices=["on", "off", "status"], help="Focus mode action")
    focus_parser.add_argument("--profile", default="default", help="Profile to use (default: default)")

    # Security audit
    subparsers.add_parser("security-audit", help="Run security audit and show score")

    # v13.0 Nexus Update - Profile management
    profile_parser = subparsers.add_parser("profile", help="System profile management")
    profile_parser.add_argument(
        "action",
        choices=[
            "list",
            "apply",
            "create",
            "delete",
            "export",
            "import",
            "export-all",
            "import-all",
        ],
        help="Profile action",
    )
    profile_parser.add_argument("name", nargs="?", help="Profile name (for apply/create/delete/export)")
    profile_parser.add_argument("path", nargs="?", help="Import/export file path")
    profile_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing custom profiles on import",
    )
    profile_parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Skip snapshot creation when applying profiles",
    )
    profile_parser.add_argument(
        "--include-builtins",
        action="store_true",
        help="Include built-in profiles in export-all bundle",
    )

    # v13.0 Nexus Update - Health history
    health_history_parser = subparsers.add_parser("health-history", help="Health timeline metrics")
    health_history_parser.add_argument(
        "action",
        choices=["show", "record", "export", "prune"],
        help="Health history action",
    )
    health_history_parser.add_argument("path", nargs="?", help="Export path (for export)")

    # ==================== v15.0 Nebula subparsers ====================

    # Performance auto-tuner
    tuner_parser = subparsers.add_parser("tuner", help="Performance auto-tuner")
    tuner_parser.add_argument("action", choices=["analyze", "apply", "history"], help="Tuner action")

    # Snapshot management
    snapshot_parser = subparsers.add_parser("snapshot", help="System snapshot management")
    snapshot_parser.add_argument(
        "action",
        choices=["list", "create", "delete", "backends"],
        help="Snapshot action",
    )
    snapshot_parser.add_argument("--label", help="Snapshot label (for create)")
    snapshot_parser.add_argument("snapshot_id", nargs="?", help="Snapshot ID (for delete)")

    # Smart log viewer
    logs_parser = subparsers.add_parser("logs", help="Smart log viewer with pattern detection")
    logs_parser.add_argument("action", choices=["show", "errors", "export"], help="Logs action")
    logs_parser.add_argument("--unit", help="Filter by systemd unit")
    logs_parser.add_argument("--priority", type=int, help="Max priority level (0-7)")
    logs_parser.add_argument("--since", help="Time filter (e.g. '1h ago', '2024-01-01')")
    logs_parser.add_argument("--lines", type=int, default=100, help="Number of lines")
    logs_parser.add_argument("path", nargs="?", help="Export path (for export)")

    # ==================== v16.0 Horizon subparsers ====================

    # Service management
    service_parser = subparsers.add_parser("service", help="Systemd service management")
    service_parser.add_argument(
        "action",
        choices=[
            "list",
            "start",
            "stop",
            "restart",
            "enable",
            "disable",
            "mask",
            "unmask",
            "logs",
            "status",
        ],
        help="Service action",
    )
    service_parser.add_argument("name", nargs="?", help="Service name")
    service_parser.add_argument("--user", action="store_true", help="User scope (default: system)")
    service_parser.add_argument(
        "--filter",
        choices=["active", "inactive", "failed"],
        help="Filter by state (for list)",
    )
    service_parser.add_argument("--search", help="Search filter (for list)")
    service_parser.add_argument("--lines", type=int, default=50, help="Log lines (for logs)")

    # Package management
    package_parser = subparsers.add_parser("package", help="Package search and management")
    package_parser.add_argument(
        "action",
        choices=["search", "install", "remove", "list", "recent"],
        help="Package action",
    )
    package_parser.add_argument("name", nargs="?", help="Package name (for install/remove)")
    package_parser.add_argument("--query", help="Search query (for search)")
    package_parser.add_argument("--source", choices=["dnf", "flatpak", "all"], help="Package source filter")
    package_parser.add_argument("--search", help="Filter installed packages")
    package_parser.add_argument("--days", type=int, default=30, help="Days for recent")

    # Firewall management
    firewall_parser = subparsers.add_parser("firewall", help="Firewall management")
    firewall_parser.add_argument(
        "action",
        choices=["status", "ports", "open-port", "close-port", "services", "zones"],
        help="Firewall action",
    )
    firewall_parser.add_argument("spec", nargs="?", help="Port spec (e.g. 8080/tcp)")

    # v17.0 Atlas - Bluetooth management
    bt_parser = subparsers.add_parser("bluetooth", help="Bluetooth management")
    bt_parser.add_argument(
        "action",
        choices=[
            "status",
            "devices",
            "scan",
            "power-on",
            "power-off",
            "connect",
            "disconnect",
            "pair",
            "unpair",
            "trust",
        ],
        help="Bluetooth action",
    )
    bt_parser.add_argument("address", nargs="?", help="Device MAC address")
    bt_parser.add_argument("--paired", action="store_true", help="Show paired only")
    bt_parser.add_argument("--timeout", type=int, default=10, help="Scan timeout")

    # v17.0 Atlas - Storage management
    storage_parser = subparsers.add_parser("storage", help="Storage & disk management")
    storage_parser.add_argument(
        "action",
        choices=["disks", "mounts", "smart", "usage", "trim"],
        help="Storage action",
    )
    storage_parser.add_argument("device", nargs="?", help="Device path (e.g. /dev/sda)")

    update_parser = subparsers.add_parser("self-update", help="Check/download verified Loofi updates")
    update_parser.add_argument(
        "action", choices=["check", "run"], default="run", nargs="?", help="Self-update action: check for updates or run the update"
    )
    update_parser.add_argument(
        "--channel", choices=["auto", "rpm", "flatpak", "appimage"], default="auto", help="Update channel to use (default: auto-detect)"
    )
    update_parser.add_argument("--download-dir", default="~/.cache/loofi-fedora-tweaks/updates", help="Directory to download updates to")
    update_parser.add_argument("--timeout", type=int, default=30, help="Download timeout in seconds (default: 30)")
    update_parser.add_argument("--no-cache", action="store_true", help="Skip cached update packages")
    update_parser.add_argument("--checksum", default="", help="Expected SHA256 checksum of the update package")
    update_parser.add_argument("--signature-path", help="Path to GPG signature file for verification")
    update_parser.add_argument("--public-key-path", help="Path to GPG public key for signature verification")

    # v18.0 Sentinel - Agent management
    agent_parser = subparsers.add_parser("agent", help="Autonomous system agent management")
    agent_parser.add_argument(
        "action",
        choices=[
            "list",
            "status",
            "enable",
            "disable",
            "run",
            "create",
            "remove",
            "logs",
            "templates",
            "notify",
        ],
        help="Agent action",
    )
    agent_parser.add_argument(
        "agent_id",
        nargs="?",
        help="Agent ID (for enable/disable/run/remove/logs/notify)",
    )
    agent_parser.add_argument("--goal", help="Natural language goal (for create)")
    agent_parser.add_argument("--webhook", help="Webhook URL for notifications (for notify)")
    agent_parser.add_argument(
        "--min-severity",
        help="Minimum severity to notify: info/low/medium/high/critical",
    )

    # v35.0 Fortress - Audit log viewer
    audit_parser = subparsers.add_parser("audit-log", help="View recent audit log entries")
    audit_parser.add_argument("--count", type=int, default=20, help="Number of entries to show (default: 20)")

    # v37.0 Pinnacle - Smart Updates
    updates_parser = subparsers.add_parser("updates", help="Smart update management")
    updates_parser.add_argument(
        "action",
        choices=["check", "conflicts", "schedule", "rollback", "history"],
        help="Update action to perform",
    )
    updates_parser.add_argument("--time", default="02:00", help="Schedule time (HH:MM, default: 02:00)")

    # v37.0 Pinnacle - Extensions
    ext_parser = subparsers.add_parser("extension", help="Desktop extension management")
    ext_parser.add_argument(
        "action",
        choices=["list", "install", "remove", "enable", "disable"],
        help="Extension action",
    )
    ext_parser.add_argument("--uuid", help="Extension UUID for install/remove/enable/disable")

    # v37.0 Pinnacle - Flatpak Manager
    flatpak_parser = subparsers.add_parser("flatpak-manage", help="Flatpak management tools")
    flatpak_parser.add_argument(
        "action",
        choices=["sizes", "permissions", "orphans", "cleanup"],
        help="Flatpak action",
    )

    # v37.0 Pinnacle - Boot Configuration
    boot_parser = subparsers.add_parser("boot", help="Boot configuration management")
    boot_parser.add_argument("action", choices=["config", "kernels", "timeout", "apply"], help="Boot action")
    boot_parser.add_argument("--seconds", type=int, help="Timeout in seconds (for timeout action)")

    # v37.0 Pinnacle - Display
    display_parser = subparsers.add_parser("display", help="Display and Wayland configuration")
    display_parser.add_argument(
        "action",
        choices=["list", "session", "fractional-on", "fractional-off"],
        help="Display action",
    )

    # v37.0 Pinnacle - Backup
    backup_parser = subparsers.add_parser("backup", help="Snapshot backup management")
    backup_parser.add_argument(
        "action",
        choices=["detect", "create", "list", "restore", "delete", "status"],
        help="Backup action",
    )
    backup_parser.add_argument("--tool", help="Backup tool (timeshift/snapper)")
    backup_parser.add_argument("--description", help="Snapshot description (for create)")
    backup_parser.add_argument("--snapshot-id", help="Snapshot ID (for restore/delete)")

    args = parser.parse_args(argv)

    # Set JSON mode
    globals()["_json_output"] = getattr(args, "json", False)

    # Set operation timeout from --timeout flag
    globals()["_operation_timeout"] = getattr(args, "timeout", 300)

    # Set dry-run mode from --dry-run flag
    globals()["_dry_run"] = getattr(args, "dry_run", False)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "info": cmd_info,
        "health": cmd_health,
        "maintenance": cmd_maintenance,
        "disk": cmd_disk,
        "processes": cmd_processes,
        "temperature": cmd_temperature,
        "netmon": cmd_netmon,
        "cleanup": cmd_cleanup,
        "tweak": cmd_tweak,
        "advanced": cmd_advanced,
        "network": cmd_network,
        "doctor": cmd_doctor,
        "hardware": cmd_hardware,
        "plugins": cmd_plugins,
        "plugin-marketplace": cmd_plugin_marketplace,
        "support-bundle": cmd_support_bundle,
        "state": cmd_state,
        "readiness": cmd_readiness,
        "action-center": cmd_action_center,
        "fedora44-readiness": cmd_fedora44_readiness,
        # v11.5 / v12.0
        "vm": cmd_vm,
        "vfio": cmd_vfio,
        "mesh": cmd_mesh,
        "teleport": cmd_teleport,
        "ai-models": cmd_ai_models,
        # New commands
        "preset": cmd_preset,
        "focus-mode": cmd_focus_mode,
        "security-audit": cmd_security_audit,
        # v13.0 Nexus Update
        "profile": cmd_profile,
        "health-history": cmd_health_history,
        # v15.0 Nebula
        "tuner": cmd_tuner,
        "snapshot": cmd_snapshot,
        "logs": cmd_logs,
        # v16.0 Horizon
        "service": cmd_service,
        "package": cmd_package,
        "firewall": cmd_firewall,
        # v17.0 Atlas
        "bluetooth": cmd_bluetooth,
        "storage": cmd_storage,
        # v18.0 Sentinel
        "agent": cmd_agent,
        "self-update": cmd_self_update,
        # v35.0 Fortress
        "audit-log": cmd_audit_log,
        # v37.0 Pinnacle
        "updates": cmd_updates,
        "extension": cmd_extension,
        "flatpak-manage": cmd_flatpak_manage,
        "boot": cmd_boot,
        "display": cmd_display,
        "backup": cmd_backup,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
