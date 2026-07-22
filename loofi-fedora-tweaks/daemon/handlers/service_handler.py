"""System and service-related daemon handlers."""

from __future__ import annotations

from services.system.services import ServiceManager, UnitScope
from services.system.system import SystemManager

from daemon.validators import (
    validate_delay_seconds,
    validate_description,
    validate_hostname,
    validate_unit_filter,
    validate_unit_name,
    validate_unit_scope,
)
from daemon.plan_boundary import create_manual_plan, create_plan


class ServiceHandler:
    """Serve system and service operations for IPC callers."""

    @staticmethod
    def reboot(description: str = "", delay_seconds: int = 0) -> dict:
        valid_description = validate_description(description)
        valid_delay_seconds = validate_delay_seconds(delay_seconds)
        return create_manual_plan(
            "reboot",
            {"description": valid_description, "delay_seconds": valid_delay_seconds},
        )

    @staticmethod
    def shutdown(description: str = "", delay_seconds: int = 0) -> dict:
        valid_description = validate_description(description)
        valid_delay_seconds = validate_delay_seconds(delay_seconds)
        return create_manual_plan(
            "shutdown",
            {"description": valid_description, "delay_seconds": valid_delay_seconds},
        )

    @staticmethod
    def suspend(description: str = "") -> dict:
        valid_description = validate_description(description)
        return create_manual_plan("suspend", {"description": valid_description})

    @staticmethod
    def update_grub(description: str = "") -> dict:
        valid_description = validate_description(description)
        return create_manual_plan("update-grub", {"description": valid_description})

    @staticmethod
    def set_hostname(hostname: str, description: str = "") -> dict:
        valid_hostname = validate_hostname(hostname)
        valid_description = validate_description(description)
        return create_manual_plan(
            "set-hostname",
            {"hostname": valid_hostname, "description": valid_description},
        )

    @staticmethod
    def has_pending_reboot() -> bool:
        """Return pending-reboot state from local system reads.

        v2.12.0 TASK-003 contract:
        - Daemon handlers must not re-enter daemon-client IPC methods.
        - Use local SystemManager read path for deterministic daemon behavior.
        """
        return bool(SystemManager.has_pending_deployment())

    @staticmethod
    def get_package_manager() -> str:
        """Return package manager via local system detection.

        v2.12.0 TASK-003 contract:
        - Use local SystemManager read path inside daemon process.
        - Avoid recursive daemon-client calls.
        """
        return str(SystemManager.get_package_manager())

    @staticmethod
    def get_variant_name() -> str:
        """Return Fedora variant name via local system detection.

        v2.12.0 TASK-003 contract:
        - Use local SystemManager read path inside daemon process.
        - Avoid recursive daemon-client calls.
        """
        return str(SystemManager.get_variant_name())

    @staticmethod
    def list_units(scope: str = "user", filter_type: str = "all") -> list[dict[str, str | bool]]:
        valid_scope = validate_unit_scope(scope)
        valid_filter_type = validate_unit_filter(filter_type)
        parsed_scope = (
            UnitScope.SYSTEM if valid_scope == "system" else UnitScope.USER
        )
        units = ServiceManager.list_units(parsed_scope, valid_filter_type)
        return [
            {
                "name": unit.name,
                "state": unit.state.value,
                "scope": unit.scope.value,
                "description": unit.description,
                "is_gaming": unit.is_gaming,
            }
            for unit in units
        ]

    @staticmethod
    def start_unit(name: str, scope: str = "user") -> dict[str, str | bool]:
        valid_name = validate_unit_name(name)
        valid_scope = validate_unit_scope(scope)
        return create_manual_plan(
            "service-start",
            {"service": valid_name, "scope": valid_scope},
        )

    @staticmethod
    def stop_unit(name: str, scope: str = "user") -> dict[str, str | bool]:
        valid_name = validate_unit_name(name)
        valid_scope = validate_unit_scope(scope)
        return create_manual_plan(
            "service-stop",
            {"service": valid_name, "scope": valid_scope},
        )

    @staticmethod
    def restart_unit(name: str, scope: str = "user") -> dict[str, str | bool]:
        valid_name = validate_unit_name(name)
        valid_scope = validate_unit_scope(scope)
        if valid_scope == "system":
            return create_plan("restart-failed-service", {"service": valid_name})
        return create_manual_plan(
            "service-restart",
            {"service": valid_name, "scope": valid_scope},
        )

    @staticmethod
    def mask_unit(name: str, scope: str = "user") -> dict[str, str | bool]:
        valid_name = validate_unit_name(name)
        valid_scope = validate_unit_scope(scope)
        return create_manual_plan(
            "service-mask",
            {"service": valid_name, "scope": valid_scope},
        )

    @staticmethod
    def unmask_unit(name: str, scope: str = "user") -> dict[str, str | bool]:
        valid_name = validate_unit_name(name)
        valid_scope = validate_unit_scope(scope)
        return create_manual_plan(
            "service-unmask",
            {"service": valid_name, "scope": valid_scope},
        )

    @staticmethod
    def get_unit_status(name: str, scope: str = "user") -> str:
        valid_name = validate_unit_name(name)
        valid_scope = validate_unit_scope(scope)
        parsed_scope = UnitScope.SYSTEM if valid_scope == "system" else UnitScope.USER
        return ServiceManager.get_unit_status(valid_name, parsed_scope)
