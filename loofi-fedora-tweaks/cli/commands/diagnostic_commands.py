"""
Diagnostic command handlers: doctor, support-bundle, audit-log.
"""

from services.system.system import cached_which


def handle_doctor(json_output, output_json, print_fn, which_fn=None):
    """Run system diagnostics and check dependencies."""
    if which_fn is None:
        which_fn = cached_which

    critical_tools = ["dnf", "pkexec", "systemctl", "flatpak"]
    optional_tools = [
        "fwupdmgr",
        "timeshift",
        "nbfc",
        "firejail",
        "ollama",
        "distrobox",
        "podman",
    ]

    all_ok = True

    if json_output:
        data = {"critical": {}, "optional": {}}
        for tool in critical_tools:
            data["critical"][tool] = which_fn(tool) is not None
        for tool in optional_tools:
            data["optional"][tool] = which_fn(tool) is not None
        data["all_critical_ok"] = all(data["critical"].values())
        all_ok = data["all_critical_ok"]
        output_json(data)
    else:
        print_fn("═══════════════════════════════════════════")
        print_fn("   System Doctor")
        print_fn("═══════════════════════════════════════════")

        print_fn("\nCritical Tools:")
        all_ok = True
        for tool in critical_tools:
            found = which_fn(tool) is not None
            icon = "✅" if found else "❌"
            print_fn(f"  {icon} {tool}")
            if not found:
                all_ok = False

        print_fn("\nOptional Tools:")
        for tool in optional_tools:
            found = which_fn(tool) is not None
            icon = "✅" if found else "⚪"
            print_fn(f"  {icon} {tool}")

        if all_ok:
            print_fn("\n🟢 All critical dependencies found.")
        else:
            print_fn("\n🔴 Some critical tools are missing. Install them for full functionality.")

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
