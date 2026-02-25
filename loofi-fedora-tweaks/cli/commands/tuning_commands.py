"""
Tuning/system command handlers: tuner, snapshot, backup, boot.
"""


def handle_tuner(args, json_output, output_json, print_fn, run_operation, auto_tuner_cls):
    """Handle tuner subcommand."""
    if args.action == "analyze":
        workload = auto_tuner_cls.detect_workload()
        rec = auto_tuner_cls.recommend(workload)
        current = auto_tuner_cls.get_current_settings()
        if json_output:
            output_json(
                {
                    "workload": vars(workload),
                    "recommendation": vars(rec),
                    "current_settings": current,
                }
            )
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Performance Auto-Tuner")
            print_fn("═══════════════════════════════════════════")
            print_fn(f"\n  Workload Detected: {workload.name}")
            print_fn(f"  CPU: {workload.cpu_percent:.1f}%  Memory: {workload.memory_percent:.1f}%")
            print_fn(f"  Description: {workload.description}")
            print_fn("\n  Current Settings:")
            for k, v in current.items():
                print_fn(f"    {k}: {v}")
            print_fn("\n  Recommendations:")
            print_fn(f"    Governor: {rec.governor}")
            print_fn(f"    Swappiness: {rec.swappiness}")
            print_fn(f"    I/O Scheduler: {rec.io_scheduler}")
            print_fn(f"    THP: {rec.thp}")
            print_fn(f"    Reason: {rec.reason}")
        return 0

    elif args.action == "apply":
        rec = auto_tuner_cls.recommend()
        print_fn(f"🔄 Applying: governor={rec.governor}, swappiness={rec.swappiness}")
        success = run_operation(auto_tuner_cls.apply_recommendation(rec))
        if success:
            run_operation(auto_tuner_cls.apply_swappiness(rec.swappiness))
        return 0 if success else 1

    elif args.action == "history":
        history = auto_tuner_cls.get_tuning_history()
        if json_output:
            output_json([vars(h) for h in history])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Tuning History")
            print_fn("═══════════════════════════════════════════")
            if not history:
                print_fn("\n  (no tuning history)")
            else:
                import time

                for entry in history[-10:]:
                    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.timestamp))
                    print_fn(f"\n  {ts} — {entry.workload} (applied: {entry.applied})")
        return 0

    return 1


def handle_snapshot(args, json_output, output_json, print_fn, run_operation, snapshot_manager_cls):
    """Handle snapshot subcommand."""
    if args.action == "list":
        snapshots = snapshot_manager_cls.list_snapshots()
        if json_output:
            output_json([vars(s) for s in snapshots])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   System Snapshots")
            print_fn("═══════════════════════════════════════════")
            if not snapshots:
                print_fn("\n  (no snapshots found)")
            else:
                import time

                for s in snapshots[:20]:
                    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(s.timestamp)) if s.timestamp else "unknown"
                    print_fn(f"  [{s.backend}] {s.id}: {s.label or '(no label)'} — {ts}")
        return 0

    elif args.action == "create":
        label = args.label or "manual-snapshot"
        print_fn(f"🔄 Creating snapshot: {label}")
        success = run_operation(snapshot_manager_cls.create_snapshot(label))
        return 0 if success else 1

    elif args.action == "delete":
        if not args.snapshot_id:
            print_fn("❌ Snapshot ID required")
            return 1
        success = run_operation(snapshot_manager_cls.delete_snapshot(args.snapshot_id))
        return 0 if success else 1

    elif args.action == "backends":
        backends = snapshot_manager_cls.detect_backends()
        if json_output:
            output_json([vars(b) for b in backends])
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Snapshot Backends")
            print_fn("═══════════════════════════════════════════")
            for b in backends:
                status = "✅" if b.available else "❌"
                print_fn(f"  {status} {b.name}: {b.version if b.available else 'not installed'}")
        return 0

    return 1


def handle_backup(args, json_output, output_json, print_fn, run_operation, backup_wizard_cls):
    """Handle backup subcommand."""
    if args.action == "detect":
        tool = backup_wizard_cls.detect_backup_tool()
        available = backup_wizard_cls.get_available_tools()
        if json_output:
            output_json({"active": tool, "available": available})
        else:
            print_fn(f"  Active tool: {tool}")
            print_fn(f"  Available: {', '.join(available)}")
        return 0

    elif args.action == "create":
        desc = getattr(args, "description", None) or "CLI backup"
        tool = getattr(args, "tool", None)
        return 0 if run_operation(backup_wizard_cls.create_snapshot(tool=tool, description=desc)) else 1

    elif args.action == "list":
        tool = getattr(args, "tool", None)
        snapshots = backup_wizard_cls.list_snapshots(tool=tool)
        if json_output:
            output_json(
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
                print_fn("  No snapshots found.")
            for s in snapshots:
                print_fn(f"  [{s.tool}] {s.id}: {s.description} ({s.date})")
        return 0

    elif args.action == "restore":
        snap_id = getattr(args, "snapshot_id", None)
        if not snap_id:
            print_fn("❌ Snapshot ID required")
            return 1
        tool = getattr(args, "tool", None)
        return 0 if run_operation(backup_wizard_cls.restore_snapshot(snap_id, tool=tool)) else 1

    elif args.action == "delete":
        snap_id = getattr(args, "snapshot_id", None)
        if not snap_id:
            print_fn("❌ Snapshot ID required")
            return 1
        tool = getattr(args, "tool", None)
        return 0 if run_operation(backup_wizard_cls.delete_snapshot(snap_id, tool=tool)) else 1

    elif args.action == "status":
        status = backup_wizard_cls.get_backup_status()
        if json_output:
            output_json(status)
        else:
            for k, v in status.items():
                print_fn(f"  {k}: {v}")
        return 0

    return 1


def handle_boot(args, json_output, output_json, print_fn, run_operation, boot_config_manager_cls):
    """Handle boot configuration subcommand."""
    if args.action == "config":
        config = boot_config_manager_cls.get_grub_config()
        if json_output:
            output_json(
                {
                    "default": config.default_entry,
                    "timeout": config.timeout,
                    "theme": config.theme,
                    "cmdline": config.cmdline_linux,
                }
            )
        else:
            print_fn(f"  Default: {config.default_entry}")
            print_fn(f"  Timeout: {config.timeout}s")
            print_fn(f"  Theme: {config.theme or 'none'}")
            print_fn(f"  Cmdline: {config.cmdline_linux}")
        return 0

    elif args.action == "kernels":
        kernels = boot_config_manager_cls.list_kernels()
        if json_output:
            output_json([{"title": k.title, "version": k.version, "default": k.is_default} for k in kernels])
        else:
            for k in kernels:
                marker = "→ " if k.is_default else "  "
                print_fn(f"  {marker}{k.title} ({k.version})")
        return 0

    elif args.action == "timeout":
        seconds = getattr(args, "seconds", None)
        if seconds is None:
            print_fn("❌ --seconds required")
            return 1
        return 0 if run_operation(boot_config_manager_cls.set_timeout(seconds)) else 1

    elif args.action == "apply":
        return 0 if run_operation(boot_config_manager_cls.apply_grub_changes()) else 1

    return 1
