"""Versioned CLI interface for explicit troubleshooting sessions."""

from __future__ import annotations

import signal
import threading
from pathlib import Path
from typing import Any, Callable

from core.troubleshooting.inspection import (
    INTERFACE_SCHEMA_ID,
    INTERFACE_SCHEMA_VERSION,
    TroubleshootingInspectionService,
    bounded_session_payload,
    profile_payload,
    sanitize_interface_payload,
)
from core.troubleshooting.lifecycle import CancellationSignal
from core.troubleshooting.profiles import all_profiles
from core.troubleshooting.service import TroubleshootingService
from core.troubleshooting.storage import UnsupportedFutureSessionSchema


def _envelope(command: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": INTERFACE_SCHEMA_ID,
        "schema_version": INTERFACE_SCHEMA_VERSION,
        "command": command,
        "data": data,
    }


def _emit_error(
    *,
    command: str,
    code: str,
    message: str,
    json_output: bool,
    output_json: Callable[[Any], Any],
    print_fn: Callable[[str], None],
) -> int:
    payload = _envelope(
        command,
        {
            "status": "error",
            "error": code,
            "message": message,
        },
    )
    if json_output:
        output_json(payload)
    else:
        print_fn(f"Error: {message}")
    return 2


def _run_with_cancellation(
    service: TroubleshootingService,
    profile_id: str,
    parameters: dict[str, Any] | None,
) -> Any:
    cancellation = CancellationSignal()
    previous_handler: Any = None
    handler_installed = False

    if threading.current_thread() is threading.main_thread():
        previous_handler = signal.getsignal(signal.SIGINT)

        def request_cancel(_signum: int, _frame: Any) -> None:
            cancellation.cancel()

        signal.signal(signal.SIGINT, request_cancel)
        handler_installed = True

    try:
        return service.run(
            profile_id,
            parameters=parameters,
            cancellation=cancellation,
        )
    finally:
        if handler_installed:
            signal.signal(signal.SIGINT, previous_handler)


def handle_troubleshoot(
    args: Any,
    json_output: bool,
    output_json: Callable[[Any], Any],
    print_fn: Callable[[str], None],
    journal_manager_cls: Any,
) -> int:
    """Handle the closed troubleshooting command family."""
    action = getattr(args, "troubleshoot_action", None)
    if action is None:
        return _emit_error(
            command="",
            code="missing_command",
            message="A troubleshooting command is required.",
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )

    try:
        if action == "profiles":
            profiles = [profile_payload(profile) for profile in all_profiles()]
            payload = _envelope(
                action,
                {
                    "status": "available",
                    "profiles": profiles,
                    "count": len(profiles),
                },
            )
            if json_output:
                output_json(payload)
            else:
                for profile in profiles:
                    print_fn(
                        f"{profile['profile_id']}: {profile['title']} "
                        f"({profile['total_budget_seconds']:.0f}s)"
                    )
            return 0

        if action == "run":
            application_id = getattr(args, "application_id", None)
            parameters = (
                {"application_id": application_id}
                if application_id is not None
                else None
            )
            result = _run_with_cancellation(
                TroubleshootingService(),
                str(args.profile_id),
                parameters,
            )
            persistence_warning = result.persistence_reason_code
            data = {
                "status": result.session.state,
                "session": bounded_session_payload(result.session),
                "comparison": (
                    sanitize_interface_payload(result.comparison.to_dict())
                    if result.comparison is not None
                    else None
                ),
                "persistence_warning": persistence_warning,
            }
            payload = _envelope(action, data)
            if json_output:
                output_json(payload)
            else:
                print_fn(
                    f"Session {result.session.session_id}: "
                    f"{result.session.state}"
                )
                print_fn(f"Findings: {len(result.session.findings)}")
                if persistence_warning:
                    print_fn(
                        "Warning: session persistence is unavailable "
                        f"({persistence_warning})."
                    )
            if result.session.state == "cancelled":
                return 130
            return (
                0
                if result.session.state in {"completed", "partial"}
                else 1
            )

        inspection = TroubleshootingInspectionService()

        if action == "show":
            shown_session = inspection.require(str(args.session_id))
            payload = _envelope(
                action,
                {
                    "status": "available",
                    "session": bounded_session_payload(shown_session),
                },
            )
            if json_output:
                output_json(payload)
            else:
                print_fn(
                    f"Session {shown_session.session_id}: "
                    f"{shown_session.state} "
                    f"({shown_session.profile_id})"
                )
            return 0

        if action == "latest":
            latest_session = inspection.latest()
            payload = _envelope(
                action,
                {
                    "status": (
                        "available"
                        if latest_session is not None
                        else "empty"
                    ),
                    "session": (
                        bounded_session_payload(latest_session)
                        if latest_session is not None
                        else None
                    ),
                },
            )
            if json_output:
                output_json(payload)
            elif latest_session is None:
                print_fn("No saved troubleshooting session.")
            else:
                print_fn(
                    f"Session {latest_session.session_id}: "
                    f"{latest_session.state} "
                    f"({latest_session.profile_id})"
                )
            return 0

        if action == "compare":
            comparison = inspection.compare(
                str(args.session_id),
                str(args.followup_id),
            )
            payload = _envelope(
                action,
                {
                    "status": (
                        "available"
                        if comparison.comparable
                        else "not_comparable"
                    ),
                    "comparison": sanitize_interface_payload(
                        comparison.to_dict()
                    ),
                },
            )
            if json_output:
                output_json(payload)
            else:
                print_fn(
                    "Comparable"
                    if comparison.comparable
                    else f"Not comparable: {comparison.reason_code}"
                )
            return 0

        if action == "export":
            exported_session = inspection.require(str(args.session_id))
            output = getattr(args, "output", None)
            result = journal_manager_cls.export_support_bundle(
                Path(output) if output else None,
                troubleshooting_session_id=exported_session.session_id,
            )
            payload = _envelope(
                action,
                {
                    "status": "exported" if result.success else "failed",
                    "session_id": exported_session.session_id,
                    "message": result.message,
                    "export": sanitize_interface_payload(
                        result.data or {}
                    ),
                },
            )
            if json_output:
                output_json(payload)
            else:
                print_fn(
                    f"{'Exported' if result.success else 'Failed'}: "
                    f"{result.message}"
                )
            return 0 if result.success else 1

        return _emit_error(
            command=str(action),
            code="unknown_command",
            message="Unknown troubleshooting command.",
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )
    except UnsupportedFutureSessionSchema as exc:
        return _emit_error(
            command=str(action),
            code="future_schema_read_only",
            message=str(exc),
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )
    except LookupError as exc:
        return _emit_error(
            command=str(action),
            code="not_found",
            message=str(exc),
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return _emit_error(
            command=str(action),
            code="invalid_request",
            message=str(exc),
            json_output=json_output,
            output_json=output_json,
            print_fn=print_fn,
        )
