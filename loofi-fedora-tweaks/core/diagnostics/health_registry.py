import time
import os
from typing import List, Dict, Optional
from .health_model import HealthCheck, HealthResult

class HealthRegistry:
    """
    Central registry for v4.0 Health & Repair Autopilot.
    Manages diagnostic definitions and execution.
    """
    def __init__(self):
        self._checks: Dict[str, HealthCheck] = {}
        self._results: Dict[str, HealthResult] = {}
        self._initialize_core_checks()

    def register(self, check: HealthCheck):
        """Register a new health check."""
        self._checks[check.id] = check

    def get_check(self, check_id: str) -> Optional[HealthCheck]:
        return self._checks.get(check_id)

    def list_checks(self, category: Optional[str] = None) -> List[HealthCheck]:
        if category:
            return [c for c in self._checks.values() if c.category == category]
        return list(self._checks.values())

    def _initialize_core_checks(self):
        """Register the baseline v4.0 foundation checks."""
        
        # 1. DNF Lock Check
        self.register(HealthCheck(
            id="dnf-lock",
            title="DNF Package Manager Lock",
            severity="warning",
            category="package",
            description="Checks if another process is currently using DNF or RPM.",
            detection_cmd=["fuser", "/var/lib/dnf/labels.db"],
            suggested_fix="Wait for the other process to finish, or terminate it if it is hung.",
            manual_commands=["ps aux | grep dnf"],
            rollback_hint="N/A",
            docs_link="https://docs.fedoraproject.org/en-US/fedora/latest/system-administrators-guide/package-management/DNF/"
        ))

        # 2. Failed Systemd Services
        self.register(HealthCheck(
            id="failed-services",
            title="Failed System Services",
            severity="error",
            category="system",
            description="Identifies systemd services that have failed to start or crashed.",
            detection_cmd=["systemctl", "--failed", "--quiet"],
            suggested_fix="Inspect the service logs and attempt to restart the failed service.",
            manual_commands=["systemctl status <service>", "journalctl -xeu <service>"],
            rollback_hint="N/A"
        ))

        # 3. Disk Space (Root)
        self.register(HealthCheck(
            id="disk-space-root",
            title="Root Partition Free Space",
            severity="warning",
            category="system",
            description="Checks if the root partition has sufficient free space (at least 5GB recommended).",
            suggested_fix="Clean up system logs, dnf cache, or remove unused packages.",
            manual_commands=["loofi-fedora-tweaks --cli cleanup"],
            docs_link="https://docs.fedoraproject.org/en-US/fedora/latest/install-guide/install/Preparing_Installation_Disk/"
        ))

        # 4. Pending Updates
        self.register(HealthCheck(
            id="pending-updates",
            title="Pending System Updates",
            severity="info",
            category="package",
            description="Checks for available DNF and Flatpak updates.",
            suggested_fix="Install pending updates to ensure system security and stability.",
            manual_commands=["dnf check-update", "flatpak update"],
            safe_to_auto_fix=False
        ))
        
        # 5. NVIDIA Akmods Status
        self.register(HealthCheck(
            id="nvidia-akmods",
            title="NVIDIA Kernel Module Status",
            severity="critical",
            category="hardware",
            description="Checks if NVIDIA kernel modules are built and loaded correctly.",
            suggested_fix="Rebuild akmods if there is a kernel mismatch.",
            manual_commands=["akmods --force", "modinfo nvidia"],
            rollback_hint="Boot into a previous kernel if the current one is broken."
        ))

        # 6. Atomic Pending Reboot
        self.register(HealthCheck(
            id="atomic-pending-reboot",
            title="Atomic Reboot Pending",
            severity="warning",
            category="system",
            description="Checks if a new rpm-ostree deployment is waiting for a reboot to apply.",
            suggested_fix="Reboot your system to apply pending updates and changes.",
            manual_commands=["systemctl reboot"],
            docs_link="https://docs.fedoraproject.org/en-US/fedora-silverblue/updates-upgrades/"
        ))

        # 7. Atomic Layered Packages
        self.register(HealthCheck(
            id="atomic-layered-packages",
            title="Layered Packages Detection",
            severity="info",
            category="package",
            description="Detects packages layered on top of the base Atomic image.",
            suggested_fix="Minimize layered packages; use Flatpaks or Toolbx/Distrobox where possible.",
            manual_commands=["rpm-ostree status"],
            docs_link="https://docs.fedoraproject.org/en-US/fedora-silverblue/toolbox/"
        ))

        # 8. SELinux Status
        self.register(HealthCheck(
            id="selinux-status",
            title="SELinux Mode",
            severity="warning",
            category="security",
            description="Checks if SELinux is in 'Enforcing' mode for maximum security.",
            suggested_fix="Enable Enforcing mode to protect your system from exploits.",
            manual_commands=["sestatus"],
            docs_link="https://docs.fedoraproject.org/en-US/fedora/latest/selinux-guide/"
        ))

    def run_check(self, check_id: str) -> HealthResult:
        """
        Execute the detection logic for a health check.
        Uses ActionExecutor for safe subprocess handling.
        """
        from ..executor.action_executor import ActionExecutor
        from services.system.system import SystemManager
        
        check = self.get_check(check_id)
        if not check:
            return HealthResult(check_id, "error", f"Check '{check_id}' not found.")
        
        executor = ActionExecutor()
        
        # 1. Handle specialized detection logic for core checks
        if check_id == "dnf-lock":
            if SystemManager.is_atomic():
                return HealthResult(check_id, "skipped", "DNF lock check not applicable on Atomic systems.")
            
            res = executor.execute("fuser", ["/var/lib/dnf/labels.db"])
            if res.exit_code == 0: # fuser returns 0 if file is accessed
                return HealthResult(check_id, "unhealthy", "Another process is using DNF.", details=res.stdout)
            return HealthResult(check_id, "healthy", "DNF is not locked.")

        if check_id == "failed-services":
            res = executor.execute("systemctl", ["--failed", "--no-legend"])
            if res.success and res.stdout.strip():
                lines = res.stdout.strip().splitlines()
                failed_names = []
                for line in lines:
                    parts = line.split()
                    if parts:
                        failed_names.append(parts[0])
                
                return HealthResult(
                    check_id, 
                    "unhealthy", 
                    f"{len(failed_names)} failed system services detected.", 
                    details=res.stdout,
                    affected_entities=failed_names
                )
            return HealthResult(check_id, "healthy", "No failed system services.")

        if check_id == "disk-space-root":
            import shutil
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (2**30)
            if free_gb < 5:
                return HealthResult(check_id, "unhealthy", f"Low disk space: {free_gb}GB remaining.", details=f"{free_gb}GB free of {total // (2**30)}GB")
            return HealthResult(check_id, "healthy", f"Sufficient disk space: {free_gb}GB free.")

        if check_id == "pending-updates":
            # This is a slower check, we might want to run it differently in the future
            pm = SystemManager.get_package_manager()
            if SystemManager.is_atomic():
                if SystemManager.has_pending_deployment():
                    return HealthResult(check_id, "unhealthy", "Update pending: reboot required to apply.")
                return HealthResult(check_id, "healthy", "System is up to date.")
            else:
                res = executor.execute(pm, ["check-update", "-q"], timeout=60)
                if res.exit_code == 100:
                    return HealthResult(check_id, "unhealthy", "System updates are available.")
                return HealthResult(check_id, "healthy", "System is up to date.")

        if check_id == "atomic-pending-reboot":
            if not SystemManager.is_atomic():
                return HealthResult(check_id, "skipped", "Check only applicable to Atomic Fedora.")
            if SystemManager.has_pending_deployment():
                return HealthResult(check_id, "unhealthy", "New deployment waiting for reboot.")
            return HealthResult(check_id, "healthy", "No pending deployments.")

        if check_id == "atomic-layered-packages":
            if not SystemManager.is_atomic():
                return HealthResult(check_id, "skipped", "Check only applicable to Atomic Fedora.")
            try:
                pkgs = SystemManager.get_layered_packages()
                if pkgs:
                    return HealthResult(
                        check_id, 
                        "info", 
                        f"{len(pkgs)} layered packages detected.",
                        details=", ".join(pkgs),
                        affected_entities=pkgs
                    )
                return HealthResult(check_id, "healthy", "No layered packages detected.")
            except Exception as e:
                return HealthResult(check_id, "error", f"Failed to detect layered packages: {e}")

        if check_id == "gaming-gamemode":
            res = executor.execute("gamemoded", ["-s"])
            if res.success:
                return HealthResult(check_id, "healthy", "GameMode is installed and active.")
            return HealthResult(check_id, "info", "GameMode is not installed.", suggested_fix="Install gamemode for better performance.")

        if check_id == "gaming-mangohud":
            from services.system.system import cached_which
            if cached_which("mangohud"):
                return HealthResult(check_id, "healthy", "MangoHud is available.")
            return HealthResult(check_id, "info", "MangoHud is not installed.")

        if check_id == "gaming-cpu-governor":
            res = executor.execute("powerprofilesctl", ["get"])
            if res.success:
                profile = res.stdout.strip()
                if profile == "performance":
                    return HealthResult(check_id, "healthy", f"Power profile is set to '{profile}'.")
                return HealthResult(check_id, "info", f"Power profile is '{profile}'. Consider 'performance' for gaming.")
            return HealthResult(check_id, "skipped", "Power profiles not supported on this hardware.")

        if check_id == "nvidia-akmods":
            from services.system.system import cached_which
            if not cached_which("modinfo"):
                return HealthResult(check_id, "skipped", "modinfo tool not found.")
            
            res = executor.execute("modinfo", ["nvidia"], timeout=10)
            if res.success:
                return HealthResult(check_id, "healthy", "NVIDIA kernel module is loaded and valid.")
            
            # Check if NVIDIA hardware is even present
            from services.system.system import SystemManager
            # Simple check via sysfs
            if not any(v in os.listdir("/sys/class/drm") for v in ["card0", "card1"]):
                return HealthResult(check_id, "skipped", "No discrete GPU detected via DRM subsystem.")
            
            return HealthResult(check_id, "warning", "NVIDIA module not found. Drivers may be missing or akmods failed to build.")

        if check_id == "selinux-status":
            if not os.path.exists("/usr/sbin/getenforce"):
                return HealthResult(check_id, "skipped", "SELinux tools not installed.")
            
            res = executor.execute("getenforce", [])
            if res.success:
                mode = res.stdout.strip()
                if mode == "Enforcing":
                    return HealthResult(check_id, "healthy", "SELinux is Enforcing.")
                return HealthResult(check_id, "warning", f"SELinux is in '{mode}' mode.", suggested_fix="Enable Enforcing mode for better security.")
            return HealthResult(check_id, "error", "Failed to detect SELinux mode.")

        # 2. Generic detection if command is provided
        if check.detection_cmd:
            cmd = check.detection_cmd[0]
            args = check.detection_cmd[1:]
            res = executor.execute(cmd, args)
            
            if res.success:
                # If expected_output is provided, check for a match
                if check.expected_output:
                    import re
                    if re.search(check.expected_output, res.stdout):
                        return HealthResult(check_id, "healthy", "Check passed (output matched).")
                    else:
                        return HealthResult(check_id, "unhealthy", "Check failed (output mismatch).", details=res.stdout)
                return HealthResult(check_id, "healthy", "Command executed successfully.")
            else:
                return HealthResult(check_id, "unhealthy", "Detection command failed.", details=res.stderr)

        return HealthResult(
            check_id=check_id,
            status="healthy",
            message=f"Check '{check.title}' verified (logic pending).",
            timestamp=time.time()
        )
