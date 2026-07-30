"""v17 Assurance action definitions for the five canonical workflows."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Literal, Mapping

from core.actions.contracts import (
    ActionDefinition,
    ActionPlan,
    ActionRun,
    ActionRuntime,
    PolicyDecision,
    VerificationDecision,
)
from core.executor.action_result import ActionResult
from core.local_profiles import validate_local_profile
from core.actions.public_boundary_definitions import public_boundary_definitions
from core.actions.continuity_recovery import (
    _preflight_dnf5_history_undo,
    _preflight_fedora_update,
    _preflight_rpm_ostree_rollback,
    _render_dnf5_history_undo,
    _render_fedora_update,
    _validate_rpm_ostree_rollback,
    _validate_transaction_id,
    _verify_dnf5_history_undo,
    _verify_fedora_update,
    _verify_rpm_ostree_rollback,
)

_PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._-]{0,127}$")
_FLATPAK_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,255}$")
_DESCRIPTION_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]{1,80}$")
_ALLOWED_RETENTION = {7, 14, 30}
_ALLOWED_BACKENDS = {"timeshift", "snapper"}


def assurance_definitions() -> list[ActionDefinition]:
    """Return the bounded v17 catalog additions."""
    return [
        ActionDefinition(
            id="update-fedora-system",
            capability_id="updates.fedora.prepare",
            title="Prepare Fedora update",
            description="Stage the currently planned Fedora package or deployment update without rebooting.",
            parameter_schema={}, risk_level="medium", privileged=True,
            confirmation_policy="explicit-no-rollback",
            recovery_guidance="Traditional systems retain package history; Atomic systems retain the previous deployment.",
            rollback_supported=False, command_renderer=_render_fedora_update,
            preflight_checker=_preflight_fedora_update, verifier=_verify_fedora_update,
            reboot_policy="required",
            affected_resources=("packages", "rpmdb", "boot-state"),
        ),
        ActionDefinition(
            id="dnf5-history-undo",
            capability_id="recovery.dnf5.transaction.undo",
            title="Prepare DNF transaction recovery",
            description="Prepare an offline inverse of one exact, verifiable DNF5 transaction.",
            parameter_schema={"transaction_id": {"type": "integer", "required": True}},
            risk_level="high",
            privileged=True,
            confirmation_policy="explicit-no-rollback",
            recovery_guidance="The inverse is applied only after a separate reboot; create a recovery point first.",
            rollback_supported=False,
            command_renderer=_render_dnf5_history_undo,
            preflight_checker=_preflight_dnf5_history_undo,
            verifier=_verify_dnf5_history_undo,
            supported_variants=frozenset({"traditional"}),
            reboot_policy="required",
            affected_resources=("packages", "rpmdb", "boot-state"),
            parameter_validator=_validate_transaction_id,
        ),
        ActionDefinition(
            id="rpm-ostree-rollback",
            capability_id="recovery.rpm-ostree.rollback",
            title="Stage Atomic rollback",
            description="Stage the exact existing previous deployment and verify it after reboot.",
            parameter_schema={
                "expected_deployment": {"type": "string", "required": True},
                "rollback_deployment": {"type": "string", "required": True},
            },
            risk_level="high",
            privileged=True,
            confirmation_policy="explicit-no-rollback",
            recovery_guidance="The current deployment remains available until the staged rollback is booted.",
            rollback_supported=False,
            command_renderer=lambda _parameters, _runtime: ["rpm-ostree", "rollback"],
            preflight_checker=_preflight_rpm_ostree_rollback,
            verifier=_verify_rpm_ostree_rollback,
            supported_variants=frozenset({"atomic"}),
            reboot_policy="required",
            affected_resources=("rpm-ostree-deployment", "boot-state"),
            parameter_validator=_validate_rpm_ostree_rollback,
        ),
        ActionDefinition(
            id="update-flatpaks",
            capability_id="updates.flatpak.apply",
            title="Update Flatpaks",
            description="Update the exact Flatpak refs discovered during preflight.",
            parameter_schema={}, risk_level="low", privileged=False,
            confirmation_policy="explicit", recovery_guidance="Review Flatpak history and application data if an update regresses.",
            rollback_supported=False, command_renderer=_render_flatpak_update,
            preflight_checker=_preflight_flatpak_update, verifier=_verify_flatpak_update,
        ),
        ActionDefinition(
            id="update-firmware",
            capability_id="updates.firmware.apply",
            title="Update firmware",
            description="Apply firmware updates reported by fwupd and verify device history.",
            parameter_schema={}, risk_level="high", privileged=True,
            confirmation_policy="explicit-no-rollback", recovery_guidance="Do not power off the device; follow vendor recovery guidance if verification fails.",
            rollback_supported=False, command_renderer=lambda _p, _r: ["fwupdmgr", "update", "-y"],
            preflight_checker=_preflight_firmware_update, verifier=_verify_firmware_update,
        ),
        _application_definition("install-application", installing=True),
        _application_definition("remove-application", installing=False),
        ActionDefinition(
            id="vacuum-journal",
            capability_id="maintenance.journal.vacuum",
            title="Vacuum system journal",
            description="Remove journal data older than an explicitly selected retention window.",
            parameter_schema={"days": {"type": "integer", "required": True}},
            risk_level="medium", privileged=True, confirmation_policy="explicit-no-rollback",
            recovery_guidance="Deleted journal entries cannot be restored.", rollback_supported=False,
            command_renderer=lambda p, _r: ["journalctl", f"--vacuum-time={int(p['days'])}d"],
            preflight_checker=_preflight_journal, verifier=_verify_journal,
            parameter_validator=_validate_journal,
        ),
        ActionDefinition(
            id="autoremove-packages",
            capability_id="maintenance.packages.autoremove",
            title="Remove unneeded packages",
            description="Remove the exact unneeded package set recorded during preflight.",
            parameter_schema={}, risk_level="medium", privileged=True,
            confirmation_policy="explicit-no-rollback", recovery_guidance="Reinstall removed packages explicitly if required.",
            rollback_supported=False, command_renderer=_render_autoremove,
            preflight_checker=_preflight_autoremove, verifier=_verify_autoremove,
        ),
        ActionDefinition(
            id="create-recovery-point",
            capability_id="recovery.snapshot.create",
            title="Create recovery point",
            description="Create and verify one Timeshift or Snapper recovery point.",
            parameter_schema={
                "backend": {"type": "string", "required": True},
                "description": {"type": "string", "required": True},
            },
            risk_level="low", privileged=True, confirmation_policy="explicit",
            recovery_guidance="Recovery-point creation does not restore or delete existing snapshots.",
            rollback_supported=True, command_renderer=_render_recovery_point,
            preflight_checker=_preflight_recovery_point, verifier=_verify_recovery_point,
            parameter_validator=_validate_recovery_point,
        ),
        _manual_definition(
            "enable-rpm-fusion",
            "Enable RPM Fusion",
            "RPM Fusion enablement requires distribution-specific repository review in v18.",
            "Follow the RPM Fusion Fedora setup guide, verify repository URLs, and return to Software after completion.",
            ("repositories", "packages"),
        ),
        _manual_definition(
            "install-multimedia-codecs",
            "Install multimedia codecs",
            "Codec groups vary by enabled repositories and remain guided manual work in v18.",
            "Review the exact package groups and repository trust before installing codecs manually.",
            ("packages", "multimedia"),
        ),
        _manual_definition(
            "enable-flathub",
            "Enable Flathub",
            "Adding a new software trust source remains a guided manual operation in v18.",
            "Verify the Flathub repository URL and scope before adding the remote manually.",
            ("flatpak-remotes",),
        ),
        _manual_definition(
            "enable-loofi-copr",
            "Enable Loofi COPR",
            "Enabling a third-party COPR remains a guided manual operation in v18.",
            "Inspect the COPR project and signing metadata before enabling it manually.",
            ("repositories", "packages"),
        ),
        *_manual_boundary_definitions(),
    ]


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
        parameter_schema={name: dict(schema) for name, schema in (parameter_schema or {}).items()},
        risk_level="medium",
        privileged=False,
        confirmation_policy="explicit-no-rollback",
        recovery_guidance=recovery_guidance,
        rollback_supported=False,
        command_renderer=lambda _parameters, _runtime: [],
        preflight_checker=lambda _parameters, _runtime: _blocked("manual_only", description),
        verifier=lambda _run, _plan, _runtime: VerificationDecision.failed("Manual-only actions are never executed by Loofi."),
        operation_class="manual_only",
        supported_variants=frozenset({"traditional", "atomic"}),
        reboot_policy=reboot_policy,
        affected_resources=affected_resources,
        parameter_validator=parameter_validator,
    )


def _manual_boundary_definitions() -> list[ActionDefinition]:
    specs = (
        ("remove-old-kernels", "Remove old kernels", "Kernel removal requires manual boot and rollback review.", ("packages", "boot-state")),
        ("enable-mac-randomization", "Enable MAC randomization", "Persistent NetworkManager privacy configuration remains guided manual work.", ("networkmanager-config",)),
        ("disable-mac-randomization", "Disable MAC randomization", "Persistent NetworkManager privacy configuration remains guided manual work.", ("networkmanager-config",)),
        ("set-battery-limit-80", "Set battery charge limit to 80%", "Persistent battery sysfs and service changes remain guided manual work.", ("battery", "systemd-unit")),
        ("set-battery-limit-100", "Set battery charge limit to 100%", "Persistent battery sysfs and service changes remain guided manual work.", ("battery", "systemd-unit")),
        ("restart-audio-session", "Restart audio session", "Restarting user audio services remains an explicit session operation.", ("user-services", "audio")),
        ("apply-grub-config", "Apply boot-loader configuration", "Boot-loader regeneration remains guided manual work in v18.", ("bootloader", "boot-state")),
        ("start-usbguard-service", "Start USBGuard service", "USBGuard service activation remains guided manual work in v18.", ("usbguard", "system-services")),
        ("enable-firewall-service", "Enable firewall service", "Persistent firewall activation remains guided manual work in v18.", ("firewall", "system-services")),
        ("disable-firewall-service", "Disable firewall service", "Disabling the host firewall remains guided manual work in v18.", ("firewall", "system-services")),
        ("remove-fedora-telemetry", "Remove Fedora telemetry packages", "Telemetry package removal requires an exact package review in v18.", ("packages", "telemetry")),
        ("legacy-cli-manual-review", "Review legacy CLI operation", "Legacy host commands are never executed directly and require a named Action Center workflow.", ("host-system",)),
        ("legacy-ui-manual-review", "Review legacy interface operation", "This host operation has no executable Haven workflow and remains guided manual work.", ("host-system",)),
        ("remove-unused-flatpaks", "Remove unused Flatpak runtimes", "Flatpak runtime cleanup remains guided manual work until the exact unused set can be verified.", ("flatpak-runtimes",)),
        ("enroll-fingerprint", "Enroll fingerprint", "Authentication enrollment remains guided manual work in v18.", ("authentication", "fingerprint-reader")),
        ("generate-mok-key", "Generate MOK signing key", "Secure Boot key creation remains guided manual work in v18.", ("secure-boot", "signing-keys")),
        ("enroll-mok-key", "Enroll MOK signing key", "Secure Boot key enrollment requires guided reboot-time verification.", ("secure-boot", "mok-database")),
    )
    definitions = [
        _manual_definition(action_id, title, description, description, resources)
        for action_id, title, description, resources in specs
    ]
    definitions.extend(
        [
            _manual_definition(
                "local-profile-review",
                "Review imported local profile",
                "Imported profile data is validated and preserved as a non-executable Action Center review plan.",
                "Review each setting and use its owning first-party Action Center workflow; profiles never execute commands.",
                ("local-profiles", "host-system"),
                parameter_schema={
                    "profile": {"type": "string", "required": True},
                    "settings": {"type": "object", "required": True},
                },
                parameter_validator=_validate_local_profile,
            ),
            _manual_definition(
                "block-firewall-port",
                "Block firewall port",
                "Firewall rule changes require guided review until exact rollback verification is available.",
                "Review the selected port and protocol, then apply and verify the rule manually.",
                ("firewall", "network-ports"),
                parameter_schema={
                    "port": {"type": "integer", "required": True},
                    "protocol": {"type": "string", "required": True},
                    "zone": {"type": "string", "required": False},
                },
                parameter_validator=_validate_firewall_port,
            ),
            *public_boundary_definitions(),
            _manual_definition(
                "allow-usb-device",
                "Allow USB device",
                "Permanent USB device policy changes remain guided manual work in v18.",
                "Review the exact USBGuard device identifier before changing policy manually.",
                ("usbguard", "usb-devices"),
                parameter_schema={"device_id": {"type": "string", "required": True}},
                parameter_validator=_validate_usb_device,
            ),
            _manual_definition(
                "block-usb-device",
                "Block USB device",
                "Permanent USB device policy changes remain guided manual work in v18.",
                "Review the exact USBGuard device identifier before changing policy manually.",
                ("usbguard", "usb-devices"),
                parameter_schema={"device_id": {"type": "string", "required": True}},
                parameter_validator=_validate_usb_device,
            ),
            _manual_definition(
                "set-grub-timeout",
                "Set boot menu timeout",
                "Boot-loader configuration remains guided manual work in v18.",
                "Review the selected timeout and current boot configuration before editing GRUB manually.",
                ("bootloader",),
                parameter_schema={"seconds": {"type": "integer", "required": True}},
                parameter_validator=_validate_grub_timeout,
            ),
            _choice_manual_definition(
                "set-cpu-governor",
                "Set CPU governor",
                "governor",
                {"conservative", "ondemand", "performance", "powersave", "schedutil", "userspace"},
                ("cpu-governor",),
            ),
            _choice_manual_definition(
                "set-power-profile",
                "Set power profile",
                "profile",
                {"power-saver", "balanced", "performance"},
                ("power-profile",),
            ),
            _choice_manual_definition(
                "set-gpu-mode",
                "Set GPU mode",
                "mode",
                {"integrated", "hybrid", "nvidia"},
                ("gpu-mode", "login-session"),
                reboot_policy="required",
            ),
            _manual_definition(
                "set-fan-speed",
                "Set fan control mode",
                "Direct fan-controller changes remain guided manual work in v18.",
                "Review hardware compatibility and thermal recovery guidance before applying fan changes manually.",
                ("fan-controller", "thermal-policy"),
                parameter_schema={"speed": {"type": "integer", "required": True}},
                parameter_validator=_validate_fan_speed,
            ),
            _choice_manual_definition(
                "install-developer-tool",
                "Install developer tool",
                "tool",
                {"nvm", "pyenv", "rustup", "vscode_cpp", "vscode_go", "vscode_python", "vscode_rust", "vscode_web"},
                ("user-development-environment",),
            ),
            _manual_definition(
                "apply-system-profile",
                "Apply system profile",
                "Profiles may combine host changes and must remain guided manual plans in v18.",
                "Review every setting in the selected local profile and create separate executable plans where available.",
                ("system-profile", "host-system"),
                parameter_schema={"profile": {"type": "string", "required": True}},
                parameter_validator=lambda values: _validate_identifier(values, "profile"),
            ),
            _manual_definition(
                "configure-hostname-privacy",
                "Configure DHCP hostname privacy",
                "Persistent NetworkManager connection changes remain guided manual work in v18.",
                "Review the exact connection and DHCP hostname policy before changing it manually.",
                ("network-connections", "dhcp"),
                parameter_schema={
                    "connection": {"type": "string", "required": True},
                    "hidden": {"type": "boolean", "required": True},
                },
                parameter_validator=_validate_hostname_privacy,
            ),
            _manual_definition(
                "configure-network-dns",
                "Configure connection DNS",
                "Connection-specific DNS changes remain guided manual work in v18.",
                "Review the exact connection and resolver addresses before changing NetworkManager manually.",
                ("network-connections", "dns"),
                parameter_schema={
                    "connection": {"type": "string", "required": True},
                    "dns": {"type": "string", "required": True},
                },
                parameter_validator=_validate_network_dns,
            ),
            _manual_definition(
                "service-control",
                "Control system service",
                "General service state changes remain guided manual work; failed-service restart has a separate verified workflow.",
                "Review the exact unit, scope, dependencies, and journal before changing service state manually.",
                ("system-services",),
                parameter_schema={
                    "service": {"type": "string", "required": True},
                    "action": {"type": "string", "required": True},
                    "scope": {"type": "string", "required": True},
                },
                parameter_validator=_validate_service_control,
            ),
            _manual_definition(
                "configure-kernel-parameter",
                "Configure kernel parameter",
                "Kernel command-line changes remain guided manual work in v18.",
                "Review the exact parameter and a tested boot recovery path before editing the kernel command line.",
                ("kernel-command-line", "boot-state"),
                parameter_schema={
                    "parameter": {"type": "string", "required": True},
                    "enabled": {"type": "boolean", "required": True},
                },
                parameter_validator=_validate_kernel_parameter,
                reboot_policy="required",
            ),
            _manual_definition(
                "restore-grub-backup",
                "Restore GRUB backup",
                "Boot-loader restoration is destructive and remains guided manual work in v18.",
                "Verify the selected backup outside the active boot path and retain recovery media before restoring manually.",
                ("bootloader", "boot-state"),
                parameter_schema={"backup": {"type": "string", "required": True}},
                parameter_validator=lambda values: _validate_identifier(values, "backup"),
                reboot_policy="required",
            ),
            _manual_definition(
                "configure-zram",
                "Configure ZRAM",
                "Persistent ZRAM generator changes remain guided manual work in v18.",
                "Review memory pressure and recovery guidance before changing ZRAM configuration manually.",
                ("zram", "system-services"),
                parameter_schema={
                    "size_percent": {"type": "integer", "required": True},
                    "algorithm": {"type": "string", "required": True},
                },
                parameter_validator=_validate_zram,
                reboot_policy="may_require",
            ),
            _manual_definition(
                "set-battery-limit",
                "Set battery charge limit",
                "Persistent battery charge thresholds require hardware-specific verification.",
                "Review hardware support and the exact threshold before applying the change manually.",
                ("battery", "power-supply"),
                parameter_schema={"limit": {"type": "integer", "required": True}},
                parameter_validator=lambda values: _validate_integer_range(
                    values, "limit", 50, 100
                ),
            ),
            _manual_definition(
                "optimize-dnf-config",
                "Review DNF configuration tuning",
                "Persistent package-manager configuration remains guided manual work.",
                "Review existing DNF5 configuration and remove conflicting values before editing it manually.",
                ("dnf-config",),
            ),
            _manual_definition(
                "enable-tcp-bbr",
                "Review TCP BBR enablement",
                "Persistent kernel networking changes require kernel and recovery verification.",
                "Verify BBR kernel support and retain the previous sysctl configuration before changing it manually.",
                ("kernel-tunables", "network-stack"),
            ),
            _manual_definition(
                "install-gamemode",
                "Review GameMode installation",
                "Package and group membership changes require separate verification.",
                "Review the Fedora package and exact user group membership before applying changes manually.",
                ("packages", "user-groups"),
            ),
            _manual_definition(
                "set-swappiness",
                "Set system swappiness",
                "Persistent memory-policy changes require workload-specific verification.",
                "Review memory pressure and retain the previous sysctl value before changing it manually.",
                ("kernel-tunables", "memory-policy"),
                parameter_schema={"value": {"type": "integer", "required": True}},
                parameter_validator=lambda values: _validate_integer_range(
                    values, "value", 0, 100
                ),
            ),
        ]
    )
    return definitions


def _choice_manual_definition(
    action_id: str,
    title: str,
    parameter: str,
    allowed: set[str],
    resources: tuple[str, ...],
    *,
    reboot_policy: Literal["none", "may_require", "required"] = "none",
) -> ActionDefinition:
    description = f"{title} remains guided manual work until preflight and verification are hardware-aware."
    return _manual_definition(
        action_id,
        title,
        description,
        description,
        resources,
        parameter_schema={parameter: {"type": "string", "required": True}},
        parameter_validator=lambda values: _validate_choice(values, parameter, allowed),
        reboot_policy=reboot_policy,
    )


def _validate_choice(parameters: Mapping[str, Any], name: str, allowed: set[str]) -> PolicyDecision:
    if parameters.get(name) not in allowed:
        return _blocked("invalid_choice", f"Parameter '{name}' must be one of: {', '.join(sorted(allowed))}.")
    return _allowed("parameters_valid", f"Parameter '{name}' is valid.")


def _validate_integer_range(
    parameters: Mapping[str, Any],
    name: str,
    minimum: int,
    maximum: int,
) -> PolicyDecision:
    value = parameters.get(name)
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not minimum <= value <= maximum
    ):
        return _blocked(
            f"invalid_{name}",
            f"Parameter '{name}' must be an integer between {minimum} and {maximum}.",
        )
    return _allowed("parameters_valid", f"Parameter '{name}' is valid.")


def _validate_fan_speed(parameters: Mapping[str, Any]) -> PolicyDecision:
    speed = parameters.get("speed")
    if not isinstance(speed, int) or isinstance(speed, bool) or not -1 <= speed <= 100:
        return _blocked("invalid_fan_speed", "Fan speed must be -1 for automatic mode or 0-100 percent.")
    return _allowed("parameters_valid", "Fan control value is valid.")


def _validate_identifier(parameters: Mapping[str, Any], name: str) -> PolicyDecision:
    value = parameters.get(name)
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        return _blocked("invalid_identifier", f"Parameter '{name}' contains rejected characters.")
    return _allowed("parameters_valid", f"Parameter '{name}' is valid.")


def _validate_hostname_privacy(parameters: Mapping[str, Any]) -> PolicyDecision:
    connection = parameters.get("connection")
    hidden = parameters.get("hidden")
    if not isinstance(connection, str) or not _DESCRIPTION_PATTERN.fullmatch(connection):
        return _blocked("invalid_connection", "Connection name must contain 1-80 printable characters.")
    if not isinstance(hidden, bool):
        return _blocked("invalid_privacy_value", "Hostname privacy value must be boolean.")
    return _allowed("parameters_valid", "Hostname privacy parameters are valid.")


def _validate_network_dns(parameters: Mapping[str, Any]) -> PolicyDecision:
    connection = parameters.get("connection")
    dns = parameters.get("dns")
    if not isinstance(connection, str) or not _DESCRIPTION_PATTERN.fullmatch(connection):
        return _blocked("invalid_connection", "Connection name must contain 1-80 printable characters.")
    if not isinstance(dns, str) or not re.fullmatch(r"(?:auto|[0-9A-Fa-f:.]+(?:[ ,]+[0-9A-Fa-f:.]+)*)", dns):
        return _blocked("invalid_dns", "DNS value must be auto or a comma-separated list of IP addresses.")
    return _allowed("parameters_valid", "DNS parameters are valid.")


def _validate_service_control(parameters: Mapping[str, Any]) -> PolicyDecision:
    action = _validate_choice(
        parameters,
        "action",
        {"start", "stop", "restart", "enable", "disable", "mask", "unmask"},
    )
    if not action.allowed:
        return action
    if parameters.get("scope") not in {"system", "user"}:
        return _blocked("invalid_service_scope", "Service scope must be system or user.")
    return _allowed("parameters_valid", "Service control parameters are valid.")


def _validate_kernel_parameter(parameters: Mapping[str, Any]) -> PolicyDecision:
    parameter = parameters.get("parameter")
    enabled = parameters.get("enabled")
    if not isinstance(parameter, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._=-]{0,127}", parameter):
        return _blocked("invalid_kernel_parameter", "Kernel parameter contains rejected characters.")
    if not isinstance(enabled, bool):
        return _blocked("invalid_kernel_state", "Kernel parameter state must be boolean.")
    return _allowed("parameters_valid", "Kernel parameter request is valid.")


def _validate_zram(parameters: Mapping[str, Any]) -> PolicyDecision:
    size = parameters.get("size_percent")
    algorithm = parameters.get("algorithm")
    if not isinstance(size, int) or isinstance(size, bool) or not 10 <= size <= 200:
        return _blocked("invalid_zram_size", "ZRAM size must be between 10 and 200 percent.")
    if algorithm not in {"lzo", "lzo-rle", "lz4", "zstd"}:
        return _blocked("invalid_zram_algorithm", "Unsupported ZRAM algorithm.")
    return _allowed("parameters_valid", "ZRAM parameters are valid.")


def _validate_firewall_port(parameters: Mapping[str, Any]) -> PolicyDecision:
    port = parameters.get("port")
    protocol = parameters.get("protocol")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        return _blocked("invalid_port", "Port must be an integer between 1 and 65535.")
    if protocol not in {"tcp", "udp"}:
        return _blocked("invalid_protocol", "Protocol must be tcp or udp.")
    zone = parameters.get("zone")
    if zone is not None and (
        not isinstance(zone, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", zone)
    ):
        return _blocked("invalid_zone", "Firewall zone contains rejected characters.")
    return _allowed("parameters_valid", "Firewall rule parameters are valid.")


def _validate_local_profile(parameters: Mapping[str, Any]) -> PolicyDecision:
    profile = parameters.get("profile")
    settings = parameters.get("settings")
    if not isinstance(profile, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", profile):
        return _blocked("invalid_profile", "The local profile name contains rejected characters.")
    try:
        validate_local_profile(settings)
    except ValueError as exc:
        return _blocked("invalid_profile", str(exc))
    return _allowed("parameters_valid", "Local profile parameters are valid.")


def _validate_usb_device(parameters: Mapping[str, Any]) -> PolicyDecision:
    device_id = parameters.get("device_id")
    if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", device_id):
        return _blocked("invalid_usb_device", "USB device identifier is invalid.")
    return _allowed("parameters_valid", "USB device identifier is valid.")


def _validate_grub_timeout(parameters: Mapping[str, Any]) -> PolicyDecision:
    seconds = parameters.get("seconds")
    if not isinstance(seconds, int) or isinstance(seconds, bool) or not 0 <= seconds <= 60:
        return _blocked("invalid_grub_timeout", "Boot timeout must be between 0 and 60 seconds.")
    return _allowed("parameters_valid", "Boot timeout is valid.")


def _application_definition(action_id: str, *, installing: bool) -> ActionDefinition:
    verb = "Install" if installing else "Remove"
    return ActionDefinition(
        id=action_id,
        capability_id=f"applications.{'install' if installing else 'remove'}",
        title=f"{verb} application",
        description=f"{verb} one validated Fedora package or Flatpak application.",
        parameter_schema={
            "source": {"type": "string", "required": True},
            "package_id": {"type": "string", "required": True},
        },
        risk_level="low" if installing else "medium",
        privileged=False,
        confirmation_policy="explicit" if installing else "explicit-no-rollback",
        recovery_guidance="Remove the application again." if installing else "Reinstall the exact application if removal was unintended.",
        rollback_supported=installing,
        command_renderer=lambda p, r: _render_application(p, r, installing=installing),
        preflight_checker=lambda p, r: _preflight_application(p, r, installing=installing),
        verifier=lambda run, plan, runtime: _verify_application(run, plan, runtime, installing=installing),
        parameter_validator=_validate_application,
        privilege_resolver=lambda p, _r: p.get("source") == "fedora",
    )


def _validate_application(parameters: Mapping[str, Any]) -> PolicyDecision:
    source = parameters.get("source")
    package_id = parameters.get("package_id")
    if source not in {"fedora", "flatpak"}:
        return _blocked("invalid_application_source", "Only Fedora RPM and Flatpak sources are supported.")
    pattern = _FLATPAK_PATTERN if source == "flatpak" else _PACKAGE_PATTERN
    if not isinstance(package_id, str) or not pattern.fullmatch(package_id) or package_id.startswith("-"):
        return _blocked("invalid_package_id", "The application identifier is invalid or option-like.")
    return _allowed("parameters_valid", "Application parameters are valid.")


def _validate_journal(parameters: Mapping[str, Any]) -> PolicyDecision:
    days = parameters.get("days")
    if not isinstance(days, int) or isinstance(days, bool) or days not in _ALLOWED_RETENTION:
        return _blocked("invalid_retention", "Journal retention must be 7, 14, or 30 days.")
    return _allowed("parameters_valid", "Journal retention is valid.")


def _validate_recovery_point(parameters: Mapping[str, Any]) -> PolicyDecision:
    backend = parameters.get("backend")
    description = parameters.get("description")
    if backend not in _ALLOWED_BACKENDS:
        return _blocked("invalid_snapshot_backend", "Only Timeshift and Snapper are executable recovery backends.")
    if not isinstance(description, str) or not _DESCRIPTION_PATTERN.fullmatch(description.strip()):
        return _blocked("invalid_snapshot_description", "Description must contain 1-80 printable characters.")
    return _allowed("parameters_valid", "Recovery-point parameters are valid.")


def _preflight_flatpak_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    result, refs = _query_flatpak_updates(runtime)
    if not result.success:
        return _blocked("flatpak_query_failed", "Flatpak updates could not be queried.")
    if not refs:
        return _blocked("no_flatpak_updates", "No Flatpak updates are currently available.")
    return _allowed("preflight_ok", f"{len(refs)} Flatpak refs are ready.", refs=refs)


def _render_flatpak_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    result, refs = _query_flatpak_updates(runtime)
    if not result.success or not refs:
        raise ValueError("Flatpak update candidates are unavailable.")
    return ["flatpak", "update", "--noninteractive", "--assumeyes", *[item["id"] for item in refs]]


def _query_flatpak_updates(runtime: ActionRuntime) -> tuple[ActionResult, list[dict[str, str]]]:
    result = runtime.execute_read_only(
        ["flatpak", "remote-ls", "--updates", "--columns=ref,commit"],
        action_id="update-flatpaks-candidates",
        timeout=90,
    )
    return result, _tab_records(result.stdout)


def _verify_flatpak_update(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    failed = []
    for record in plan.policy_decision.facts.get("refs", []):
        if not isinstance(record, dict):
            continue
        ref, expected = str(record.get("id", "")), str(record.get("value", ""))
        result = runtime.execute_read_only(["flatpak", "info", "--show-commit", ref], action_id="update-flatpaks-verify-ref", timeout=30)
        if not result.success or (expected and result.stdout.strip() != expected):
            failed.append(ref)
    if failed:
        return VerificationDecision.failed("One or more planned Flatpak refs could not be verified.", failed_refs=failed)
    return VerificationDecision.succeeded("All planned Flatpak refs were verified.")


def _preflight_firmware_update(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    result = runtime.execute_read_only(["fwupdmgr", "get-updates", "--json"], action_id="update-firmware-candidates", timeout=90)
    devices = _firmware_records(_json_payload(result))
    if not result.success:
        return _blocked("firmware_query_failed", "Firmware updates could not be queried.")
    if not devices:
        return _blocked("no_firmware_updates", "No firmware updates are currently available.")
    return _allowed("preflight_ok", f"{len(devices)} firmware updates are ready.", devices=devices)


def _verify_firmware_update(run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    result = runtime.execute_read_only(["fwupdmgr", "get-history", "--json"], action_id="update-firmware-verify-history", timeout=60)
    if not result.success:
        return VerificationDecision.failed("Firmware history could not be queried.")
    history_text = json.dumps(_json_payload(result), sort_keys=True)
    missing = []
    for item in plan.policy_decision.facts.get("devices", []):
        if not isinstance(item, Mapping):
            continue
        identity = [str(item.get("guid", "")), str(item.get("version", ""))]
        checksum = str(item.get("checksum", ""))
        if not all(value and value in history_text for value in identity) or (checksum and checksum not in history_text):
            missing.append(dict(item))
    if not missing:
        return VerificationDecision.succeeded("Firmware history contains every planned update.")
    if _runtime_boot_id(runtime) == run.execution_boot_id:
        return VerificationDecision.awaiting_reboot("Firmware application is awaiting reboot verification.", pending_devices=missing)
    return VerificationDecision.failed("The expected firmware result was not recorded after reboot.", missing_devices=missing)


def _render_application(parameters: Mapping[str, Any], runtime: ActionRuntime, *, installing: bool) -> list[str]:
    package_id = str(parameters["package_id"])
    if parameters["source"] == "flatpak":
        action = "install" if installing else "uninstall"
        vector = ["flatpak", action, "--noninteractive", "--assumeyes"]
        if installing:
            vector.append("flathub")
        return [*vector, package_id]
    if runtime.is_atomic():
        return ["rpm-ostree", "install" if installing else "uninstall", package_id]
    manager = runtime.package_manager()
    return [manager if manager in {"dnf", "dnf5"} else "dnf", "install" if installing else "remove", "-y", package_id]


def _preflight_application(parameters: Mapping[str, Any], runtime: ActionRuntime, *, installing: bool) -> PolicyDecision:
    package_id, source = str(parameters["package_id"]), str(parameters["source"])
    if source == "flatpak":
        installed = runtime.execute_read_only(["flatpak", "info", package_id], action_id="application-installed", timeout=20).success
        target_commit = ""
        if installing:
            available = runtime.execute_read_only(
                ["flatpak", "remote-info", "--show-commit", "flathub", package_id],
                action_id="application-available",
                timeout=30,
            )
            if not available.success:
                return _blocked("application_unavailable", "The Flatpak application is unavailable from Flathub.")
            target_commit = available.stdout.strip()
        if installed == installing:
            return _blocked("application_state_unchanged", "The application already has the requested state.")
        return _allowed(
            "preflight_ok",
            "Flatpak application state is ready to change.",
            source=source,
            package_id=package_id,
            installed_before=installed,
            target_commit=target_commit,
        )
    if runtime.package_manager_busy():
        return _blocked("package_manager_busy", "Another package operation may be active.")
    installed_result = runtime.execute_read_only(
        ["rpm", "-q", "--qf", "%{name}|%{evr}|%{arch}\\n", package_id],
        action_id="application-installed",
        timeout=15,
    )
    installed = installed_result.success
    if installing:
        manager = runtime.package_manager()
        available = runtime.execute_read_only(
            [manager, "repoquery", "--available", "--latest-limit", "1", "--qf", "%{name}|%{evr}|%{arch}", package_id],
            action_id="application-available",
            timeout=60,
        )
        if not available.success or not available.stdout.strip():
            return _blocked("application_unavailable", "The Fedora package is unavailable from enabled repositories.")
    if installed == installing:
        return _blocked("application_state_unchanged", "The application already has the requested state.")
    return _allowed(
        "preflight_ok",
        "Fedora application state is ready to change.",
        source=source,
        package_id=package_id,
        installed_before=installed,
        atomic=runtime.is_atomic(),
        target_nevra=available.stdout.strip() if installing else "",
        installed_nevra=installed_result.stdout.strip() if installed else "",
    )


def _verify_application(run: ActionRun, plan: ActionPlan, runtime: ActionRuntime, *, installing: bool) -> VerificationDecision:
    package_id = str(plan.parameters["package_id"])
    if plan.parameters["source"] == "flatpak":
        result = runtime.execute_read_only(
            ["flatpak", "info", "--show-commit", package_id],
            action_id="application-verify",
            timeout=20,
        )
        expected = str(plan.policy_decision.facts.get("target_commit", ""))
        verified = result.success == installing and (not installing or not expected or result.stdout.strip() == expected)
        return VerificationDecision.succeeded("Flatpak application state was verified.") if verified else VerificationDecision.failed("Flatpak application state did not match the plan.")
    if runtime.is_atomic():
        status = runtime.execute_read_only(["rpm-ostree", "status", "--json"], action_id="application-verify-atomic", timeout=30)
        deployments = _json_payload(status).get("deployments", []) if status.success else []
        candidate = _pending_deployment(deployments)
        booted = next((item for item in deployments if isinstance(item, dict) and item.get("booted")), {})
        expected_checksum = str((((run.verification_result or {}).get("data") or {}).get("expected_checksum", "")))
        if _runtime_boot_id(runtime) == run.execution_boot_id:
            if not candidate or not candidate.get("checksum"):
                return VerificationDecision.failed("No staged Atomic deployment was found.")
            requested = set(str(item) for item in candidate.get("requested-packages", []))
            if (package_id in requested) != installing:
                return VerificationDecision.failed("The staged Atomic package request did not match the plan.")
            return VerificationDecision.awaiting_reboot(
                "The Atomic application change is staged.",
                package_id=package_id,
                expected_checksum=str(candidate.get("checksum", "")),
            )
        if expected_checksum and str(booted.get("checksum", "")) != expected_checksum:
            return VerificationDecision.awaiting_reboot("The expected Atomic deployment is not booted.", expected_checksum=expected_checksum)
    result = runtime.execute_read_only(
        ["rpm", "-q", "--qf", "%{name}|%{evr}|%{arch}\\n", package_id],
        action_id="application-verify-rpm",
        timeout=15,
    )
    expected_nevra = str(plan.policy_decision.facts.get("target_nevra", ""))
    verified = result.success == installing and (not installing or not expected_nevra or expected_nevra in _lines(result.stdout))
    return VerificationDecision.succeeded("Fedora application state was verified.") if verified else VerificationDecision.failed("Fedora application state did not match the plan.")


def _preflight_journal(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    result = runtime.execute_read_only(["journalctl", "--disk-usage", "--no-pager"], action_id="journal-usage-before", timeout=15)
    if not result.success:
        return _blocked("journal_usage_unavailable", "Journal usage could not be measured.")
    return _allowed("preflight_ok", "Journal usage was measured.", usage_bytes=_human_bytes(result.stdout))


def _verify_journal(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    result = runtime.execute_read_only(["journalctl", "--disk-usage", "--no-pager"], action_id="journal-usage-after", timeout=15)
    before, after = int(plan.policy_decision.facts.get("usage_bytes", 0)), _human_bytes(result.stdout)
    if not result.success or (before > 0 and after > before):
        return VerificationDecision.failed("Journal retention could not be verified.", before_bytes=before, after_bytes=after)
    return VerificationDecision.succeeded("Journal retention and usage were verified.", before_bytes=before, after_bytes=after)


def _preflight_autoremove(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    if runtime.is_atomic():
        return _blocked("atomic_manual_only", "Package autoremove remains manual-only on Atomic Fedora.")
    if runtime.package_manager_busy():
        return _blocked("package_manager_busy", "Another package operation may be active.")
    manager = runtime.package_manager()
    result = runtime.execute_read_only([manager, "repoquery", "--unneeded", "--installed", "--qf", "%{name}"], action_id="autoremove-candidates", timeout=60)
    packages = [item for item in _lines(result.stdout) if _PACKAGE_PATTERN.fullmatch(item)]
    if not result.success:
        return _blocked("autoremove_query_failed", "Unneeded packages could not be resolved.")
    if not packages:
        return _blocked("nothing_to_remove", "No unneeded packages are currently installed.")
    return _allowed("preflight_ok", f"{len(packages)} exact packages are ready for removal.", manager=manager, packages=packages)


def _render_autoremove(_parameters: Mapping[str, Any], runtime: ActionRuntime) -> list[str]:
    manager = runtime.package_manager()
    result = _preflight_autoremove({}, runtime)
    packages = [str(item) for item in result.facts.get("packages", [])]
    return [manager, "remove", "-y", *packages]


def _verify_autoremove(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    remaining = []
    for package in plan.policy_decision.facts.get("packages", []):
        if runtime.execute_read_only(["rpm", "-q", str(package)], action_id="autoremove-verify-package", timeout=15).success:
            remaining.append(str(package))
    manager = str(plan.policy_decision.facts.get("manager", runtime.package_manager()))
    health = runtime.execute_read_only([manager, "check"], action_id="autoremove-verify-health", timeout=120)
    if remaining or not health.success:
        return VerificationDecision.failed("Package removal verification failed.", remaining_packages=remaining)
    return VerificationDecision.succeeded("Every planned package removal was verified.")


def _render_recovery_point(parameters: Mapping[str, Any], _runtime: ActionRuntime) -> list[str]:
    backend, description = str(parameters["backend"]), str(parameters["description"]).strip()
    if backend == "timeshift":
        return ["timeshift", "--create", "--comments", description]
    return ["snapper", "create", "--description", description, "--type", "single"]


def _preflight_recovery_point(parameters: Mapping[str, Any], runtime: ActionRuntime) -> PolicyDecision:
    backend = str(parameters["backend"])
    vector = [backend, "--list"] if backend == "timeshift" else [backend, "list"]
    result = runtime.execute_read_only(vector, action_id="recovery-point-before", timeout=30)
    if not result.success:
        return _blocked("snapshot_backend_unavailable", f"{backend} could not list recovery points.")
    return _allowed("preflight_ok", f"{backend} is ready.", backend=backend, before_lines=_lines(result.stdout))


def _verify_recovery_point(_run: ActionRun, plan: ActionPlan, runtime: ActionRuntime) -> VerificationDecision:
    backend, description = str(plan.parameters["backend"]), str(plan.parameters["description"]).strip()
    vector = [backend, "--list"] if backend == "timeshift" else [backend, "list"]
    result = runtime.execute_read_only(vector, action_id="recovery-point-after", timeout=30)
    before, after = set(plan.policy_decision.facts.get("before_lines", [])), set(_lines(result.stdout))
    added = after - before
    if result.success and any(description in line for line in added):
        return VerificationDecision.succeeded("The recovery point was created and listed.", backend=backend, added=sorted(added))
    return VerificationDecision.failed("The new recovery point could not be identified after creation.")


def _allowed(code: str, explanation: str, **facts: Any) -> PolicyDecision:
    return PolicyDecision(True, code, explanation, facts=facts)


def _blocked(code: str, explanation: str) -> PolicyDecision:
    return PolicyDecision(False, code, explanation, "Review the current state and create a fresh plan.")


def _json_payload(result: ActionResult) -> dict[str, Any]:
    if not result.success:
        return {}
    try:
        payload = json.loads(result.stdout or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {"items": payload}


def _lines(value: str) -> list[str]:
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _tab_records(value: str) -> list[dict[str, str]]:
    records = []
    for line in _lines(value):
        parts = line.split("\t", 1)
        records.append({"id": parts[0], "value": parts[1] if len(parts) > 1 else ""})
    return records


def _firmware_records(payload: Any) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            guid = value.get("Guid") or value.get("DeviceId") or value.get("device_id")
            version = value.get("Version") or value.get("version")
            if guid and version:
                records.append({"guid": str(guid), "version": str(version), "checksum": str(value.get("Checksum") or value.get("checksum") or "")})
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    unique = {(item["guid"], item["version"]): item for item in records}
    return list(unique.values())


def _human_bytes(value: str) -> int:
    match = re.search(r"(\d+(?:\.\d+)?)\s*([KMGT]?)(?:i?B|bytes?)", str(value), re.IGNORECASE)
    if not match:
        return 0
    factor = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[match.group(2).upper()]
    return int(float(match.group(1)) * factor)


def _runtime_boot_id(runtime: ActionRuntime) -> str:
    reader = getattr(runtime, "boot_id", None)
    return str(reader() if callable(reader) else "").strip()


def _pending_deployment(deployments: Any) -> dict[str, Any]:
    if not isinstance(deployments, list):
        return {}
    for marker in ("staged", "pending"):
        candidate = next(
            (item for item in deployments if isinstance(item, dict) and item.get(marker) and not item.get("booted")),
            None,
        )
        if candidate is not None:
            return candidate
    return {}
