"""Read-only CLI presentation for curated Fedora guides."""

from __future__ import annotations

from typing import Any, Callable

from core.tasks.guides import (
    GUIDES,
    GUIDES_BY_ID,
    GuideProgressStore,
    guide_evidence_exists,
    guide_progress_payload,
)


def handle_guides(
    args: Any,
    *,
    json_output: bool,
    output_json: Callable[[Any], Any],
    print_fn: Callable[[str], Any],
    error_fn: Callable[[str], Any],
) -> int:
    """List or show saved guide progress without changing it."""
    try:
        snapshot = GuideProgressStore().read()
        payload: dict[str, Any]
        if args.guides_action == "list":
            payload = {
                "schema_id": "loofi.user-guides",
                "schema_version": 1,
                "active_guide": snapshot.active_guide,
                "writable": snapshot.writable,
                "reason_code": snapshot.reason_code,
                "guides": [
                    {
                        "id": guide.id,
                        "title": guide.title,
                        "active": snapshot.active_guide == guide.id,
                        "completed_steps": sum(
                            snapshot.steps.get(step.id) is not None
                            and (
                                snapshot.steps[step.id].state == "reviewed"
                                or (
                                    snapshot.steps[step.id].state == "verified"
                                    and guide_evidence_exists(
                                        snapshot.steps[step.id].evidence_kind,
                                        snapshot.steps[step.id].evidence_id,
                                    )
                                )
                            )
                            for step in guide.steps
                        ),
                        "step_count": len(guide.steps),
                    }
                    for guide in GUIDES
                ],
            }
        else:
            guide = GUIDES_BY_ID.get(str(args.guide_id))
            if guide is None:
                error_fn(f"Unknown guide: {args.guide_id}")
                return 2
            payload = {
                "schema_id": "loofi.user-guide",
                "schema_version": 1,
                "progress_revision": snapshot.revision,
                **guide_progress_payload(guide.id, snapshot),
            }
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        error_fn(str(exc))
        return 1

    if json_output:
        output_json(payload)
    elif args.guides_action == "list":
        for guide in payload["guides"]:
            current = " · active" if guide["active"] else ""
            print_fn(f"{guide['title']} — {guide['completed_steps']}/{guide['step_count']} reviewed{current}")
    else:
        print_fn(payload["title"])
        print_fn(payload["description"])
        for step in payload["steps"]:
            print_fn(f"[{step['status']}] {step['title']} — {step['description']}")
    return 0
