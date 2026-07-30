"""Closed manual-only definitions for migrated public host operations."""

from __future__ import annotations

import re
from typing import Any, Callable, Literal, Mapping

from core.actions.contracts import (
    ActionDefinition,
    PolicyDecision,
    VerificationDecision,
)

_ALLOWED_BACKENDS = {"timeshift", "snapper"}
_FLATPAK_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,255}$")


def _allowed(code: str, explanation: str) -> PolicyDecision:
    return PolicyDecision(True, code, explanation)


def _blocked(code: str, explanation: str) -> PolicyDecision:
    return PolicyDecision(False, code, explanation)


def _manual_definition(
    action_id: str,
    title: str,
    description: str,
    recovery_guidance: str,
    affected_resources: tuple[str, ...],
    *,
    parameter_schema: Mapping[str, Mapping[str, Any]] | None = None,
    parameter_validator: Callable[[Mapping[str, Any]], PolicyDecision] | None = None,
    reboot_policy: Literal["none", "may_require", "required"] = "none",
) -> ActionDefinition:
    return ActionDefinition(
        id=action_id,
        capability_id=f"manual.{action_id}",
        title=title,
        description=description,
        parameter_schema={
            name: dict(schema)
            for name, schema in (parameter_schema or {}).items()
        },
        risk_level="medium",
        privileged=False,
        confirmation_policy="explicit-no-rollback",
        recovery_guidance=recovery_guidance,
        rollback_supported=False,
        command_renderer=lambda _parameters, _runtime: [],
        preflight_checker=lambda _parameters, _runtime: _blocked(
            "manual_only",
            description,
        ),
        verifier=lambda _run, _plan, _runtime: VerificationDecision.failed(
            "Manual-only actions are never executed by Loofi."
        ),
        operation_class="manual_only",
        supported_variants=frozenset({"traditional", "atomic"}),
        reboot_policy=reboot_policy,
        affected_resources=affected_resources,
        parameter_validator=parameter_validator,
    )


