"""Trusted Change Journal CLI presentation."""

from __future__ import annotations

from typing import Any, Callable


def handle_activity(
    args: Any,
    *,
    json_output: bool,
    output_json: Callable[[Any], Any],
    print_fn: Callable[[Any], Any],
    create_plan: Callable[[str, dict[str, Any]], Any],
    emit_plans: Callable[[Any], int],
) -> int:
    """Inspect inert change history or create one reviewed recovery plan."""
    from core.change_journal import ChangeJournalService

    service = ChangeJournalService()
    action = getattr(args, "activity_action", None) or "list"
    refresh = bool(getattr(args, "refresh", False))
    if action == "list":
        selected_sources = getattr(args, "source", []) or None
        snapshot = service.snapshot(
            limit=getattr(args, "limit", 25),
            since=getattr(args, "since", None),
            until=getattr(args, "until", None),
            sources=selected_sources,
            statuses=getattr(args, "statuses", None) or None,
            reboot_required=(
                True if getattr(args, "reboot", None) == "required"
                else False if getattr(args, "reboot", None) == "not-required"
                else None
            ),
            search=getattr(args, "search", None),
            refresh=refresh,
        )
        payload = snapshot.to_dict()
        if json_output:
            output_json(payload)
        else:
            for event in snapshot.events:
                recovery_label = (
                    f" recovery={event.recovery.kind}"
                    if event.recovery.kind != "none"
                    else ""
                )
                print_fn(
                    f"{event.event_id} [{event.source}/{event.state}] "
                    f"{event.summary}{recovery_label}"
                )
            unavailable = [
                status.source
                for status in snapshot.sources
                if status.availability != "available"
            ]
            if unavailable:
                print_fn(f"Partial sources: {', '.join(unavailable)}")
        return 0

    event_id = str(getattr(args, "event_id", ""))
    if action == "export":
        try:
            content = service.export_event(
                event_id,
                format=str(getattr(args, "format", "json")),
                refresh=refresh,
            )
        except (KeyError, ValueError) as exc:
            if json_output:
                output_json(
                    {
                        "schema": "loofi.activity-export/v1",
                        "error": "export_unavailable",
                        "event_id": event_id,
                        "message": str(exc),
                    }
                )
            else:
                print_fn(str(exc))
            return 1
        if json_output:
            output_json(
                {
                    "schema": "loofi.activity-export/v1",
                    "event_id": event_id,
                    "format": str(getattr(args, "format", "json")),
                    "content": content,
                }
            )
        else:
            print_fn(content)
        return 0

    selected_event = service.get(event_id, refresh=refresh)
    if selected_event is None:
        if json_output:
            output_json(
                {
                    "schema": "loofi.change-journal/v1",
                    "error": "not_found",
                    "event_id": event_id,
                }
            )
        else:
            print_fn(f"Activity event not found: {event_id}")
        return 1

    if action == "show":
        if json_output:
            output_json(
                {
                    "schema": "loofi.change-journal/v1",
                    "event": selected_event.to_dict(),
                }
            )
        else:
            print_fn(f"{selected_event.summary}")
            print_fn(f"Source: {selected_event.source}; state: {selected_event.state}")
            print_fn(f"Resources: {', '.join(selected_event.resources) or 'none'}")
            print_fn(f"Recovery: {selected_event.recovery.kind}")
        return 0

    if action == "related":
        related = service.related(
            selected_event.event_id,
            limit=getattr(args, "limit", 20),
            refresh=refresh,
        )
        payload = {
            "schema": "loofi.change-journal/v1",
            "relationship": "possibly_related",
            "event_id": selected_event.event_id,
            "events": [candidate.to_dict() for candidate in related],
        }
        if json_output:
            output_json(payload)
        else:
            for candidate in related:
                print_fn(
                    f"{candidate.event_id} [{candidate.source}] "
                    f"Possibly related: {candidate.summary}"
                )
        return 0

    if action == "recover":
        capability = selected_event.recovery
        if capability.kind != "action_center" or capability.action_id is None:
            message = capability.guidance or "This event has no automated recovery capability."
            if json_output:
                output_json(
                    {
                        "schema": "loofi.change-journal/v1",
                        "error": "recovery_unavailable",
                        "event_id": selected_event.event_id,
                        "guidance": message,
                    }
                )
            else:
                print_fn(message)
            return 1
        plan = create_plan(
            capability.action_id,
            dict(capability.parameters),
        )
        return emit_plans([plan])
    return 1
