"""
Battery Manager - Battery charge limit control via systemd service.
Part of hardware services layer (v23.0 Architecture Hardening).
"""

import logging
import os
import subprocess
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class BatteryManager:
    SCRIPT_PATH = "/usr/local/bin/loofi-battery-limit.sh"
    SERVICE_PATH = "/etc/systemd/system/loofi-battery.service"
    CONFIG_PATH = "/etc/loofi-fedora-tweaks/battery.conf"
    SYSFS_PATH = "/sys/class/power_supply/BAT0/charge_control_end_threshold"
    HP_BIOSCFG_PATH = (
        "/sys/class/firmware-attributes/hp-bioscfg/attributes/Battery Health Manager/current_value"
    )

    @classmethod
    def get_threshold_path(cls) -> str:
        """
        Returns the active sysfs path if available, or falls back to SYSFS_PATH.
        """
        for bat in ("BAT0", "BAT1"):
            path = f"/sys/class/power_supply/{bat}/charge_control_end_threshold"
            if os.path.exists(path):
                return path
        return cls.SYSFS_PATH

    @classmethod
    def is_sysfs_supported(cls) -> bool:
        """Check if any standard sysfs charge control node exists."""
        for bat in ("BAT0", "BAT1"):
            if os.path.exists(f"/sys/class/power_supply/{bat}/charge_control_end_threshold"):
                return True
        return False

    @classmethod
    def is_supported(cls) -> bool:
        """
        Check if battery charge threshold control is supported on this system
        either via standard sysfs or HP firmware attributes.
        """
        return cls.is_sysfs_supported() or os.path.exists(cls.HP_BIOSCFG_PATH)

    def set_limit(self, limit: int) -> Tuple[Optional[str], Optional[list]]:
        """
        Sets the battery charge limit (80 or 100) using a persistent Systemd service.

        Returns:
            Tuple of (cmd, args) for the caller, or (None, None) on error.
            The command is now a multi-step operation run internally;
            returns ("echo", ["Battery limit set"]) on success.
        """
        # 1. Save config for the UI to read back
        try:
            os.makedirs(os.path.dirname(self.CONFIG_PATH), exist_ok=True)
            with open(self.CONFIG_PATH, "w") as f:
                f.write(str(limit))
        except (OSError, IOError) as e:
            logger.debug("Failed to save battery config: %s", e)

        # 2. Determine sysfs path and create the Systemd Service content with ConditionPathExists
        threshold_path = self.get_threshold_path()
        service_content = f"""[Unit]
Description=Restore Battery Charge Limit ({limit}%)
ConditionPathExists={threshold_path}
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo {limit} > {threshold_path}'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""

        # 3. Write to a temporary file to prepare for pkexec move
        tmp_service = "/tmp/loofi-battery.service"
        try:
            with open(tmp_service, "w") as f:
                f.write(service_content)

            # 4. Move service file to systemd directory
            result = subprocess.run(
                ["pkexec", "mv", tmp_service, self.SERVICE_PATH],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                logger.debug("Failed to move service file: %s", result.stderr)
                return None, None

            # 5. Reload systemd daemon
            result = subprocess.run(
                ["pkexec", "systemctl", "daemon-reload"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                logger.debug("daemon-reload failed: %s", result.stderr)
                return None, None

            # 6. Enable and start the service
            result = subprocess.run(
                ["pkexec", "systemctl", "enable", "--now", "loofi-battery.service"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                logger.debug("Service enable failed: %s", result.stderr)
                return None, None

            # 7. Apply immediately by writing to sysfs
            result = subprocess.run(
                [
                    "pkexec",
                    "tee",
                    threshold_path,
                ],
                input=str(limit),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                logger.debug("sysfs write failed: %s", result.stderr)
                # Service is installed but immediate apply failed
                return "echo", [
                    f"Battery limit service installed, reboot to apply {limit}%"
                ]

            return "echo", [f"Battery limit set to {limit}%"]

        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("Error preparing battery service: %s", e)
            return None, None

    def remove_service(self) -> Tuple[Optional[str], Optional[list]]:
        """
        Disables and removes the loofi-battery systemd service.

        Returns:
            Tuple of (cmd, args) on success, or (None, None) on error.
        """
        try:
            subprocess.run(
                ["pkexec", "systemctl", "disable", "--now", "loofi-battery.service"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if os.path.exists(self.SERVICE_PATH):
                subprocess.run(
                    ["pkexec", "rm", "-f", self.SERVICE_PATH],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
            subprocess.run(
                ["pkexec", "systemctl", "daemon-reload"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            subprocess.run(
                ["pkexec", "systemctl", "reset-failed", "loofi-battery.service"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            return "echo", ["Battery limit service removed"]
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("Error removing battery service: %s", e)
            return None, None
