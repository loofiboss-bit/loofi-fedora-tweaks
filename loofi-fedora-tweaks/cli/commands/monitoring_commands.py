"""
Monitoring command handlers: health-history, logs.
"""


def handle_health_history(args, json_output, output_json, print_fn, health_timeline_cls):
    """Handle health-history subcommand."""
    timeline = health_timeline_cls()

    if args.action == "show":
        summary = timeline.get_summary(hours=24)
        if json_output:
            output_json({"summary": summary})
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Health Timeline (24h Summary)")
            print_fn("═══════════════════════════════════════════")
            if not summary:
                print_fn("\n(no metrics recorded)")
                print_fn("Run 'loofi health-history record' to capture a snapshot.")
            else:
                metric_labels = {
                    "cpu_temp": ("CPU Temp", "C"),
                    "ram_usage": ("RAM Usage", "%"),
                    "disk_usage": ("Disk Usage", "%"),
                    "load_avg": ("Load Avg", ""),
                }
                for metric_type, data in summary.items():
                    label, unit = metric_labels.get(metric_type, (metric_type, ""))
                    print_fn(f"\n  {label}:")
                    print_fn(f"      Min: {data['min']:.1f}{unit}")
                    print_fn(f"      Max: {data['max']:.1f}{unit}")
                    print_fn(f"      Avg: {data['avg']:.1f}{unit}")
                    print_fn(f"      Samples: {data['count']}")
        return 0

    elif args.action == "record":
        result = timeline.record_snapshot()
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    elif args.action == "export":
        if not args.path:
            print_fn("❌ Export path required")
            return 1
        # Determine format from extension
        if args.path.lower().endswith(".csv"):
            format_type = "csv"
        else:
            format_type = "json"
        result = timeline.export_metrics(args.path, format=format_type)
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    elif args.action == "prune":
        result = timeline.prune_old_data()
        if json_output:
            output_json(
                {
                    "success": result.success,
                    "message": result.message,
                    "data": result.data,
                }
            )
        else:
            icon = "✅" if result.success else "❌"
            print_fn(f"{icon} {result.message}")
        return 0 if result.success else 1

    return 1


def handle_logs(args, json_output, output_json, print_fn, smart_log_viewer_cls):
    """Handle logs subcommand."""
    if args.action == "show":
        entries = smart_log_viewer_cls.get_logs(
            unit=args.unit,
            priority=args.priority,
            since=args.since,
            lines=args.lines,
        )
        if json_output:
            output_json([vars(e) for e in entries])
        else:
            for e in entries:
                marker = "⚠️ " if e.pattern_match else ""
                print_fn(f"  {e.timestamp} [{e.priority_label}] {e.unit}: {marker}{e.message[:120]}")
                if e.pattern_match:
                    print_fn(f"    ↳ {e.pattern_match}")
        return 0

    elif args.action == "errors":
        summary = smart_log_viewer_cls.get_error_summary(since=args.since or "24h ago")
        if json_output:
            output_json(vars(summary))
        else:
            print_fn("═══════════════════════════════════════════")
            print_fn("   Log Error Summary")
            print_fn("═══════════════════════════════════════════")
            print_fn(f"  Total entries: {summary.total_entries}")
            print_fn(f"  Critical: {summary.critical_count}")
            print_fn(f"  Errors: {summary.error_count}")
            print_fn(f"  Warnings: {summary.warning_count}")
            if summary.top_units:
                print_fn("\n  Top Units:")
                for unit, count in summary.top_units:
                    print_fn(f"    {unit}: {count}")
            if summary.detected_patterns:
                print_fn("\n  Detected Patterns:")
                for pattern, count in summary.detected_patterns:
                    print_fn(f"    {pattern}: {count}")
        return 0

    elif args.action == "export":
        if not args.path:
            print_fn("❌ Export path required")
            return 1
        entries = smart_log_viewer_cls.get_logs(since=args.since, lines=args.lines or 500)
        fmt = "json" if args.path.endswith(".json") else "text"
        success = smart_log_viewer_cls.export_logs(entries, args.path, format=fmt)
        icon = "✅" if success else "❌"
        print_fn(f"{icon} Exported {len(entries)} entries to {args.path}")
        return 0 if success else 1

    return 1
