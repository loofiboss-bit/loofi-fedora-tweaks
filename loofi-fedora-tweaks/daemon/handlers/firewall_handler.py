"""Firewall and port-audit daemon handlers."""

from __future__ import annotations

from services.network.ports import PortAuditor
from services.security.firewall import FirewallManager

from daemon.validators import validate_port, validate_protocol, validate_zone


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
    def open_port(port: str, protocol: str = "tcp", zone: str = "", permanent: bool = True) -> dict:
        result = FirewallManager.open_port_local(
            validate_port(port),
            validate_protocol(protocol),
            validate_zone(zone),
            permanent=bool(permanent),
        )
        return {"success": result.success, "message": result.message}

    @staticmethod
    def close_port(port: str, protocol: str = "tcp", zone: str = "", permanent: bool = True) -> dict:
        result = FirewallManager.close_port_local(
            validate_port(port),
            validate_protocol(protocol),
            validate_zone(zone),
            permanent=bool(permanent),
        )
        return {"success": result.success, "message": result.message}

    @staticmethod
    def start_firewall() -> dict:
        result = FirewallManager.start_firewall_local()
        return {"success": result.success, "message": result.message}

    @staticmethod
    def stop_firewall() -> dict:
        result = FirewallManager.stop_firewall_local()
        return {"success": result.success, "message": result.message}

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

