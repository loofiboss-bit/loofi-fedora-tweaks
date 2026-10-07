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
    if args.action == "diagnose":
        from services.software.update_diagnostics import UpdateDiagnosticsService

        outcome = UpdateDiagnosticsService().diagnose(args.source, run_id=getattr(args, "run_id", None))
        payload = outcome.session.to_dict()
        payload["persistence_reason_code"] = outcome.persistence_reason_code
        if json_output:
            output_json(payload)
        else:
            print_fn(f"Update diagnosis: {args.source} ({outcome.session.state})")
            for result in outcome.session.source_results:
                print_fn(f"  {result.source_id}: {result.state} — {result.message or result.reason_code}")
                print_fn(f"    Collected: {result.completed_at}")
                for key, value in result.to_dict()["facts"].items():
                    print_fn(f"    {key}: {value}")
            for finding in outcome.session.findings:
                print_fn(f"  {finding.title}: {finding.summary}")
                step = finding.next_step
                print_fn(f"    Next step: {step.guidance or step.target_id or step.reason_code}")
        return 0 if outcome.session.state == "completed" else 1

    if args.action == "check":
        from dataclasses import asdict
        from services.software.update_overview import UpdateOverviewService

        snapshot = UpdateOverviewService().check()
        success = all(source.status in {"up_to_date", "available"} for source in snapshot.sources)
        if json_output:
            output_json({"success": success, **asdict(snapshot)})
        else:
            for source in snapshot.sources:
                print_fn(f"  {source.source}: {source.status}" + (f" ({source.error_code})" if source.error_code else ""))
                for item in source.items:
                    print_fn(f"    {item.name}: {item.old_version} → {item.version}")
        return 0 if success else 1

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