def public_boundary_definitions() -> list[ActionDefinition]:
    """Return parameter-closed manual plans for public compatibility commands."""
    return [
        _manual_definition(
            "allow-firewall-port",
            "Allow firewall port",
            "Firewall rule changes require guided review until exact rollback verification is available.",
            "Review the selected port, protocol, and zone, then apply and verify the rule manually.",
            ("firewall", "network-ports"),
            parameter_schema={
                "port": {"type": "integer", "required": True},
                "protocol": {"type": "string", "required": True},
                "zone": {"type": "string", "required": False},
            },
            parameter_validator=_validate_firewall_port,
        ),
        _manual_definition(
            "firewall-service-control",
            "Change firewall service rule",
            "Firewall service rules remain guided manual work until exact rollback verification is available.",
            "Review the exact service and zone before changing the permanent firewall policy manually.",
            ("firewall", "network-services"),
            parameter_schema={
                "action": {"type": "string", "required": True},
                "service": {"type": "string", "required": True},
                "zone": {"type": "string", "required": False},
            },
            parameter_validator=_validate_firewall_service,
        ),
        _manual_definition(
            "set-firewall-default-zone",
            "Set default firewall zone",
            "Changing the default firewall zone remains guided manual work.",
            "Review active interfaces and the selected zone before changing the default manually.",
            ("firewall", "network-zones"),
            parameter_schema={"zone": {"type": "string", "required": True}},
            parameter_validator=_validate_firewall_zone,
        ),
        _manual_definition(
            "reload-firewall",
            "Reload firewall policy",
            "Reloading firewall policy remains guided manual work.",
            "Review permanent and runtime rules before reloading the firewall manually.",
            ("firewall",),
        ),
        _manual_definition(
            "apply-performance-tuning",
            "Apply performance tuning",
            "Multi-resource kernel tuning remains guided manual work.",
            "Review each recommended setting and retain the current values before changing them manually.",
            ("kernel-tunables", "power-profile"),
            parameter_schema={"settings": {"type": "object", "required": True}},
            parameter_validator=_validate_performance_settings,
        ),
        *[
            _manual_definition(
                f"{action}-recovery-point",
                f"{action.title()} recovery point",
                f"Recovery-point {action} remains guided manual work.",
                (
                    "Verify the exact backend and recovery point before "
                    f"{'restoring' if action == 'restore' else 'deleting'} it manually."
                ),
                (
                    ("recovery-points", "filesystem")
                    if action == "restore"
                    else ("recovery-points",)
                ),
                parameter_schema={
                    "backend": {"type": "string", "required": True},
                    "snapshot_id": {"type": "string", "required": True},
                },
                parameter_validator=_validate_recovery_point_selection,
                reboot_policy="may_require" if action == "restore" else "none",
            )
            for action in ("restore", "delete")
        ],
        *[
            _manual_definition(
                f"{action}-desktop-extension",
                f"{action.title()} desktop extension",
                "Desktop extension changes remain guided manual work.",
                "Review the exact extension identifier and use the desktop extension manager manually.",
                ("desktop-extensions",),
                parameter_schema={"uuid": {"type": "string", "required": True}},
                parameter_validator=_validate_extension_uuid,
            )
            for action in ("enable", "disable", "install", "remove")
        ],
        _manual_definition(
            "update-flatpak-application",
            "Update Flatpak application",
            "A selected Flatpak update remains manual-only until its exact target commit can be verified.",
            "Review the exact application identifier and update it manually.",
            ("flatpak-applications",),
            parameter_schema={"app_id": {"type": "string", "required": False}},
            parameter_validator=_validate_optional_flatpak_id,
        ),
        _manual_definition(
            "set-fractional-scaling",
            "Change fractional scaling",
            "Display-session scaling changes remain guided manual work.",
            "Review the current Plasma display configuration before changing fractional scaling manually.",
            ("display-session",),
            parameter_schema={"enabled": {"type": "boolean", "required": True}},
        ),
        _manual_definition(
            "schedule-system-update",
            "Schedule system update",
            "Unattended host updates remain guided manual work.",
            "Review the schedule, package-manager behavior, and reboot policy before creating a timer manually.",
            ("packages", "systemd-timers"),
            parameter_schema={"when": {"type": "string", "required": True}},
            parameter_validator=_validate_update_schedule,
        ),
        _manual_definition(
            "rollback-latest-update",
            "Review latest update rollback",
            "A rollback requires an exact transaction or deployment identity.",
            "Inspect update history and create an exact DNF5 undo or rpm-ostree rollback plan.",
            ("packages", "deployment"),
            reboot_policy="may_require",
        ),
        _manual_definition(
            "control-focus-mode",
            "Change focus mode",
            "Focus mode can change host filtering, processes, and desktop session state.",
            "Review the selected profile and its domain/process effects before changing focus mode manually.",
            ("hosts-file", "desktop-session", "processes"),
            parameter_schema={
                "action": {"type": "string", "required": True},
                "profile": {"type": "string", "required": False},
            },
            parameter_validator=_validate_focus_mode,
        ),
        _manual_definition(
            "control-bluetooth-device",
            "Change Bluetooth device state",
            "Bluetooth pairing, trust, connection, and adapter changes remain guided manual work.",
            "Review the exact action and device address before using the system Bluetooth controls manually.",
            ("bluetooth", "devices"),
            parameter_schema={
                "action": {"type": "string", "required": True},
                "target": {"type": "string", "required": True},
            },
            parameter_validator=_validate_bluetooth_control,
        ),
        _manual_definition(
            "control-virtual-machine",
            "Change virtual machine state",
            "Virtual machine start and stop operations remain guided manual work.",
            "Review the exact virtual machine and its storage state before changing it manually.",
            ("virtual-machines",),
            parameter_schema={
                "action": {"type": "string", "required": True},
                "name": {"type": "string", "required": True},
            },
            parameter_validator=_validate_virtual_machine_control,
        ),
    ]


def _validate_choice(
    parameters: Mapping[str, Any],
    name: str,
    allowed: set[str],
) -> PolicyDecision:
    if parameters.get(name) not in allowed:
        return _blocked(
            "invalid_choice",
            f"Parameter '{name}' must be one of: {', '.join(sorted(allowed))}.",
        )
    return _allowed("parameters_valid", f"Parameter '{name}' is valid.")


def _validate_identifier(
    parameters: Mapping[str, Any],
    name: str,
) -> PolicyDecision:
    value = parameters.get(name)
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",
        value,
    ):
        return _blocked(
            "invalid_identifier",
            f"Parameter '{name}' contains rejected characters.",
        )
    return _allowed("parameters_valid", f"Parameter '{name}' is valid.")


def _validate_firewall_port(parameters: Mapping[str, Any]) -> PolicyDecision:
    port = parameters.get("port")
    protocol = parameters.get("protocol")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        return _blocked(
            "invalid_port",
            "Port must be an integer between 1 and 65535.",
        )
    if protocol not in {"tcp", "udp"}:
        return _blocked("invalid_protocol", "Protocol must be tcp or udp.")
    return _validate_firewall_zone(parameters, optional=True)


def _validate_firewall_service(parameters: Mapping[str, Any]) -> PolicyDecision:
    action = _validate_choice(parameters, "action", {"add", "remove"})
    if not action.allowed:
        return action
    service = parameters.get("service")
    if not isinstance(service, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
        service,
    ):
        return _blocked(
            "invalid_firewall_service",
            "Firewall service contains rejected characters.",
        )
    return _validate_firewall_zone(parameters, optional=True)


