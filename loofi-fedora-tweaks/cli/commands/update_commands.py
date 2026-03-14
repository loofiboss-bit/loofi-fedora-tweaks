"""
Update command handlers: self-update, updates.
"""

import os


def handle_self_update(args, json_output, output_json, print_fn, system_manager_cls, update_checker_cls, version):
    """Check and run self-update flow."""
    package_manager = system_manager_cls.get_package_manager()
    preference = update_checker_cls.resolve_artifact_preference(package_manager, args.channel)
    use_cache = not args.no_cache

    if args.action == "check":
        info = update_checker_cls.check_for_updates(timeout=args.timeout, use_cache=use_cache)
        if json_output:
            output_json(
                {
                    "success": info is not None,
                    "stage": "check",
                    "update_available": bool(info and info.is_newer),
                    "offline": bool(info and info.offline),
                    "source": info.source if info else "network",
                    "current_version": info.current_version if info else version,
                    "latest_version": info.latest_version if info else None,
                    "selected_asset": info.selected_asset.name if info and info.selected_asset else None,
                }
            )
            return 0 if info is not None else 1

        if info is None:
            print_fn("❌ Update check failed")
            return 1
        if info.is_newer:
            print_fn(f"✅ Update available: {info.current_version} -> {info.latest_version}")
            if info.selected_asset:
                print_fn(f"📦 Selected asset: {info.selected_asset.name}")
        else:
            print_fn("✅ No update available")
        return 0

    result = update_checker_cls.run_auto_update(
        artifact_preference=preference,
        target_dir=os.path.expanduser(args.download_dir),
        timeout=args.timeout,
        use_cache=use_cache,
        expected_sha256=args.checksum,
        signature_path=args.signature_path,
        public_key_path=args.public_key_path,
    )

    if json_output:
        output_json(
            {
                "success": result.success,
                "stage": result.stage,
                "error": result.error,
                "offline": result.offline,
                "source": result.source,
                "selected_asset": result.selected_asset.name if result.selected_asset else None,
                "downloaded_file": result.download.file_path if result.download else None,
                "download_ok": result.download.ok if result.download else None,
                "verify_ok": result.verify.ok if result.verify else None,
            }
        )
    else:
        if result.success:
            print_fn("✅ Update package downloaded and verified")
            if result.download and result.download.file_path:
                print_fn(f"📁 File: {result.download.file_path}")
        else:
            print_fn(f"❌ Self-update failed at stage '{result.stage}': {result.error}")

    return 0 if result.success else 1


def handle_updates(args, json_output, output_json, print_fn, run_operation, update_manager_cls):
    """Handle smart updates subcommand."""
    if args.action == "check":
        updates = update_manager_cls.check_updates()
        if json_output:
            output_json(
                [
                    {
                        "name": u.name,
                        "old": u.old_version,
                        "new": u.new_version,
                        "source": u.source,
                    }
                    for u in updates
                ]
            )
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Available Updates")
            print_fn("═══════════════════════════════════════════")
            if not updates:
                print_fn("  System is up to date.")
            for u in updates:
                print_fn(f"  {u.name}: {u.old_version} → {u.new_version} ({u.source})")
        return 0

    elif args.action == "conflicts":
        conflicts = update_manager_cls.preview_conflicts()
        if json_output:
            output_json(
                [
                    {
                        "package": c.package,
                        "type": c.conflict_type,
                        "desc": c.description,
                    }
                    for c in conflicts
                ]
            )
        else:
            if not conflicts:
                print_fn("  No conflicts detected.")
            for c in conflicts:
                print_fn(f"  ⚠ {c.package}: {c.conflict_type} — {c.description}")
        return 0

    elif args.action == "schedule":
        time_str = getattr(args, "time", "02:00") or "02:00"
        scheduled = update_manager_cls.schedule_update(time_str)
        cmds = update_manager_cls.get_schedule_commands(scheduled)
        for binary, cmd_args, desc in cmds:
            run_operation((binary, cmd_args, desc))
        return 0

    elif args.action == "rollback":
        return 0 if run_operation(update_manager_cls.rollback_last()) else 1

    elif args.action == "history":
        history = update_manager_cls.get_update_history()
        if json_output:
            output_json(
                [
                    {
                        "date": h.date,
                        "name": h.name,
                        "version": h.new_version,
                        "source": h.source,
                    }
                    for h in history
                ]
            )
        else:
            for h in history:
                print_fn(f"  {h.date}: {h.name} → {h.new_version} ({h.source})")
        return 0

    return 1
