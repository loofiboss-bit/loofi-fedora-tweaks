"""Health timeline CLI presentation."""

from __future__ import annotations

from typing import Any, Callable


def handle_health_history(
    args: Any,
    *,
    json_output: bool,
    output_json: Callable[[Any], Any],
    print_fn: Callable[[Any], Any],
    timeline_cls: type[Any],
) -> Any:
    """Handle health-history subcommand."""
    timeline = timeline_cls()

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
