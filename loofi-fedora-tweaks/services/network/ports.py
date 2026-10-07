"""
Port Auditor - Network port security scanner.

Scans open ports, identifies listening services,
and provides firewall management via firewall-cmd.

Migrated from utils/ports.py in v2.0.0.
"""

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from services.ipc import daemon_client
from services.system.system import cached_which

logger = logging.getLogger(__name__)


@dataclass
class Result:
    """Operation result."""

    success: bool
    message: str
    data: Optional[dict] = None


@dataclass
class OpenPort:
    """Represents an open network port."""

    protocol: str  # tcp, udp
    port: int
    address: str
    process: str
    pid: int
    is_risky: bool = False
    risk_reason: str = ""


@dataclass(frozen=True)
class PortScanObservation:
    """One bounded port scan whose status distinguishes empty from unknown."""

    status: Literal["complete", "unavailable", "error", "stale"]
    ports: tuple[OpenPort, ...] = ()
    observed_at: str = ""
    error: str = ""


@dataclass(frozen=True)
class FirewallObservation:
    """Read-only firewalld state, with probe failures kept explicit."""

    status: Literal["running", "stopped", "unavailable", "error", "stale"]
    observed_at: str = ""
    error: str = ""


@dataclass(frozen=True)
class SecurityScoreObservation:
    """A limited port and firewall assessment, or an explicit unknown."""

    status: Literal["complete", "unknown"]
    score: int | None = None
    rating: str = "Unknown"
    open_ports: int | None = None
    risky_ports: int | None = None
    recommendations: tuple[str, ...] = ()
    observed_at: str = ""
    error: str = ""
    ports_status: str = "unknown"
    firewall_status: str = "unknown"


