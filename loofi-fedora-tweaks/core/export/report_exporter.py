"""
Report Exporter — v2.3.0 Insight
Exports system information as Markdown or HTML report.

v2.3.0: Added comprehensive diagnostic sections — failed services, journal errors,
pending updates, SELinux status, and network overview.
v42.0.0 Sentinel: Replaced subprocess.getoutput() with safe alternatives.
"""

import logging
import os
import platform
import socket
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReportExporter:
    """Exports system information in Markdown or HTML format."""

    @staticmethod
    def _read_file(path: str) -> Optional[str]:
        """Read a file safely, returning None on error.

        Args:
            path: Absolute file path.

        Returns:
            File contents stripped, or None on failure.
        """
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        except (OSError, IOError) as e:
            logger.debug("Failed to read %s: %s", path, e)
            return None

    @staticmethod
    def _run_cmd(cmd: list, timeout: int = 10) -> Optional[str]:
        """Run a command safely and return stdout.

        Args:
            cmd: Command as argument list (no shell).
            timeout: Subprocess timeout in seconds.

        Returns:
            Stripped stdout, or None on failure.
        """
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("Command %s failed: %s", cmd, e)
            return None

    @staticmethod
    def gather_system_info() -> Dict[str, str]:
        """
        Collect all system information for the report.

        Returns:
            Dictionary of system info key-value pairs.
        """
        info: Dict[str, str] = {}

        try:
            info["hostname"] = socket.gethostname()
        except OSError as e:
            logger.debug("Failed to get hostname: %s", e)
            info["hostname"] = "Unknown"

        info["kernel"] = platform.release() or "Unknown"

        fedora_release = ReportExporter._read_file("/etc/fedora-release")
        info["fedora_version"] = fedora_release or "Unknown"

        lscpu_out = ReportExporter._run_cmd(["lscpu"])
        cpu = "Unknown"
        if lscpu_out:
            for line in lscpu_out.splitlines():
                if "Model name" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        cpu = parts[1].strip()
                    break
        info["cpu"] = cpu

        free_out = ReportExporter._run_cmd(["free", "-h"])
        ram = "Unknown"
        if free_out:
            for line in free_out.splitlines():
                if line.startswith("Mem:"):
                    fields = line.split()
                    if len(fields) >= 3:
                        ram = f"{fields[1]} total, {fields[2]} used"
                    break
        info["ram"] = ram

        df_out = ReportExporter._run_cmd(["df", "-h", "/"])
        disk = "Unknown"
        if df_out:
            lines = df_out.splitlines()
            if len(lines) >= 2:
                fields = lines[1].split()
                if len(fields) >= 5:
                    disk = f"{fields[2]}/{fields[1]} ({fields[4]} used)"
        info["disk_root"] = disk

        uptime_out = ReportExporter._run_cmd(["uptime", "-p"])
        info["uptime"] = uptime_out or "Unknown"

        bat_cap = ReportExporter._read_file("/sys/class/power_supply/BAT0/capacity")
        if bat_cap is not None:
            bat_status = ReportExporter._read_file("/sys/class/power_supply/BAT0/status") or "Unknown"
            info["battery"] = f"{bat_cap}% ({bat_status})"
        else:
            info["battery"] = "No battery detected"

        info["architecture"] = platform.machine() or "Unknown"
        info["desktop"] = os.environ.get("XDG_CURRENT_DESKTOP", "Unknown")
        info["report_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return info

    @staticmethod
    def gather_services_info() -> List[Dict[str, str]]:
        """Collect failed systemd services.

        Returns:
            List of dicts with keys 'unit', 'load', 'active', 'sub', 'description'.
            Empty list if no failed units or if systemctl is unavailable.
        """
        out = ReportExporter._run_cmd(
            ["systemctl", "--failed", "--no-legend", "--no-pager"],
            timeout=15,
        )
        if not out:
            return []

        services: List[Dict[str, str]] = []
        for line in out.splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 4:
                services.append(
                    {
                        "unit": parts[0],
                        "load": parts[1],
                        "active": parts[2],
                        "sub": parts[3],
                        "description": parts[4] if len(parts) > 4 else "",
                    }
                )
        return services

    @staticmethod
    def gather_journal_errors() -> str:
        """Collect recent critical/error journal entries.

        Returns:
            Last 20 error/critical log lines as a single string,
            or empty string if none found or journalctl unavailable.
        """
        out = ReportExporter._run_cmd(
            ["journalctl", "-p", "3", "-n", "20", "--no-pager", "--output=short"],
            timeout=15,
        )
        return out or ""

    @staticmethod
    def gather_updates_info() -> str:
        """Check for pending package updates.

        Branches on whether the system is Atomic Fedora (rpm-ostree) or traditional (dnf).

        Returns:
            Human-readable string like '12 packages pending', 'Up to date', or 'Unknown'.
        """
        pm = "dnf"  # safe default for traditional Fedora
        try:
            from services.system.system import SystemManager  # type: ignore[import]

            is_atomic = SystemManager.is_atomic()
            pm = SystemManager.get_package_manager()
        except (ImportError, AttributeError):
            is_atomic = False

        if is_atomic:
            out = ReportExporter._run_cmd(["rpm-ostree", "status", "--json"], timeout=20)
            if out and '"transactions"' in out:
                return "Pending deployment available (rpm-ostree)"
            elif out:
                return "Up to date (rpm-ostree)"
            return "Unknown (rpm-ostree unavailable)"

        try:
            result = subprocess.run(
                [pm, "check-update", "-q", "--assumeno"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 100:
                update_lines = [
                    ln
                    for ln in result.stdout.strip().splitlines()
                    if ln and not ln.startswith("Last metadata")
                ]
                count = len(update_lines)
                return f"{count} package{'s' if count != 1 else ''} pending"
            elif result.returncode == 0:
                return "Up to date"
            return "Unknown (dnf returned unexpected status)"
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("dnf check-update failed: %s", e)
            return "Unknown (dnf unavailable)"

    @staticmethod
    def gather_selinux_info() -> Dict[str, str]:
        """Collect SELinux enforcement mode and recent AVC denials.

        Returns:
            Dict with keys 'mode' (e.g. 'Enforcing') and 'recent_denials'
            (last 10 AVC denial lines, may be empty string).
        """
        mode = ReportExporter._run_cmd(["getenforce"], timeout=5) or "Unknown"

        denials = ""
        raw = ReportExporter._run_cmd(
            ["ausearch", "-m", "AVC", "-ts", "today", "-i"],
            timeout=10,
        )
        if raw:
            lines = raw.splitlines()
            denials = "\n".join(lines[-10:]) if len(lines) > 10 else raw

        return {"mode": mode, "recent_denials": denials}

    @staticmethod
    def gather_network_info() -> Dict[str, str]:
        """Collect basic network overview — IP address, DNS servers, default gateway.

        Returns:
            Dict with keys 'ip_addresses', 'dns_servers', 'default_gateway'.
        """
        ip_out = ReportExporter._run_cmd(["ip", "-4", "addr", "show"], timeout=5)
        ip_addresses = ""
        if ip_out:
            addrs = []
            for line in ip_out.splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    parts = line.split()
                    if len(parts) >= 2:
                        addrs.append(parts[1])
            ip_addresses = ", ".join(addrs) if addrs else "None"

        dns_servers = "Unknown"
        resolv = ReportExporter._read_file("/etc/resolv.conf")
        if resolv:
            servers = []
            for line in resolv.splitlines():
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
            dns_servers = ", ".join(servers) if servers else "None"

        gateway_out = ReportExporter._run_cmd(["ip", "route", "show", "default"], timeout=5)
        default_gateway = "Unknown"
        if gateway_out:
            parts = gateway_out.split()
            if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                default_gateway = parts[2]

        return {
            "ip_addresses": ip_addresses,
            "dns_servers": dns_servers,
            "default_gateway": default_gateway,
        }

    @staticmethod
    def gather_all_diagnostics() -> Dict[str, Any]:
        """Gather all diagnostic data for a comprehensive report.

        Returns:
            Combined dict with 'system_info', 'services', 'journal_errors',
            'updates', 'selinux', and 'network' keys.
        """
        return {
            "system_info": ReportExporter.gather_system_info(),
            "services": ReportExporter.gather_services_info(),
            "journal_errors": ReportExporter.gather_journal_errors(),
            "updates": ReportExporter.gather_updates_info(),
            "selinux": ReportExporter.gather_selinux_info(),
            "network": ReportExporter.gather_network_info(),
        }

    @staticmethod
    def export_markdown(
        info: Optional[Dict[str, str]] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format diagnostic data as a Markdown report.

        Args:
            info: Legacy system info dict (key-value strings). Ignored when diagnostics provided.
            diagnostics: Full diagnostics dict from gather_all_diagnostics().
                         When provided, all diagnostic sections are included.

        Returns:
            Formatted Markdown string.
        """
        if diagnostics is not None:
            info = diagnostics.get("system_info") or {}
            services: List[Dict[str, str]] = diagnostics.get("services") or []
            journal_errors: str = diagnostics.get("journal_errors") or ""
            updates: str = diagnostics.get("updates") or "Unknown"
            selinux: Dict[str, str] = diagnostics.get("selinux") or {}
            network: Dict[str, str] = diagnostics.get("network") or {}
            has_diagnostics = True
        else:
            if info is None:
                info = ReportExporter.gather_system_info()
            services, journal_errors, updates = [], "", ""
            selinux, network = {}, {}
            has_diagnostics = False

        field_labels = {
            "hostname": "Hostname",
            "kernel": "Kernel",
            "fedora_version": "Fedora Version",
            "cpu": "CPU",
            "ram": "RAM",
            "disk_root": "Disk Usage (/)",
            "uptime": "Uptime",
            "battery": "Battery",
            "architecture": "Architecture",
            "desktop": "Desktop Environment",
        }

        lines = [
            "# System Report — Loofi Fedora Tweaks",
            "",
            f"**Generated:** {info.get('report_date', 'Unknown')}",
            "",
            "## System Information",
            "",
            "| Property | Value |",
            "|----------|-------|",
        ]

        for key, label in field_labels.items():
            lines.append(f"| {label} | {info.get(key, 'Unknown')} |")

        if has_diagnostics:
            lines.extend(["", "## Failed Services", ""])
            if services:
                lines += ["| Unit | Sub-State | Description |", "|------|-----------|-------------|"]
                for svc in services:
                    lines.append(f"| {svc['unit']} | {svc['sub']} | {svc['description']} |")
            else:
                lines.append("\u2705 No failed services.")

            lines.extend(["", "## Recent Journal Errors", ""])
            if journal_errors:
                lines += ["```", journal_errors, "```"]
            else:
                lines.append("\u2705 No recent critical/error journal entries.")

            lines.extend(["", "## Pending Updates", "", f"**Status:** {updates}"])

            lines.extend(["", "## SELinux Status", ""])
            lines.append(f"**Mode:** {selinux.get('mode', 'Unknown')}")
            denials = selinux.get("recent_denials", "")
            if denials:
                lines += ["", "**Recent AVC Denials (today):**", "```", denials, "```"]
            else:
                lines += ["", "\u2705 No AVC denials today."]

            lines.extend(["", "## Network Overview", ""])
            lines += [
                f"| IP Addresses | {network.get('ip_addresses', 'Unknown')} |",
                f"| DNS Servers | {network.get('dns_servers', 'Unknown')} |",
                f"| Default Gateway | {network.get('default_gateway', 'Unknown')} |",
            ]

        lines += ["", "---", "*Report generated by Loofi Fedora Tweaks*", ""]
        return "\n".join(lines)

    @staticmethod
    def export_html(
        info: Optional[Dict[str, str]] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format diagnostic data as a styled HTML report.

        Args:
            info: Legacy system info dict. Ignored when diagnostics provided.
            diagnostics: Full diagnostics dict from gather_all_diagnostics().
                         When provided, all diagnostic sections are rendered.

        Returns:
            Complete HTML document string.
        """
        if diagnostics is not None:
            info = diagnostics.get("system_info") or {}
            services: List[Dict[str, str]] = diagnostics.get("services") or []
            journal_errors: str = diagnostics.get("journal_errors") or ""
            updates: str = diagnostics.get("updates") or "Unknown"
            selinux: Dict[str, str] = diagnostics.get("selinux") or {}
            network: Dict[str, str] = diagnostics.get("network") or {}
            has_diagnostics = True
        else:
            if info is None:
                info = ReportExporter.gather_system_info()
            services, journal_errors, updates = [], "", ""
            selinux, network = {}, {}
            has_diagnostics = False

        field_labels = {
            "hostname": "Hostname",
            "kernel": "Kernel",
            "fedora_version": "Fedora Version",
            "cpu": "CPU",
            "ram": "RAM",
            "disk_root": "Disk Usage (/)",
            "uptime": "Uptime",
            "battery": "Battery",
            "architecture": "Architecture",
            "desktop": "Desktop Environment",
        }

        sys_rows = ""
        for key, label in field_labels.items():
            sys_rows += f"        <tr><td><b>{label}</b></td><td>{info.get(key, 'Unknown')}</td></tr>\n"

        report_date = info.get("report_date", "Unknown")

        extra_sections = ""
        if has_diagnostics:
            if services:
                svc_rows = "".join(
                    f"        <tr><td>{s['unit']}</td><td>{s['sub']}</td><td>{s['description']}</td></tr>\n"
                    for s in services
                )
                extra_sections += (
                    "\n    <h2>Failed Services</h2>\n"
                    "    <table>\n"
                    "        <tr><th>Unit</th><th>Sub-State</th><th>Description</th></tr>\n"
                    f"{svc_rows}"
                    "    </table>"
                )
            else:
                extra_sections += "\n    <h2>Failed Services</h2>\n    <p class='ok'>\u2705 No failed services.</p>"

            if journal_errors:
                escaped = (
                    journal_errors.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                )
                extra_sections += f"\n    <h2>Recent Journal Errors</h2>\n    <pre>{escaped}</pre>"
            else:
                extra_sections += (
                    "\n    <h2>Recent Journal Errors</h2>\n"
                    "    <p class='ok'>\u2705 No recent critical/error entries.</p>"
                )

            extra_sections += f"\n    <h2>Pending Updates</h2>\n    <p><b>Status:</b> {updates}</p>"

            selinux_mode = selinux.get("mode", "Unknown")
            denials = selinux.get("recent_denials", "")
            if denials:
                esc = denials.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                selinux_body = f"<p><b>Mode:</b> {selinux_mode}</p><pre>{esc}</pre>"
            else:
                selinux_body = (
                    f"<p><b>Mode:</b> {selinux_mode}</p>"
                    "<p class='ok'>\u2705 No AVC denials today.</p>"
                )
            extra_sections += f"\n    <h2>SELinux Status</h2>\n    {selinux_body}"

            net_rows = (
                f"        <tr><td><b>IP Addresses</b></td><td>{network.get('ip_addresses', 'Unknown')}</td></tr>\n"
                f"        <tr><td><b>DNS Servers</b></td><td>{network.get('dns_servers', 'Unknown')}</td></tr>\n"
                f"        <tr><td><b>Default Gateway</b></td><td>{network.get('default_gateway', 'Unknown')}</td></tr>\n"
            )
            extra_sections += (
                "\n    <h2>Network Overview</h2>\n"
                "    <table>\n"
                "        <tr><th>Property</th><th>Value</th></tr>\n"
                f"{net_rows}"
                "    </table>"
            )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>System Report \u2014 Loofi Fedora Tweaks</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               max-width: 900px; margin: 40px auto; padding: 0 20px;
               background: #0b0e14; color: #e6edf3; }}
        h1 {{ color: #39c5cf; border-bottom: 2px solid #1c2030; padding-bottom: 12px; }}
        h2 {{ color: #cdd6f4; margin-top: 32px; border-bottom: 1px solid #1c2030; padding-bottom: 6px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th, td {{ padding: 10px 16px; text-align: left; border-bottom: 1px solid #1c2030; }}
        th {{ background: #1c2030; color: #39c5cf; }}
        tr:hover {{ background: #1c2030; }}
        pre {{ background: #1c2030; padding: 14px; border-radius: 6px; overflow-x: auto;
               font-size: 0.85em; white-space: pre-wrap; color: #fab387; }}
        .ok {{ color: #a6e3a1; }}
        .footer {{ color: #6c7086; font-size: 0.85em; margin-top: 30px; }}
    </style>
</head>
<body>
    <h1>System Report \u2014 Loofi Fedora Tweaks</h1>
    <p><b>Generated:</b> {report_date}</p>
    <h2>System Information</h2>
    <table>
        <tr><th>Property</th><th>Value</th></tr>
{sys_rows}    </table>{extra_sections}
    <p class="footer">Report generated by Loofi Fedora Tweaks</p>
</body>
</html>"""

        return html

    @staticmethod
    def save_report(
        path: str,
        fmt: str,
        info: Optional[Dict[str, str]] = None,
        comprehensive: bool = True,
    ) -> str:
        """Generate and save a system report to a file.

        Args:
            path: Output file path.
            fmt: Format — 'markdown' or 'html'.
            info: Optional pre-gathered system info dict. Ignored when comprehensive=True.
            comprehensive: When True (default), gathers all 6 diagnostic sections.
                           When False, only basic system info is included (legacy mode).

        Returns:
            The path of the saved report.
        """
        if comprehensive:
            diagnostics = ReportExporter.gather_all_diagnostics()
            content = (
                ReportExporter.export_html(diagnostics=diagnostics)
                if fmt == "html"
                else ReportExporter.export_markdown(diagnostics=diagnostics)
            )
        else:
            if info is None:
                info = ReportExporter.gather_system_info()
            content = (
                ReportExporter.export_html(info=info)
                if fmt == "html"
                else ReportExporter.export_markdown(info=info)
            )

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return path
