"""D-Bus service host for Loofi daemon."""

from __future__ import annotations

import logging

from daemon.contracts import error_response, ok_response
from daemon.handlers import FirewallHandler, NetworkHandler
from daemon.interfaces import BUS_NAME, INTERFACE, OBJECT_PATH
from daemon.validators import ValidationError

logger = logging.getLogger(__name__)

try:
    import dbus  # type: ignore[import-not-found]
    import dbus.service  # type: ignore[import-not-found]
except ImportError:
    dbus = None  # type: ignore[assignment]


class DaemonServiceBase:
    """Base class for fallback behavior when dbus is missing."""

    def Ping(self) -> str:  # noqa: N802
        return ok_response("pong")


if dbus is None:
    class DaemonService(DaemonServiceBase):
        """No-op service when dbus is unavailable."""

else:
    class DaemonService(dbus.service.Object):  # type: ignore[misc,valid-type]
        """D-Bus object exposing daemon methods."""

        def __init__(self, bus_name: "dbus.service.BusName"):
            super().__init__(bus_name, OBJECT_PATH)

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def Ping(self) -> str:  # noqa: N802
            return ok_response("pong")

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def GetCapabilities(self) -> str:  # noqa: N802
            return ok_response(
                {
                    "version": 1,
                    "network": [
                        "scan_wifi",
                        "load_vpn_connections",
                        "detect_current_dns",
                        "get_active_connection",
                        "check_hostname_privacy",
                        "reactivate_connection",
                    ],
                    "firewall": [
                        "get_status",
                        "list_ports",
                        "list_services",
                        "open_port",
                        "close_port",
                        "start_firewall",
                        "stop_firewall",
                    ],
                    "ports": ["scan_ports", "security_score"],
                }
            )

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def NetworkScanWifi(self) -> str:  # noqa: N802
            return self._safe_call(NetworkHandler.scan_wifi)

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def NetworkLoadVpnConnections(self) -> str:  # noqa: N802
            return self._safe_call(NetworkHandler.load_vpn_connections)

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def NetworkDetectCurrentDns(self) -> str:  # noqa: N802
            return self._safe_call(NetworkHandler.detect_current_dns)

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def NetworkGetActiveConnection(self) -> str:  # noqa: N802
            return self._safe_call(NetworkHandler.get_active_connection)

        @dbus.service.method(INTERFACE, in_signature="s", out_signature="s")
        def NetworkCheckHostnamePrivacy(self, connection_name: str) -> str:  # noqa: N802
            return self._safe_call(NetworkHandler.check_hostname_privacy, connection_name)

        @dbus.service.method(INTERFACE, in_signature="s", out_signature="s")
        def NetworkReactivateConnection(self, connection_name: str) -> str:  # noqa: N802
            return self._safe_call(NetworkHandler.reactivate_connection, connection_name)

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def FirewallGetStatus(self) -> str:  # noqa: N802
            return self._safe_call(FirewallHandler.get_status)

        @dbus.service.method(INTERFACE, in_signature="s", out_signature="s")
        def FirewallListPorts(self, zone: str = "") -> str:  # noqa: N802
            return self._safe_call(FirewallHandler.list_ports, zone)

        @dbus.service.method(INTERFACE, in_signature="s", out_signature="s")
        def FirewallListServices(self, zone: str = "") -> str:  # noqa: N802
            return self._safe_call(FirewallHandler.list_services, zone)

        @dbus.service.method(INTERFACE, in_signature="sssb", out_signature="s")
        def FirewallOpenPort(self, port: str, protocol: str, zone: str, permanent: bool) -> str:  # noqa: N802
            return self._safe_call(FirewallHandler.open_port, port, protocol, zone, permanent)

        @dbus.service.method(INTERFACE, in_signature="sssb", out_signature="s")
        def FirewallClosePort(self, port: str, protocol: str, zone: str, permanent: bool) -> str:  # noqa: N802
            return self._safe_call(FirewallHandler.close_port, port, protocol, zone, permanent)

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def FirewallStart(self) -> str:  # noqa: N802
            return self._safe_call(FirewallHandler.start_firewall)

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def FirewallStop(self) -> str:  # noqa: N802
            return self._safe_call(FirewallHandler.stop_firewall)

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def PortAuditScan(self) -> str:  # noqa: N802
            return self._safe_call(FirewallHandler.scan_ports)

        @dbus.service.method(INTERFACE, in_signature="", out_signature="s")
        def PortAuditSecurityScore(self) -> str:  # noqa: N802
            return self._safe_call(FirewallHandler.security_score)

        @staticmethod
        def _safe_call(func, *args):
            try:
                return ok_response(func(*args))
            except ValidationError as exc:
                return error_response("validation_error", str(exc))
            except (OSError, RuntimeError, ValueError, TypeError) as exc:
                logger.exception("Daemon method failure")
                return error_response("execution_error", str(exc))