class PortAuditor:
    """
    Scans and audits open network ports.

    Features:
    - List all listening ports
    - Identify risky services
    - Close ports via firewall
    """

    # Known risky ports/services
    RISKY_PORTS = {
        22: ("SSH", "Remote access - ensure key auth only"),
        23: ("Telnet", "CRITICAL: Unencrypted, disable immediately"),
        21: ("FTP", "Unencrypted file transfer"),
        3306: ("MySQL", "Database exposed to network"),
        5432: ("PostgreSQL", "Database exposed to network"),
        27017: ("MongoDB", "Database - often unauth by default"),
        6379: ("Redis", "Cache - often unauth by default"),
        8080: ("HTTP Alt", "Common development server"),
        5900: ("VNC", "Remote desktop - ensure auth"),
        3389: ("RDP", "Windows remote desktop"),
        1433: ("MSSQL", "SQL Server exposed"),
        11211: ("Memcached", "Cache - often unauth"),
    }

    @staticmethod
    def _normalize_port(port: int) -> int:
        if not isinstance(port, int):
            raise ValueError("Port must be an integer")
        if port < 1 or port > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return port

    @staticmethod
    def _normalize_protocol(protocol: str) -> str:
        if not isinstance(protocol, str):
            raise ValueError("Protocol must be a string")
        normalized = protocol.strip().lower()
        if normalized not in {"tcp", "udp"}:
            raise ValueError("Protocol must be tcp or udp")
        return normalized

    @classmethod
    def scan_ports(cls) -> PortScanObservation:
        """Scan listening ports without treating a failed probe as empty."""
        observed_at = datetime.now(timezone.utc).isoformat()
        data = daemon_client.call_json("PortAuditScan")
        if isinstance(data, list):
            result: list[OpenPort] = []
            for row in data:
                try:
                    if not isinstance(row, dict):
                        raise ValueError("invalid port record")
                    port = cls._normalize_port(int(row.get("port", 0) or 0))
                    protocol = cls._normalize_protocol(str(row.get("protocol", ""))).upper()
                    result.append(
                        OpenPort(
                            protocol=protocol,
                            port=port,
                            address=str(row.get("address", "")),
                            process=str(row.get("process", "unknown")),
                            pid=int(row.get("pid", 0) or 0),
                            is_risky=bool(row.get("is_risky", False)),
                            risk_reason=str(row.get("risk_reason", "")),
                        )
                    )
                except (TypeError, ValueError, OverflowError) as exc:
                    return PortScanObservation("error", observed_at=observed_at, error=f"Invalid port scan response: {exc}")
            return PortScanObservation("complete", tuple(result), observed_at)
        return cls.scan_ports_local()

    @classmethod
    def scan_ports_local(cls) -> PortScanObservation:
        """Local scan via ss, preserving unavailable and error states."""
        observed_at = datetime.now(timezone.utc).isoformat()
        if not shutil.which("ss"):
            return PortScanObservation("unavailable", observed_at=observed_at, error="The ss network inspection tool is not installed.")
        ports = []

        try:
            # ss -tulwn: TCP/UDP listening with numeric ports
            result = subprocess.run(
                ["ss", "-tulwn"], capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return PortScanObservation("error", observed_at=observed_at, error=result.stderr.strip() or "The ss port scan failed.")

            for line in result.stdout.strip().split("\n")[1:]:  # Skip header
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) < 5:
                    return PortScanObservation("error", observed_at=observed_at, error="The ss port scan returned an incomplete row.")

                protocol = parts[0].lower()
                local_addr = parts[4]

                # Parse address:port
                if ":" in local_addr:
                    addr_parts = local_addr.rsplit(":", 1)
                    address = addr_parts[0]
                    try:
                        port = int(addr_parts[1])
                    except ValueError:
                        return PortScanObservation("error", observed_at=observed_at, error="The ss port scan returned an unreadable port number.")
                else:
                    return PortScanObservation("error", observed_at=observed_at, error="The ss port scan returned an unreadable address.")

                # Get process info
                process = "unknown"
                pid = 0

                # Check if risky
                is_risky = False
                risk_reason = ""

                if port in cls.RISKY_PORTS:
                    is_risky = True
                    risk_reason = cls.RISKY_PORTS[port][1]

                # World-exposed is risky
                if address in ["0.0.0.0", "*", "[::]", "::"]:
                    if port in cls.RISKY_PORTS:
                        is_risky = True
                        risk_reason = f"{cls.RISKY_PORTS[port][0]}: {cls.RISKY_PORTS[port][1]}"

                ports.append(
                    OpenPort(
                        protocol=protocol.replace(
                            "tcp", "TCP").replace("udp", "UDP"),
                        port=port,
                        address=address,
                        process=process,
                        pid=pid,
                        is_risky=is_risky,
                        risk_reason=risk_reason,
                    )
                )

            # Enhance with process info from ss -tulpn (requires sudo)
            cls._enhance_with_process_info(ports)

            return PortScanObservation("complete", tuple(ports), observed_at)

        except FileNotFoundError:
            return PortScanObservation("unavailable", observed_at=observed_at, error="The ss network inspection tool is not installed.")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Port scan failed: %s", e)
            return PortScanObservation("error", observed_at=observed_at, error=str(e) or "The ss port scan failed.")

    @classmethod
    def _enhance_with_process_info(cls, ports: list[OpenPort]):
        """Add process information to ports (best effort)."""
        try:
            result = subprocess.run(
                ["ss", "-tulpn"], capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return

            for line in result.stdout.strip().split("\n")[1:]:
                if not line.strip():
                    continue

                # Look for pattern: users:(("process",pid=123,...))
                match = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                if match:
                    process_name = match.group(1)
                    pid = int(match.group(2))

                    # Match to port
                    parts = line.split()
                    if len(parts) >= 5:
                        local_addr = parts[4]
                        if ":" in local_addr:
                            try:
                                port_num = int(local_addr.rsplit(":", 1)[1])
                                for p in ports:
                                    if p.port == port_num:
                                        p.process = process_name
                                        p.pid = pid
                                        break
                            except ValueError:
                                pass

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to enhance port info: %s", e)

    @classmethod
    def get_risky_ports(cls) -> PortScanObservation:
        """Filter risky ports without discarding the source observation status."""
        observation = cls.scan_ports()
        if observation.status != "complete":
            return observation
        return PortScanObservation(
            observation.status,
            tuple(port for port in observation.ports if port.is_risky),
            observation.observed_at,
        )

    @classmethod
    def observe_firewalld(cls) -> FirewallObservation:
        """Check whether firewalld is active without folding probe failure into stopped."""
        observed_at = datetime.now(timezone.utc).isoformat()
        status = daemon_client.call_json("FirewallGetStatus")
        if isinstance(status, dict) and isinstance(status.get("running"), bool):
            return FirewallObservation("running" if status["running"] else "stopped", observed_at)
        if not shutil.which("systemctl"):
            return FirewallObservation("unavailable", observed_at, "The systemd service inspection tool is not installed.")
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "firewalld"], capture_output=True, text=True, timeout=5
            )
            state = (getattr(result, "stdout", "") or "").strip().lower()
            if state == "active":
                return FirewallObservation("running", observed_at)
            if state == "inactive":
                return FirewallObservation("stopped", observed_at)
            return FirewallObservation("error", observed_at, result.stderr.strip() or "The firewalld state could not be determined.")
        except subprocess.TimeoutExpired:
            return FirewallObservation("error", observed_at, "Checking firewalld timed out.")
        except (subprocess.SubprocessError, OSError) as exc:
            return FirewallObservation("error", observed_at, str(exc) or "The firewalld state could not be checked.")

    @classmethod
    def is_firewalld_running(cls) -> bool:
        """Check if firewalld is running."""
        return cls.observe_firewalld().status == "running"

    @classmethod
    def is_firewalld_running_local(cls) -> bool:
        """Local firewalld state check."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "firewalld"], capture_output=True, text=True, timeout=5)
            return (getattr(result, "stdout", "") or "").strip().lower() == "active"
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to check firewalld status: %s", e)
            return False

    @classmethod
    def block_port(cls, port: int, protocol: str = "tcp") -> Result:
        """
        Block a port using firewall-cmd.

        Args:
            port: Port number to block
            protocol: tcp or udp
        """
        try:
            valid_port = cls._normalize_port(port)
            valid_protocol = cls._normalize_protocol(protocol)
        except ValueError as e:
            return Result(False, str(e))

        data = daemon_client.call_json(
            "FirewallClosePort", str(valid_port), valid_protocol, "", True
        )
        if isinstance(data, dict):
            return Result(bool(data.get("success", False)), str(data.get("message", "")))
        return cls.block_port_local(valid_port, valid_protocol)

    @classmethod
    def block_port_local(cls, port: int, protocol: str = "tcp") -> Result:
        """Local fallback for blocking a port."""
        try:
            valid_port = cls._normalize_port(port)
            valid_protocol = cls._normalize_protocol(protocol)
        except ValueError as e:
            return Result(False, str(e))

        if not cached_which("firewall-cmd"):
            return Result(False, "firewall-cmd not found")

        if not cls.is_firewalld_running_local():
            return Result(False, "firewalld is not running")

        try:
            # Remove from allowed (if present) and add to blocked
            subprocess.run(
                ["pkexec", "firewall-cmd", "--remove-port",
                    f"{valid_port}/{valid_protocol}", "--permanent"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Reload firewall
            subprocess.run(["pkexec", "firewall-cmd", "--reload"],
                           capture_output=True, text=True, timeout=30)

            return Result(True, f"Port {valid_port}/{valid_protocol} blocked")

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            return Result(False, f"Error: {e}")

    @classmethod
    def allow_port(cls, port: int, protocol: str = "tcp") -> Result:
        """
        Allow a port using firewall-cmd.

        Args:
            port: Port number to allow
            protocol: tcp or udp
        """
        try:
            valid_port = cls._normalize_port(port)
            valid_protocol = cls._normalize_protocol(protocol)
        except ValueError as e:
            return Result(False, str(e))

        data = daemon_client.call_json(
            "FirewallOpenPort", str(valid_port), valid_protocol, "", True
        )
        if isinstance(data, dict):
            return Result(bool(data.get("success", False)), str(data.get("message", "")))
        return cls.allow_port_local(valid_port, valid_protocol)

    @classmethod
    def allow_port_local(cls, port: int, protocol: str = "tcp") -> Result:
        """Local fallback for allowing a port."""
        try:
            valid_port = cls._normalize_port(port)
            valid_protocol = cls._normalize_protocol(protocol)
        except ValueError as e:
            return Result(False, str(e))

        if not cached_which("firewall-cmd"):
            return Result(False, "firewall-cmd not found")

        if not cls.is_firewalld_running_local():
            return Result(False, "firewalld is not running")

        try:
            result = subprocess.run(
                ["pkexec", "firewall-cmd", "--add-port",
                    f"{valid_port}/{valid_protocol}", "--permanent"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return Result(False, f"Failed: {result.stderr}")

            # Reload firewall
            subprocess.run(["pkexec", "firewall-cmd", "--reload"],
                           capture_output=True, text=True, timeout=30)

            return Result(True, f"Port {valid_port}/{valid_protocol} allowed")

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            return Result(False, f"Error: {e}")

    @classmethod
    def get_firewall_status(cls) -> dict:
        """Get firewall status and open ports."""
        status = daemon_client.call_json("FirewallGetStatus")
        if isinstance(status, dict):
            return {
                "running": bool(status.get("running", False)),
                "default_zone": str(status.get("default_zone", "unknown")),
                "allowed_ports": [str(x) for x in status.get("ports", [])],
                "allowed_services": [str(x) for x in status.get("services", [])],
            }
        return cls.get_firewall_status_local()

    @classmethod
    def get_firewall_status_local(cls) -> dict:
        """Local fallback for firewall status."""
        status = {"running": False, "default_zone": "unknown",
                  "allowed_ports": [], "allowed_services": []}

        if not cls.is_firewalld_running_local():
            return status

        status["running"] = True

        try:
            # Get default zone
            result = subprocess.run(
                ["firewall-cmd", "--get-default-zone"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                status["default_zone"] = result.stdout.strip()

            # Get allowed ports
            result = subprocess.run(
                ["firewall-cmd", "--list-ports"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                status["allowed_ports"] = result.stdout.strip().split()

            # Get allowed services
            result = subprocess.run(
                ["firewall-cmd", "--list-services"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                status["allowed_services"] = result.stdout.strip().split()

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to get firewall status: %s", e)

        return status

    @classmethod
    def get_security_score(cls) -> SecurityScoreObservation:
        """
        Calculate a simple security score based on open ports.

        Returns score from 0-100 and recommendations.
        """
        return cls.get_security_score_local()

    @classmethod
    def get_security_score_local(cls) -> SecurityScoreObservation:
        """Calculate a limited score only when both source observations are complete."""
        port_scan = cls.scan_ports()
        firewall = cls.observe_firewalld()
        if port_scan.status != "complete" or firewall.status not in {"running", "stopped"}:
            errors = [item.error for item in (port_scan, firewall) if item.error]
            return SecurityScoreObservation(
                "unknown", observed_at=port_scan.observed_at or firewall.observed_at,
                error=" ".join(errors) or "Port and firewall observations are incomplete.",
                ports_status=port_scan.status,
                firewall_status=firewall.status,
            )
        ports = port_scan.ports
        risky = [p for p in ports if p.is_risky]

        # Start with 100, deduct for issues
        score = 100
        recommendations = []

        # Deduct for each risky port
        for p in risky:
            if p.port == 23:  # Telnet is critical
                score -= 30
                recommendations.append(
                    f"CRITICAL: Disable Telnet on port {p.port}")
            elif p.port in [3306, 5432, 27017, 6379]:  # Databases
                score -= 15
                recommendations.append(
                    f"Database {p.process} on port {p.port} exposed")
            else:
                score -= 10
                recommendations.append(
                    f"Review {p.process} on port {p.port}: {p.risk_reason}")

        # Check if firewall is running
        if firewall.status == "stopped":
            score -= 20
            recommendations.append("Firewall is not running!")

        score = max(0, score)

        return SecurityScoreObservation(
            "complete", score, "Excellent" if score >= 90 else "Good" if score >= 70 else "Fair" if score >= 50 else "Poor",
            len(ports), len(risky), tuple(recommendations), port_scan.observed_at, "",
            port_scan.status, firewall.status,
        )
