"""Read-only compatibility commands for retired external extensions."""

from __future__ import annotations

from dataclasses import asdict


def handle_plugins(args, json_output, output_json, print_fn, legacy_service_cls):
    """List legacy files or return a stable retirement error."""
    if args.action == "list":
        extensions = [asdict(item) for item in legacy_service_cls.list_extensions()]
        payload = {
            "schema_version": 3,
            "execution": "disabled",
            "extensions": extensions,
        }
        if json_output:
            output_json(payload)
        else:
            print_fn("Legacy extensions (execution disabled)")
            if not extensions:
                print_fn("No legacy extension directories found.")
            for extension in extensions:
                print_fn(f"- {extension['name']}: {extension['path']}")
        return 0

    payload = {
        "schema_version": 3,
        "error": "feature_retired",
        "feature": "external-plugins",
        "requested_action": args.action,
        "name": getattr(args, "name", None),
        "message": "External Python extension execution was retired in Haven.",
        "alternative": "Use built-in features or local profiles.",
    }
    if json_output:
        output_json(payload)
    else:
        print_fn(payload["message"])
        print_fn(payload["alternative"])
    return 2
