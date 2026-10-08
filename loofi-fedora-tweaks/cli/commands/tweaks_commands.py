"""CLI handlers for desktop and system tweaks."""

from __future__ import annotations

from typing import Any, Callable
from subprocess import TimeoutExpired

from core.actions import ActionCatalog, ActionCenterOrchestrator, OperationController
from core.actions.catalog import SystemActionRuntime
from core.actions.tweak_operations import activate_verified_tweak, activation_parameters
from core.executor.command_facade import CommandFacade
from core.platform import detect_platform_profile
from core.tasks.tweak_history import read_tweak_runs, restoration_for
from core.tasks.tweaks import BY_ID, inspect_one, read_tweak, snapshot


def handle_tweaks(
    args: Any,
    json_output: bool,
    output_json: Callable[[Any], None],
    print_fn: Callable[[str], None],
    *,
    dry_run: bool = False,
) -> int:
    action = getattr(args, "tweaks_action", "list") or "list"
    profile = detect_platform_profile()
    runtime = SystemActionRuntime(CommandFacade())

    if action == "profile":
        return _handle_profile(args, json_output, output_json, print_fn, profile, runtime, dry_run=dry_run)
    if action == "preset":
        return _handle_preset(args, json_output, output_json, print_fn, profile, runtime, dry_run=dry_run)

    if action == "list":
        states = snapshot(profile, runtime)
        desktop_filter = getattr(args, "desktop", "all")
        if desktop_filter != "all":
            states = tuple(s for s in states if s.tweak.desktop in {"all", desktop_filter})
        if json_output:
            output_json({
                "schema_version": 1,
                "tweaks": [
                    {
                        "id": s.tweak.id,
                        "title": s.tweak.title,
                        "description": s.tweak.description,
                        "group": s.tweak.group,
                        "desktop": s.tweak.desktop,
                        "status": s.status,
                        "value": s.value,
                        "choices": [dict(value=c[0], label=c[1]) for c in s.choices],
                        "restore_available": bool(s.restore_run_id),
                        "restore_value": s.restore_value,
                    }
                    for s in states
                ],
            })
        else:
            print_fn(f"{'ID':<28} {'CURRENT':<16} {'STATUS':<10} {'RESTORE':<10} {'TITLE'}")
            print_fn("-" * 80)
            for s in states:
                restore_info = s.restore_value if s.restore_run_id else "-"
                print_fn(f"{s.tweak.id:<28} {s.value[:15]:<16} {s.status:<10} {restore_info:<10} {s.tweak.title}")
        return 0

    if action == "get":
        tweak_id = getattr(args, "tweak_id", "").strip()
        tweak = BY_ID.get(tweak_id)
        if tweak is None:
            print_fn(f"Unknown tweak: {tweak_id}")
            return 1
        state = inspect_one(tweak_id, profile, runtime)
        if json_output:
            output_json({
                "schema_version": 1,
                "id": tweak.id,
                "title": tweak.title,
                "description": tweak.description,
                "group": tweak.group,
                "desktop": tweak.desktop,
                "status": state.status,
                "value": state.value,
                "choices": [dict(value=c[0], label=c[1]) for c in state.choices],
                "restore_run_id": state.restore_run_id,
                "restore_value": state.restore_value,
                "message": state.message or state.restore_message,
            })
        else:
            print_fn(f"Setting:     {tweak.title} ({tweak.id})")
            print_fn(f"Group:       {tweak.group} [{tweak.desktop}]")
            print_fn(f"Description: {tweak.description}")
            print_fn(f"Status:      {state.status}")
            print_fn(f"Value:       {state.value or '(none)'}")
            if state.choices:
                print_fn("Choices:")
                for val, lbl in state.choices:
                    marker = " *" if val == state.value else ""
                    print_fn(f"  - {val}: {lbl}{marker}")
            if state.restore_run_id:
                print_fn(f"Restorable:  {state.restore_value} (from {state.restore_run_id})")
        return 0

    if action == "set":
        tweak_id = getattr(args, "tweak_id", "").strip()
        value = getattr(args, "value", "").strip()
        tweak = BY_ID.get(tweak_id)
        if tweak is None:
            print_fn(f"Unknown tweak: {tweak_id}")
            return 1
        controller = OperationController(
            orchestrator=ActionCenterOrchestrator(catalog=ActionCatalog(), runtime=runtime),
            facade=runtime.facade,
        )
        ticket = controller.prepare(tweak.action_id, {"value": value})
        if ticket.blocked:
            print_fn(f"Cannot apply {tweak_id}: {ticket.plan.policy_decision.explanation}")
            return 1
        if dry_run:
            print_fn(f"[dry-run] Would apply {tweak.action_id} with value={value}")
            return 0
        if not getattr(args, "yes", False):
            print_fn(f"Plan: Set '{tweak.title}' to '{value}'")
            print_fn(f"Action: {tweak.action_id}")
            print_fn("Pass --yes to confirm execution.")
            return 0
        prepared = controller.confirm(ticket, confirmed=True)
        if prepared.status != "prepared":
            print_fn(f"Failed to apply {tweak.title}: {prepared.message}")
            return 1
        outcome = controller.run(prepared)
        if outcome.status == "verifying":
            outcome = controller.verify(outcome)
        if outcome.success:
            if activation_parameters(outcome):
                print_fn(activate_verified_tweak(controller, outcome).message)
            print_fn(f"Successfully applied {tweak.title}: {value}")
            return 0
        print_fn(f"Failed to apply {tweak.title}: {outcome.message}")
        return 1

    if action == "restore":
        tweak_id = getattr(args, "tweak_id", "").strip()
        tweak = BY_ID.get(tweak_id)
        if tweak is None:
            print_fn(f"Unknown tweak: {tweak_id}")
            return 1
        runs, _ = read_tweak_runs(runtime)
        state = read_tweak(tweak, profile, runtime.execute_read_only)
        offer = restoration_for(tweak, state, runs)
        if not offer.source_run_id:
            print_fn(offer.message or "No previous verified change available to restore.")
            return 1
        controller = OperationController(
            orchestrator=ActionCenterOrchestrator(catalog=ActionCatalog(), runtime=runtime),
            facade=runtime.facade,
        )
        ticket = controller.prepare(f"restore-{tweak.id}", {"source_run_id": offer.source_run_id})
        if ticket.blocked:
            print_fn(f"Cannot restore {tweak_id}: {ticket.plan.policy_decision.explanation}")
            return 1
        if dry_run:
            print_fn(f"[dry-run] Would restore {tweak_id} to '{offer.before}'")
            return 0
        if not getattr(args, "yes", False):
            print_fn(f"Plan: Restore '{tweak.title}' to '{offer.before}'")
            print_fn("Pass --yes to confirm execution.")
            return 0
        prepared = controller.confirm(ticket, confirmed=True)
        if prepared.status != "prepared":
            print_fn(f"Failed to restore {tweak.title}: {prepared.message}")
            return 1
        outcome = controller.run(prepared)
        if outcome.status == "verifying":
            outcome = controller.verify(outcome)
        if outcome.success:
            if activation_parameters(outcome):
                print_fn(activate_verified_tweak(controller, outcome).message)
            print_fn(f"Successfully restored {tweak.title}: {offer.before}")
            return 0
        print_fn(f"Failed to restore {tweak.title}: {outcome.message}")
        return 1

    return 0