def _validate_firewall_zone(
    parameters: Mapping[str, Any],
    *,
    optional: bool = False,
) -> PolicyDecision:
    zone = parameters.get("zone")
    if optional and zone is None:
        return _allowed("parameters_valid", "Firewall parameters are valid.")
    if not isinstance(zone, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
        zone,
    ):
        return _blocked(
            "invalid_zone",
            "Firewall zone contains rejected characters.",
        )
    return _allowed("parameters_valid", "Firewall zone is valid.")


def _validate_performance_settings(
    parameters: Mapping[str, Any],
) -> PolicyDecision:
    settings = parameters.get("settings")
    if not isinstance(settings, Mapping):
        return _blocked(
            "invalid_performance_settings",
            "Performance settings must be an object.",
        )
    allowed = {"governor", "swappiness", "io_scheduler", "thp"}
    if not settings or set(settings) - allowed:
        return _blocked(
            "invalid_performance_settings",
            "Performance settings contain unknown or empty fields.",
        )
    swappiness = settings.get("swappiness")
    if swappiness is not None and (
        not isinstance(swappiness, int)
        or isinstance(swappiness, bool)
        or not 0 <= swappiness <= 100
    ):
        return _blocked(
            "invalid_swappiness",
            "Swappiness must be between 0 and 100.",
        )
    for name in ("governor", "io_scheduler", "thp"):
        value = settings.get(name)
        if value is not None and (
            not isinstance(value, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", value)
        ):
            return _blocked(
                "invalid_performance_setting",
                f"Performance setting '{name}' is invalid.",
            )
    return _allowed("parameters_valid", "Performance settings are valid.")


def _validate_recovery_point_selection(
    parameters: Mapping[str, Any],
) -> PolicyDecision:
    if parameters.get("backend") not in _ALLOWED_BACKENDS:
        return _blocked(
            "invalid_snapshot_backend",
            "Only Timeshift and Snapper recovery points are supported.",
        )
    return _validate_identifier(parameters, "snapshot_id")


def _validate_extension_uuid(parameters: Mapping[str, Any]) -> PolicyDecision:
    uuid = parameters.get("uuid")
    if not isinstance(uuid, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9@._-]{0,127}",
        uuid,
    ):
        return _blocked(
            "invalid_extension_uuid",
            "Desktop extension identifier contains rejected characters.",
        )
    return _allowed(
        "parameters_valid",
        "Desktop extension identifier is valid.",
    )


def _validate_optional_flatpak_id(
    parameters: Mapping[str, Any],
) -> PolicyDecision:
    app_id = parameters.get("app_id")
    if app_id is None:
        return _allowed(
            "parameters_valid",
            "The full Flatpak update request is valid.",
        )
    if not isinstance(app_id, str) or not _FLATPAK_PATTERN.fullmatch(app_id):
        return _blocked(
            "invalid_flatpak_id",
            "Flatpak application identifier is invalid.",
        )
    return _allowed(
        "parameters_valid",
        "Flatpak application identifier is valid.",
    )


def _validate_update_schedule(
    parameters: Mapping[str, Any],
) -> PolicyDecision:
    when = parameters.get("when")
    if not isinstance(when, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d",
        when,
    ):
        return _blocked(
            "invalid_update_schedule",
            "Update schedule must use 24-hour HH:MM format.",
        )
    return _allowed("parameters_valid", "Update schedule is valid.")


def _validate_focus_mode(parameters: Mapping[str, Any]) -> PolicyDecision:
    action = _validate_choice(parameters, "action", {"enable", "disable"})
    if not action.allowed:
        return action
    profile = parameters.get("profile")
    if parameters.get("action") == "enable":
        return _validate_identifier({"profile": profile}, "profile")
    if profile is not None:
        return _blocked(
            "unexpected_profile",
            "Disable does not accept a focus profile.",
        )
    return _allowed("parameters_valid", "Focus mode parameters are valid.")


def _validate_bluetooth_control(
    parameters: Mapping[str, Any],
) -> PolicyDecision:
    action = _validate_choice(
        parameters,
        "action",
        {
            "power-on",
            "power-off",
            "connect",
            "disconnect",
            "pair",
            "unpair",
            "trust",
        },
    )
    if not action.allowed:
        return action
    target = parameters.get("target")
    if target == "adapter" and str(parameters.get("action", "")).startswith(
        "power-"
    ):
        return _allowed(
            "parameters_valid",
            "Bluetooth adapter request is valid.",
        )
    if not isinstance(target, str) or not re.fullmatch(
        r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}",
        target,
    ):
        return _blocked(
            "invalid_bluetooth_target",
            "Bluetooth target must be an exact device address.",
        )
    return _allowed(
        "parameters_valid",
        "Bluetooth device request is valid.",
    )


def _validate_virtual_machine_control(
    parameters: Mapping[str, Any],
) -> PolicyDecision:
    action = _validate_choice(parameters, "action", {"start", "stop"})
    if not action.allowed:
        return action
    return _validate_identifier(parameters, "name")
