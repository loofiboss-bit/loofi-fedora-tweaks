"""Read-only CLI presentation for local portable Fedora configurations."""
from __future__ import annotations

from typing import Any, Callable


def handle_setup(
    args: Any,
    *,
    json_output: bool,
    output_json: Callable[[Any], Any],
    print_fn: Callable[[str], Any],
    error_fn: Callable[[str], Any],
) -> int:
    """List, show, and compare saved setup data without authorizing changes."""
    from core.tasks.setup_configurations import SetupLibrary, SetupProgressStore

    use_json = bool(json_output or getattr(args, "json", False))
    payload: dict[str, Any]
    try:
        setups = SetupLibrary().list()
        progress = SetupProgressStore().list()
        action = str(args.setup_action)
        if action == "list":
            rows: list[dict[str, Any]] = []
            for identifier, document in setups:
                runs = [item for item in progress if item.get("setup_id") == identifier]
                latest = max(runs, key=lambda item: float(item.get("started_at", 0))) if runs else None
                rows.append({
                    "id": identifier,
                    "name": document.name,
                    "applications": len(document.applications),
                    "settings": len(document.profile.settings),
                    "latest_progress": ({"status": latest.get("status"), "started_at": latest.get("started_at")}
                                        if latest is not None else None),
                })
            payload = {"schema_id": "loofi.setup-library", "schema_version": 1, "setups": rows}
        else:
            identifier = str(args.setup_id)
            saved_document = next((item for setup_id, item in setups if setup_id == identifier), None)
            if saved_document is None:
                error_fn(f"Unknown saved setup: {identifier}")
                return 2
            if action == "show":
                payload = {"schema_id": "loofi.setup", "schema_version": 1, "id": identifier,
                           "document": saved_document.to_dict(),
                           "progress": [item for item in progress if item.get("setup_id") == identifier]}
            elif action == "compare":
                payload = _compare(identifier, saved_document)
            else:
                error_fn(f"Unknown setup command: {action}")
                return 2
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        error_fn(str(exc))
        return 1

    if use_json:
        output_json(payload)
    elif action == "list":
        for row in payload["setups"]:
            progress_status = row["latest_progress"]["status"] if row["latest_progress"] else "not started"
            print_fn(f"{row['name']} [{row['id']}] — {row['applications']} apps, {row['settings']} settings — {progress_status}")
        if not payload["setups"]:
            print_fn("No local Fedora configurations are saved.")
    elif action == "show":
        document = payload["document"]
        print_fn(f"{document['name']} [{identifier}]")
        for app in document["applications"]:
            print_fn(f"- App: {app.get('name') or app['app_id']} · {app['source']} · {app['installation']} · {app['ref']}")
        for setting in document["profile"]["settings"]:
            print_fn(f"- Setting: {setting['id']} = {setting['value']}")
        print_fn(f"Saved progress records: {len(payload['progress'])}")
    else:
        print_fn(f"{payload['name']} — read at {payload['sampled_at']}")
        for entry in payload["entries"]:
            current = f" · current {entry['current']}" if entry["current"] else ""
            target = f" · target {entry['desired']}" if entry["desired"] else ""
            detail = f" · {entry['message']}" if entry["message"] else ""
            print_fn(f"- {entry['kind']}: {entry['title']} [{entry['status']}]{current}{target}{detail}")
    return 0


def _compare(identifier: str, document: Any) -> dict[str, Any]:
    from core.actions.operation_controller import OperationController
    from core.tasks.tweaks import _profile_desktop, snapshot, visible_tweaks
    from core.tasks.setup_configurations import compare_setup
    from services.software.installed_applications import InstalledApplicationService
    from services.system import SystemManager

    profile = SystemManager.get_platform_profile()
    host_desktop = _profile_desktop(profile)
    controller = OperationController()
    inventory = InstalledApplicationService().snapshot()
    from core.tasks.tweaks import TweakState
    states: tuple[TweakState, ...] = ()
    if document.profile.settings and document.profile.desktop == host_desktop:
        allowed = {tweak.id for tweak in visible_tweaks(profile)}
        requested = tuple(key for key, _value in document.profile.settings if key in allowed)
        states = snapshot(profile, controller.orchestrator.runtime, tweak_ids=requested)
    return compare_setup(document, identifier, inventory, states, current_desktop=host_desktop).to_dict()