def _handle_profile(args: Any, json_output: bool, output_json: Callable[[Any], None], print_fn: Callable[[str], None],
                    profile: object, runtime: Any, *, dry_run: bool) -> int:
    from pathlib import Path
    from core.tasks.tweak_profiles import apply_profile, export_profile, load_profile, review_profile, save_profile

    operation = args.profile_action
    try:
        if operation == "library":
            from core.tasks.tweak_library import ProfileLibrary

            library = ProfileLibrary()
            library_action = args.library_action
            payload: dict[str, Any]
            if library_action == "list":
                payload = {"schema": "loofi.tweak-library/v1", "profiles": [entry.to_dict() for entry in library.list(profile)]}
            elif library_action == "add":
                imported = load_profile(Path(args.path))
                payload = {"schema": "loofi.tweak-library/v1", "saved": not dry_run, "profile": imported.to_dict()}
                if not dry_run:
                    payload["entry"] = library.add(imported).to_dict()
            else:
                library._path(args.profile_id)
                if not dry_run:
                    library.remove(args.profile_id)
                payload = {"schema": "loofi.tweak-library/v1", "removed": not dry_run, "id": args.profile_id}
            if json_output:
                output_json(payload)
            elif library_action == "list":
                for library_entry in payload["profiles"]:
                    print_fn(f"{library_entry['id']}: {library_entry['profile']['name']} [{library_entry['profile']['desktop']}] {'built-in' if library_entry['builtin'] else 'custom'}")
            else:
                print_fn("[dry-run] Library unchanged." if dry_run else "Profile library updated.")
            return 0
        if operation == "export":
            exported = export_profile(args.name, profile, runtime, getattr(args, "ids", None))
            if not dry_run:
                save_profile(Path(args.path), exported.profile)
            payload = exported.to_dict()
            payload["saved"] = not dry_run
            if json_output:
                output_json(payload)
            else:
                print_fn(f"{'Would save' if dry_run else 'Saved'} {len(exported.profile.settings)} settings to {args.path}")
                for key, reason in exported.omitted:
                    print_fn(f"Omitted {key}: {reason}")
            return 0
        controller = OperationController(orchestrator=ActionCenterOrchestrator(catalog=ActionCatalog(), runtime=runtime), facade=runtime.facade)
        review = review_profile(load_profile(Path(args.path)), controller)
        if operation == "apply" and getattr(args, "yes", False) and not dry_run:
            result = apply_profile(review, controller, confirmed=True, selected_ids=getattr(args, "ids", None))
            if json_output:
                output_json(result.to_dict())
            else:
                for item in result.entries:
                    print_fn(f"{item.id}: {item.status} — {item.message}")
                print_fn(result.message)
            return 0 if result.success else 1
        if json_output:
            output_json(review.to_dict())
        else:
            print_fn(f"Profile: {review.name} [{review.desktop}]")
            for entry in review.entries:
                print_fn(f"{entry.id}: {entry.before or '?'} -> {entry.value} [{entry.status}] {entry.message}")
            if operation == "apply":
                print_fn("Pass --yes to confirm execution." if not dry_run else "[dry-run] No settings changed.")
        return 0
    except (OSError, RuntimeError, TypeError, ValueError, TimeoutExpired) as exc:
        if json_output:
            output_json({"schema": "loofi.tweak-profile-result/v1", "status": "failed", "message": str(exc), "entries": []})
        else:
            print_fn(f"Profile operation failed: {exc}")
        return 1


