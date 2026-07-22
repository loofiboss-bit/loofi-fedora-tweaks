"""
Loofi CLI - Command-line interface for Loofi Fedora Tweaks.
Enables headless operation and scripting.
"""

import typing

import json as json_module
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from core.executor.operations import AdvancedOps, NetworkOps, TweakOps
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from cli.parser import build_parser
from cli.commands.readiness_commands import (
    cmd_action_center,
    cmd_fedora44_readiness,
    cmd_readiness,
    cmd_state,
)
from cli.commands.readiness_commands import _cmd_readiness_action as _cmd_readiness_action  # noqa: F401
from cli.commands.readiness_commands import _print_action_result as _print_action_result  # noqa: F401
from cli.commands.readiness_commands import _print_readiness_report as _print_readiness_report  # noqa: F401
from cli.commands.readiness_commands import _print_release_plan as _print_release_plan  # noqa: F401

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
from core.plugins.legacy import LegacyExtensionService  # noqa: E402
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


def _print(text: typing.Any) -> typing.Any:
    """Print text (suppressed in JSON mode)."""
    if not _json_output:
        print(text)


def _output_json(data: typing.Any) -> typing.Any:
    """Output JSON data and exit."""
    print(json_module.dumps(data, indent=2, default=str))


def run_operation(op_result: typing.Any, timeout: typing.Any = None) -> typing.Any:
    """Execute an operation tuple (cmd, args, description).

    Args:
        op_result: Tuple of (cmd, args, description) from utils operations.
        timeout: Override timeout in seconds. Defaults to global _operation_timeout (300s).
    """
    cmd, args, desc = op_result
    full_cmd = [cmd] + args

    from core.execution_policy import blocked_execution_message, execution_allowed

    if not _dry_run and not execution_allowed(cmd, args):
        message = blocked_execution_message(cmd, args)
        plan = _create_action_center_plan("legacy-cli-manual-review", {})
        if _json_output:
            _output_json(
                {
                    "schema_version": 3,
                    "error": "action_center_required",
                    "message": message,
                    "auto_apply": False,
                    "plan": plan.to_dict(),
                }
            )
        else:
            _print(f"Blocked: {message}")
            _print(f"Plan {plan.plan_id}: {plan.action_id} [{plan.state}]")
        return False

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


def _create_action_center_plan(action_id: str, parameters: Dict[str, Any]) -> typing.Any:
    from core.actions import ActionCenterOrchestrator

    return ActionCenterOrchestrator().plan(action_id, parameters)


def _emit_legacy_plans(plans: typing.Any) -> int:
    payload = {
        "schema_version": 3,
        "plans": [plan.to_dict() for plan in plans],
        "auto_apply": False,
    }
    if _json_output:
        _output_json(payload)
    else:
        for plan in plans:
            _print(f"Plan {plan.plan_id}: {plan.action_id} [{plan.state}]")
            _print(f"  {plan.policy_decision.explanation}")
            if plan.state != "blocked":
                _print(f"  Apply separately: loofi --cli action-center apply {plan.plan_id} --confirm")
    return 0 if all(plan.state != "blocked" for plan in plans) else 1


def cmd_cleanup(args: typing.Any) -> typing.Any:
    """Create independent cleanup plans; never auto-apply legacy commands."""
    mapping = {
        "dnf": ("dnf-clean-all", {}),
        "journal": ("vacuum-journal", {"days": args.days}),
        "trim": ("fstrim-all", {}),
        "autoremove": ("autoremove-packages", {}),
    }
    if args.action == "rpmdb":
        _print("RPM database repair is manual-only under Troubleshooting.")
        return 1
    actions = ["dnf", "journal", "trim"] if args.action == "all" else [args.action]
    plans = [_create_action_center_plan(*mapping[action]) for action in actions]
    return _emit_legacy_plans(plans)


def cmd_tweak(args: typing.Any) -> typing.Any:
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


def cmd_advanced(args: typing.Any) -> typing.Any:
    """Handle advanced subcommand."""
    return handle_advanced(args=args, print_fn=_print, advanced_ops_cls=AdvancedOps)


def cmd_network(args: typing.Any) -> typing.Any:
    """Handle network subcommand."""
    return handle_network(args=args, print_fn=_print, network_ops_cls=NetworkOps)


def cmd_info(_args: typing.Any) -> typing.Any:
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


