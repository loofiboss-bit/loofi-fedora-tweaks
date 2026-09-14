"""
Diagnostic command handlers: doctor, support-bundle, audit-log.
"""

from __future__ import annotations

from typing import Any, Callable

from services.system.system import SystemManager, cached_which


def handle_doctor(
    json_output: bool,
    output_json: Callable[[dict[str, Any]], None],
    print_fn: Callable[[str], None],
    which_fn: Callable[[str], str | None] | None = None,
) -> int:
    """Run read-only diagnostics without inventing host capabilities.

    Platform detection is part of the doctor result.  If the profile cannot
    establish Fedora identity or a supported deployment backend, the result
    is unhealthy and exposes ``unknown`` values rather than silently
    reporting a Traditional Workstation.
    """
    if which_fn is None:
        which_fn = cached_which

    from core.platform.profile import (
        DeploymentBackend,
        DesktopEnvironment,
        PlatformProfile,
        SessionType,
    )

    profile = None
    profile_error = False
    try:
        profile = PlatformProfile.detect(
            reboot_pending_checker=SystemManager._check_reboot_pending,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        profile_error = True

    if profile is None:
        fedora_ver: int | str | None = None
        backend = DeploymentBackend.UNKNOWN.value
        desktop = DesktopEnvironment.UNKNOWN.value
        session = SessionType.UNKNOWN.value
        reboot_pending: bool | None = None
        reboot_status = "unknown"
        support_status = "unknown"
        platform_ok = False
    else:
        fedora_ver = profile.fedora_version
        backend = profile.deployment_backend.value
        desktop = profile.desktop.value
        session = profile.session_type.value
        reboot_pending = profile.reboot_pending
        reboot_status = profile.reboot_status.value
        support_status = profile.support_status
        platform_ok = (
            profile.is_fedora
            and support_status in {"supported", "preview"}
            and profile.deployment_backend is not DeploymentBackend.UNKNOWN
        )

    # Flatpak and fwupd are optional integrations.  The deployment backend's
    # package tool is the only backend-specific critical dependency.
    critical_tools = ["pkexec", "systemctl"]
    backend_tool = {
        DeploymentBackend.DNF5.value: "dnf5",
        DeploymentBackend.RPM_OSTREE.value: "rpm-ostree",
        DeploymentBackend.BOOTC.value: "bootc",
    }.get(backend)
    if backend_tool is not None:
        critical_tools.append(backend_tool)
    optional_tools = ["flatpak", "fwupdmgr", "timeshift", "snapper"]

    def tool_present(tool: str) -> bool:
        try:
            return which_fn(tool) is not None
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            return False

    critical_status = {tool: tool_present(tool) for tool in critical_tools}
    # Fedora 43/44 may expose the DNF5 stack through the legacy ``dnf``
    # compatibility command.  Keep the profile's canonical backend label but
    # accept either executable as evidence that the package path is present.
    if backend == DeploymentBackend.DNF5.value and not critical_status["dnf5"]:
        critical_status["dnf5"] = tool_present("dnf")
    optional_status = {tool: tool_present(tool) for tool in optional_tools}
    polkit_active = critical_status.get("pkexec", False)
    all_ok = platform_ok and not profile_error and all(critical_status.values())

    if json_output:
        data = {
            "fedora_version": fedora_ver,
            "support_status": support_status,
            "deployment_backend": backend,
            "desktop": desktop,
            "session_type": session,
            "reboot_pending": reboot_pending,
            "reboot_status": reboot_status,
            "platform_ok": platform_ok,
            "profile_error": profile_error,
            "polkit_active": polkit_active,
            "critical": critical_status,
            "optional": optional_status,
        }
        data["all_critical_ok"] = all_ok
        output_json(data)
    else:
        print_fn("═══════════════════════════════════════════")
        print_fn("   System Doctor - Fedora Maintenance Core")
        print_fn("═══════════════════════════════════════════")
        print_fn(f"Fedora Version:      {fedora_ver if fedora_ver is not None else 'Unknown'}")
        print_fn(f"Support Status:      {support_status}")
        print_fn(f"Deployment Backend:  {backend}")
        print_fn(f"Desktop Environment: {desktop} ({session})")
        print_fn(f"Reboot Status:       {reboot_status}")
        print_fn(f"Polkit Service:      {'✅ Active' if polkit_active else '❌ Inactive / Not running'}")

        print_fn("\nCritical Tools:")
        for tool, found in critical_status.items():
            icon = "✅" if found else "❌"
            print_fn(f"  {icon} {tool}")

        print_fn("\nOptional Tools:")
        for tool, found in optional_status.items():
            icon = "✅" if found else "⚪"
            print_fn(f"  {icon} {tool}")

        if all_ok:
            print_fn("\n🟢 All critical dependencies and Polkit are healthy.")
        else:
            print_fn("\n🔴 Platform or critical dependencies are unknown or unavailable.")

    return 0 if all_ok else 1


def handle_support_bundle(json_output, output_json, print_fn, journal_manager_cls):
    """Export support bundle ZIP."""
    result = journal_manager_cls.export_support_bundle()
    if json_output:
        output_json({"success": result.success, "message": result.message, "data": result.data})
    else:
        print_fn(f"{'✅' if result.success else '❌'} {result.message}")
    return 0 if result.success else 1


def handle_audit_log(args, json_output, output_json, print_fn, audit_logger_cls):
    """Show recent audit log entries."""
    audit = audit_logger_cls()
    count = getattr(args, "count", 20)
    entries = audit.get_recent(count)

    if json_output:
        output_json({"entries": entries, "count": len(entries), "log_path": str(audit.log_path)})
        return 0

    if not entries:
        print_fn("No audit log entries found.")
        print_fn(f"Log path: {audit.log_path}")
        return 0

    print_fn(f"📋 Recent Audit Log ({len(entries)} entries)")
    print_fn(f"   Log: {audit.log_path}")
    print_fn("─" * 72)

    for entry in entries:
        ts = entry.get("ts", "?")[:19].replace("T", " ")
        action = entry.get("action", "?")
        exit_code = entry.get("exit_code")
        dry_run = entry.get("dry_run", False)

        status = "DRY" if dry_run else ("✅" if exit_code == 0 else f"❌ ({exit_code})")
        print_fn(f"  {ts}  {action:30s}  {status}")

    return 0