def _handle_preset(args: Any, json_output: bool, output_json: Callable[[Any], None], print_fn: Callable[[str], None],
                   platform: object, runtime: Any, *, dry_run: bool) -> int:
    """List, review, or apply built-in presets using portable profile authority."""
    from core.tasks.tweak_presets import BY_PRESET_ID, list_presets, profile_for_preset
    from core.tasks.tweak_profiles import apply_profile, review_profile

    operation = args.preset_action
    if operation == "list":
        presets = list_presets()
        if json_output:
            output_json({"schema": "loofi.tweak-presets/v1", "presets": [item.to_dict() for item in presets]})
        else:
            for item in presets:
                print_fn(f"{item.id}: {item.name} — {item.description} [{', '.join(sorted(item.settings))}]")
        return 0

    preset_id = str(args.preset_id).strip()
    selected_preset = BY_PRESET_ID.get(preset_id)
    if selected_preset is None:
        message = f"Unknown tweak preset: {preset_id}"
        if json_output:
            output_json({"schema": "loofi.tweak-profile-result/v1", "status": "failed", "message": message, "entries": []})
        else:
            print_fn(message)
        return 1
    try:
        profile = profile_for_preset(preset_id, platform)
        controller = OperationController(
            orchestrator=ActionCenterOrchestrator(catalog=ActionCatalog(), runtime=runtime),
            facade=runtime.facade,
        )
        review = review_profile(profile, controller)
        if operation == "apply" and getattr(args, "yes", False) and not dry_run:
            result = apply_profile(review, controller, confirmed=True, selected_ids=getattr(args, "ids", None))
            if json_output:
                output_json({"preset": selected_preset.to_dict(), "result": result.to_dict()})
            else:
                for result_entry in result.entries:
                    print_fn(f"{result_entry.id}: {result_entry.status} — {result_entry.message}")
                print_fn(result.message)
            return 0 if result.success else 1
        if json_output:
            output_json({"preset": selected_preset.to_dict(), "review": review.to_dict()})
        else:
            print_fn(f"Preset: {selected_preset.name} [{profile.desktop}]")
            for review_entry in review.entries:
                print_fn(f"{review_entry.id}: {review_entry.before or '?'} -> {review_entry.value} [{review_entry.status}] {review_entry.message}")
            if operation == "apply":
                print_fn("[dry-run] No settings changed." if dry_run else "Pass --yes to confirm execution.")
        return 0
    except (OSError, RuntimeError, TypeError, ValueError, TimeoutExpired) as exc:
        if json_output:
            output_json({"schema": "loofi.tweak-profile-result/v1", "status": "failed", "message": str(exc), "entries": []})
        else:
            print_fn(f"Preset operation failed: {exc}")
        return 1