def cmd_health(args: typing.Any) -> typing.Any:
    """Show system health overview."""
    action = getattr(args, "health_action", None)
    if action == "snapshot":
        from core.observability import MaintenanceTrendAnalyzer, ObservabilityService

        service = ObservabilityService()
        snapshot = service.collect_snapshot(target=getattr(args, "target", FEDORA_RELEASE_POLICY.stable_target), source="cli")
        timeline = service.snapshots.load()
        payload: dict[str, typing.Any] = {
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


def cmd_maintenance(args: typing.Any) -> typing.Any:
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
    action_items = ActionCenterService().candidates_from_readiness(getattr(args, "target", FEDORA_RELEASE_POLICY.stable_target))
    snapshot = HealthSnapshot.from_daily_maintenance(
        report, action_center_items=action_items, fedora_target=getattr(args, "target", FEDORA_RELEASE_POLICY.stable_target)
    )
    timeline = [*HealthTimelineStore().load(), snapshot]
    payload: dict[str, typing.Any] = {
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


def cmd_disk(args: typing.Any) -> typing.Any:
    """Show disk usage information."""
    return handle_disk(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        disk_manager_cls=DiskManager,
    )


def cmd_processes(args: typing.Any) -> typing.Any:
    """Show top processes."""
    return handle_processes(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        process_manager_cls=ProcessManager,
    )


def cmd_temperature(_args: typing.Any) -> typing.Any:
    """Show temperature readings."""
    return handle_temperature(
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        temperature_manager_cls=TemperatureManager,
    )


def cmd_netmon(args: typing.Any) -> typing.Any:
    """Show network interface stats."""
    return handle_netmon(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        network_monitor_cls=NetworkMonitor,
    )


def cmd_doctor(_args: typing.Any) -> typing.Any:
    """Run system diagnostics and check dependencies."""
    return handle_doctor(_json_output, _output_json, _print, which_fn=cached_which)


def cmd_hardware(_args: typing.Any) -> typing.Any:
    """Show detected hardware profile."""
    from services.hardware.hardware_profiles import detect_hardware_profile

    return handle_hardware(_json_output, _output_json, _print, detect_hardware_profile)


def cmd_self_update(args: typing.Any) -> typing.Any:
    """Check and run self-update flow."""
    return handle_self_update(args, _json_output, _output_json, _print, SystemManager, UpdateChecker, __version__)


def cmd_plugins(args: typing.Any) -> typing.Any:
    """Inventory quarantined legacy extensions without executing them."""
    return handle_plugins(
        args,
        _json_output,
        _output_json,
        _print,
        LegacyExtensionService,
    )


def cmd_plugin_marketplace(args: typing.Any) -> typing.Any:
    """Return the stable v18 retirement response for legacy callers."""
    del args
    payload = {
        "schema_version": 3,
        "error": "feature_retired",
        "feature": "plugin-marketplace",
        "message": "External Marketplace distribution was retired in Haven.",
        "alternative": "Use built-in features or local profiles.",
    }
    if _json_output:
        _output_json(payload)
    else:
        _print(payload["message"])
        _print(payload["alternative"])
    return 2


def cmd_api_key(args: typing.Any) -> typing.Any:
    """Rotate, revoke, or inspect the local Web API credential."""
    from utils.auth import AuthManager

    if args.action == "rotate":
        api_key = AuthManager.generate_api_key()
        payload = {
            "schema_version": 3,
            "status": "rotated",
            "api_key": api_key,
            "warning": "This key is shown once. Store it in a password manager.",
        }
    elif args.action == "revoke":
        AuthManager.revoke_api_key()
        payload = {"schema_version": 3, "status": "revoked"}
    else:
        payload = {
            "schema_version": 3,
            "status": "active" if AuthManager.has_api_key() else "not_configured",
        }
    if _json_output:
        _output_json(payload)
    else:
        _print(payload["status"])
        if "api_key" in payload:
            _print(payload["api_key"])
            _print(payload["warning"])
    return 0


def cmd_support_bundle(_args: typing.Any) -> typing.Any:
    """Export support bundle ZIP."""
    return handle_support_bundle(_json_output, _output_json, _print, JournalManager)


# ==================== v11.5 / v12.0 COMMANDS ====================


def cmd_vm(args: typing.Any) -> typing.Any:
    """Handle VM subcommand."""
    from services.virtualization import VMManager

    return handle_vm(args, _json_output, _output_json, _print, VMManager)


def cmd_vfio(args: typing.Any) -> typing.Any:
    """Handle VFIO GPU passthrough subcommand."""
    from services.virtualization import VFIOAssistant

    return handle_vfio(args, _json_output, _output_json, _print, VFIOAssistant)


def cmd_mesh(args: typing.Any) -> typing.Any:
    """Handle mesh networking subcommand."""
    from services.network import MeshDiscovery

    return handle_mesh(args, _json_output, _output_json, _print, MeshDiscovery)


def cmd_teleport(args: typing.Any) -> typing.Any:
    """Handle state teleport subcommand."""
    from services.storage import StateTeleportManager

    return handle_teleport(args, _json_output, _output_json, _print, StateTeleportManager)


def cmd_ai_models(args: typing.Any) -> typing.Any:
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


def cmd_preset(args: typing.Any) -> typing.Any:
    """Handle preset subcommand."""
    return handle_preset(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        json_module=json_module,
        preset_manager_cls=PresetManager,
    )


def cmd_focus_mode(args: typing.Any) -> typing.Any:
    """Handle focus-mode subcommand."""
    return handle_focus_mode(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        focus_mode_cls=FocusMode,
    )


def cmd_security_audit(_args: typing.Any) -> typing.Any:
    """Handle security-audit subcommand."""
    return handle_security_audit(
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        port_auditor_cls=PortAuditor,
    )


def cmd_profile(args: typing.Any) -> typing.Any:
    """Handle profile subcommand."""
    return handle_profile(
        args=args,
        json_output=_json_output,
        output_json=_output_json,
        print_fn=_print,
        profile_manager_cls=ProfileManager,
    )


def cmd_health_history(args: typing.Any) -> typing.Any:
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


def cmd_tuner(args: typing.Any) -> typing.Any:
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


def cmd_snapshot(args: typing.Any) -> typing.Any:
    """Handle snapshot subcommand."""
    if args.action == "create":
        backend = getattr(args, "backend", None)
        if backend not in {"timeshift", "snapper"}:
            _print("Snapshot creation requires --backend timeshift|snapper; raw Btrfs remains manual-only.")
            return 1
        plan = _create_action_center_plan(
            "create-recovery-point",
            {"backend": backend, "description": args.label or "manual-snapshot"},
        )
        return _emit_legacy_plans([plan])
    from utils.snapshot_manager import SnapshotManager

    return handle_snapshot(args, _json_output, _output_json, _print, run_operation, SnapshotManager)


def cmd_logs(args: typing.Any) -> typing.Any:
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


def cmd_service(args: typing.Any) -> typing.Any:
    """Handle service subcommand."""
    return handle_service(args, _json_output, _output_json, _print, run_operation, ServiceExplorer)


def cmd_package(args: typing.Any) -> typing.Any:
    """Handle package subcommand."""
    if args.action in {"install", "remove"}:
        if not args.name:
            _print("Package name required")
            return 1
        source = {"dnf": "fedora", "flatpak": "flatpak"}.get(getattr(args, "source", None) or "dnf")
        if source is None:
            _print("Install/remove requires an explicit --source dnf|flatpak.")
            return 1
        action_id = "install-application" if args.action == "install" else "remove-application"
        plan = _create_action_center_plan(action_id, {"source": source, "package_id": args.name})
        return _emit_legacy_plans([plan])
    return handle_package(args, _json_output, _output_json, _print, run_operation, PackageExplorer)


def cmd_firewall(args: typing.Any) -> typing.Any:
    """Handle firewall subcommand."""
    return handle_firewall(args, _json_output, _output_json, _print, run_operation, FirewallManager)


# ==================== v17.0 Atlas ====================


def cmd_bluetooth(args: typing.Any) -> typing.Any:
    """Handle bluetooth subcommand."""
    return handle_bluetooth(args, _json_output, _output_json, _print, BluetoothManager)


# ==================== v18.0 Sentinel ====================


def cmd_agent(args: typing.Any) -> typing.Any:
    """Handle agent subcommand."""
    from core.agents import AgentRegistry, AgentScheduler, AgentPlanner, AgentNotifier

    return handle_agent(args, _json_output, _output_json, _print, run_operation, AgentRegistry, AgentScheduler, AgentPlanner, AgentNotifier)


def cmd_storage(args: typing.Any) -> typing.Any:
    """Handle storage subcommand."""
    return handle_storage(args, _json_output, _output_json, _print, StorageManager)


def cmd_audit_log(args: typing.Any) -> typing.Any:
    """Show recent audit log entries."""
    from services.security import AuditLogger

    return handle_audit_log(args, _json_output, _output_json, _print, AuditLogger)


# ==================== v37.0 Pinnacle ====================


def cmd_updates(args: typing.Any) -> typing.Any:
    """Handle smart updates subcommand."""
    from utils.update_manager import UpdateManager

    return handle_updates(args, _json_output, _output_json, _print, run_operation, UpdateManager)


def cmd_extension(args: typing.Any) -> typing.Any:
    """Handle extension management subcommand."""
    from utils.extension_manager import ExtensionManager

    return handle_extension(args, _json_output, _output_json, _print, run_operation, ExtensionManager)


def cmd_flatpak_manage(args: typing.Any) -> typing.Any:
    """Handle Flatpak management subcommand."""
    from services.software import FlatpakManager

    return handle_flatpak_manage(args, _json_output, _output_json, _print, run_operation, FlatpakManager)


def cmd_boot(args: typing.Any) -> typing.Any:
    """Handle boot configuration subcommand."""
    from utils.boot_config import BootConfigManager

    return handle_boot(args, _json_output, _output_json, _print, run_operation, BootConfigManager)


def cmd_display(args: typing.Any) -> typing.Any:
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


def cmd_backup(args: typing.Any) -> typing.Any:
    """Handle backup subcommand."""
    from utils.backup_wizard import BackupWizard

    if args.action == "detect":
        active_tool = BackupWizard.detect_backup_tool()
        available = BackupWizard.get_available_tools()
        if _json_output:
            _output_json({"active": active_tool, "available": available})
        else:
            _print(f"  Active tool: {active_tool}")
            _print(f"  Available: {', '.join(available)}")
        return 0

    elif args.action == "create":
        desc = getattr(args, "description", None) or "CLI backup"
        selected_tool = getattr(args, "tool", None)
        if selected_tool not in {"timeshift", "snapper"}:
            _print("Backup creation requires --tool timeshift|snapper.")
            return 1
        plan = _create_action_center_plan("create-recovery-point", {"backend": selected_tool, "description": desc})
        return _emit_legacy_plans([plan])

    elif args.action == "list":
        list_tool = getattr(args, "tool", None)
        snapshots = BackupWizard.list_snapshots(tool=list_tool)
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
        restore_tool = getattr(args, "tool", None)
        return 0 if run_operation(BackupWizard.restore_snapshot(snap_id, tool=restore_tool)) else 1

    elif args.action == "delete":
        snap_id = getattr(args, "snapshot_id", None)
        if not snap_id:
            _print("❌ Snapshot ID required")
            return 1
        delete_tool = getattr(args, "tool", None)
        return 0 if run_operation(BackupWizard.delete_snapshot(snap_id, tool=delete_tool)) else 1

    elif args.action == "status":
        status = BackupWizard.get_backup_status()
        if _json_output:
            _output_json(status)
        else:
            for k, v in status.items():
                _print(f"  {k}: {v}")
        return 0

    return 1


def _command_handlers() -> typing.Any:
    """Return the command-to-domain-handler map."""
    return {
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
        "api-key": cmd_api_key,
        "support-bundle": cmd_support_bundle,
        "state": cmd_state,
        "readiness": cmd_readiness,
        "action-center": cmd_action_center,
        "fedora44-readiness": cmd_fedora44_readiness,
        "vm": cmd_vm,
        "vfio": cmd_vfio,
        "mesh": cmd_mesh,
        "teleport": cmd_teleport,
        "ai-models": cmd_ai_models,
        "preset": cmd_preset,
        "focus-mode": cmd_focus_mode,
        "security-audit": cmd_security_audit,
        "profile": cmd_profile,
        "health-history": cmd_health_history,
        "tuner": cmd_tuner,
        "snapshot": cmd_snapshot,
        "logs": cmd_logs,
        "service": cmd_service,
        "package": cmd_package,
        "firewall": cmd_firewall,
        "bluetooth": cmd_bluetooth,
        "storage": cmd_storage,
        "agent": cmd_agent,
        "self-update": cmd_self_update,
        "audit-log": cmd_audit_log,
        "updates": cmd_updates,
        "extension": cmd_extension,
        "flatpak-manage": cmd_flatpak_manage,
        "boot": cmd_boot,
        "display": cmd_display,
        "backup": cmd_backup,
    }


def main(argv: Optional[List[str]] = None) -> typing.Any:
    """Parse CLI arguments and dispatch one domain handler."""
    parser = build_parser()
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

    handler = _command_handlers().get(args.command)
    if handler:
        return handler(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
