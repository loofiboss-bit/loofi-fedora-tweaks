"""Firewall and port-audit daemon handlers."""

from __future__ import annotations

from services.network.ports import PortAuditor
from services.security.firewall import FirewallManager

from daemon.validators import (
    validate_boolean,
    validate_firewall_service,
    validate_port,
    validate_protocol,
    validate_rich_rule,
    validate_zone,
)
from daemon.plan_boundary import create_manual_plan


class FirewallHandler:
    """Serve firewall and port-auditing operations for IPC callers."""

    @staticmethod
    def get_status() -> dict:
        return FirewallManager.get_status_local().to_dict()

    @staticmethod
    def list_ports(zone: str = "") -> list[str]:
        return FirewallManager.list_ports_local(validate_zone(zone))

    @staticmethod
    def list_services(zone: str = "") -> list[str]:
        return FirewallManager.list_services_local(validate_zone(zone))

    @staticmethod
    def get_default_zone() -> str:
        return FirewallManager.get_default_zone_local()

    @staticmethod
    def get_zones() -> list[str]:
        return FirewallManager.get_zones_local()

    @staticmethod
    def get_active_zones() -> dict:
        return FirewallManager.get_active_zones_local()

    @staticmethod
    def list_rich_rules(zone: str = "") -> list[str]:
        return FirewallManager.list_rich_rules_local(validate_zone(zone))

    @staticmethod
    def set_default_zone(zone: str) -> dict:
        return create_manual_plan(
            "firewall-default-zone",
            {"zone": validate_zone(zone)},
        )

    @staticmethod
    def add_service(service: str, zone: str = "", permanent: bool = True) -> dict:
        valid_service = validate_firewall_service(service)
        valid_zone = validate_zone(zone)
        valid_permanent = validate_boolean(permanent, "permanent")
        return create_manual_plan(
            "firewall-add-service",
            {"service": valid_service, "zone": valid_zone, "permanent": valid_permanent},
        )

    @staticmethod
    def remove_service(service: str, zone: str = "", permanent: bool = True) -> dict:
        valid_service = validate_firewall_service(service)
        valid_zone = validate_zone(zone)
        valid_permanent = validate_boolean(permanent, "permanent")
        return create_manual_plan(
            "firewall-remove-service",
            {"service": valid_service, "zone": valid_zone, "permanent": valid_permanent},
        )

    @staticmethod
    def add_rich_rule(rule: str, zone: str = "", permanent: bool = True) -> dict:
        valid_rule = validate_rich_rule(rule)
        valid_zone = validate_zone(zone)
        valid_permanent = validate_boolean(permanent, "permanent")
        return create_manual_plan(
            "firewall-add-rich-rule",
            {"rule": valid_rule, "zone": valid_zone, "permanent": valid_permanent},
        )

    @staticmethod
    def remove_rich_rule(rule: str, zone: str = "", permanent: bool = True) -> dict:
        valid_rule = validate_rich_rule(rule)
        valid_zone = validate_zone(zone)
        valid_permanent = validate_boolean(permanent, "permanent")
        return create_manual_plan(
            "firewall-remove-rich-rule",
            {"rule": valid_rule, "zone": valid_zone, "permanent": valid_permanent},
        )

    @staticmethod
    def open_port(port: str, protocol: str = "tcp", zone: str = "", permanent: bool = True) -> dict:
        valid_permanent = validate_boolean(permanent, "permanent")
        return create_manual_plan(
            "firewall-open-port",
            {
                "port": validate_port(port),
                "protocol": validate_protocol(protocol),
                "zone": validate_zone(zone),
                "permanent": valid_permanent,
            },
        )

    @staticmethod
    def close_port(port: str, protocol: str = "tcp", zone: str = "", permanent: bool = True) -> dict:
        valid_permanent = validate_boolean(permanent, "permanent")
        return create_manual_plan(
            "firewall-close-port",
            {
                "port": validate_port(port),
                "protocol": validate_protocol(protocol),
                "zone": validate_zone(zone),
                "permanent": valid_permanent,
            },
        )

    @staticmethod
    def start_firewall() -> dict:
        return create_manual_plan("firewall-start")

    @staticmethod
    def stop_firewall() -> dict:
        return create_manual_plan("firewall-stop")

    @staticmethod
    def scan_ports() -> list[dict]:
        ports = PortAuditor.scan_ports_local()
        return [
            {
                "protocol": p.protocol,
                "port": p.port,
                "address": p.address,
                "process": p.process,
                "pid": p.pid,
                "is_risky": p.is_risky,
                "risk_reason": p.risk_reason,
            }
            for p in ports
        ]

    @staticmethod
    def security_score() -> dict:
        return PortAuditor.get_security_score_local()
