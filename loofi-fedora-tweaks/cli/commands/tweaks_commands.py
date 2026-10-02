"""CLI handlers for desktop and system tweaks."""

from __future__ import annotations

from typing import Any, Callable

from core.actions import ActionCatalog, ActionCenterOrchestrator
from core.actions.catalog import SystemActionRuntime
from core.executor.command_facade import CommandFacade
from core.platform import detect_platform_profile
from core.tasks.tweak_history import read_tweak_runs, restoration_for
from core.tasks.tweaks import BY_ID, read_tweak, snapshot


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
        runs, _ = read_tweak_runs(runtime)
        state = read_tweak(tweak, profile, runtime.execute_read_only)
        offer = restoration_for(tweak, state, runs)
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
                "restore_run_id": offer.source_run_id,
                "restore_value": offer.before,
                "message": state.message or offer.message,
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
            if offer.source_run_id:
                print_fn(f"Restorable:  {offer.before} (from {offer.source_run_id})")
        return 0

    if action == "set":
        tweak_id = getattr(args, "tweak_id", "").strip()
        value = getattr(args, "value", "").strip()
        tweak = BY_ID.get(tweak_id)
        if tweak is None:
            print_fn(f"Unknown tweak: {tweak_id}")
            return 1
        catalog = ActionCatalog()
        orchestrator = ActionCenterOrchestrator(catalog=catalog, runtime=runtime)
        plan = orchestrator.plan(tweak.action_id, {"value": value})
        if not plan.policy_decision.allowed:
            print_fn(f"Cannot apply {tweak_id}: {plan.policy_decision.explanation}")
            return 1
        if dry_run:
            print_fn(f"[dry-run] Would apply {tweak.action_id} with value={value}")
            return 0
        if not getattr(args, "yes", False):
            print_fn(f"Plan: Set '{tweak.title}' to '{value}'")
            print_fn(f"Action: {tweak.action_id}")
            print_fn("Pass --yes to confirm execution.")
            return 0
        run = orchestrator.execute(plan)
        if run.state == "succeeded":
            print_fn(f"Successfully applied {tweak.title}: {value}")
            return 0
        print_fn(f"Failed to apply {tweak.title}: {run.error_message}")
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
        catalog = ActionCatalog()
        orchestrator = ActionCenterOrchestrator(catalog=catalog, runtime=runtime)
        plan = orchestrator.plan(f"restore-{tweak.id}", {"source_run_id": offer.source_run_id})
        if not plan.policy_decision.allowed:
            print_fn(f"Cannot restore {tweak_id}: {plan.policy_decision.explanation}")
            return 1
        if dry_run:
            print_fn(f"[dry-run] Would restore {tweak_id} to '{offer.before}'")
            return 0
        if not getattr(args, "yes", False):
            print_fn(f"Plan: Restore '{tweak.title}' to '{offer.before}'")
            print_fn("Pass --yes to confirm execution.")
            return 0
        run = orchestrator.execute(plan)
        if run.state == "succeeded":
            print_fn(f"Successfully restored {tweak.title}: {offer.before}")
            return 0
        print_fn(f"Failed to restore {tweak.title}: {run.error_message}")
        return 1

    return 0
