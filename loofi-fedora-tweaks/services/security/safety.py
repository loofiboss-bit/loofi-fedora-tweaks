"""
Safety Manager — system snapshot and pre-action safety checks.

Migrated from utils/safety.py in v2.0.0.
"""

import logging
import subprocess
from typing import Any, Optional

from services.system.system import cached_which

logger = logging.getLogger(__name__)


class SafetyManager:
    """Pre-action safety checks and snapshot management."""

    @staticmethod
    def check_dnf_lock() -> bool:
        """
        Check if DNF or RPM is currently running.

        Returns:
            True if a package manager process is running (locked).
        """
        import os

        if os.path.exists("/var/run/dnf.pid"):
            return True
        try:
            subprocess.check_call(
                ["pgrep", "-f", "dnf|yum|rpm"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            return True
        except subprocess.CalledProcessError:
            return False
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to check DNF lock: %s", e)
            return False

    @staticmethod
    def check_snapshot_tool() -> Optional[str]:
        """Check if Timeshift or Snapper is installed.

        Returns:
            Tool name ('timeshift' or 'snapper'), or None if neither found.
        """
        if cached_which("timeshift"):
            return "timeshift"
        elif cached_which("snapper"):
            return "snapper"
        return None

    @staticmethod
    def create_snapshot(tool: str, comment: str = "Loofi Auto-Snapshot") -> bool:
        """Create a system snapshot using the detected tool.

        Args:
            tool: Snapshot tool name ('timeshift' or 'snapper').
            comment: Snapshot description comment.

        Returns:
            True on success, False on failure.
        """
        if tool not in ("timeshift", "snapper"):
            logger.warning("Unknown snapshot tool requested: %s", tool)
            return False

        try:
            if tool == "timeshift":
                cmd = [
                    "pkexec",
                    "timeshift",
                    "--create",
                    "--comments",
                    comment,
                    "--tags",
                    "D",
                ]
            else:
                cmd = ["pkexec", "snapper", "create", "--description", comment]

            logger.info("Creating %s snapshot: %s", tool, comment)
            subprocess.run(cmd, check=True, timeout=600)
            logger.info("Snapshot created successfully via %s", tool)
            return True

        except subprocess.TimeoutExpired:
            logger.warning("Snapshot creation timed out after 600s using %s", tool)
            return False
        except subprocess.CalledProcessError as e:
            logger.warning("Snapshot failed via %s: %s", tool, e)
            return False
        except OSError as e:
            logger.warning("Could not run %s: %s", tool, e)
            return False

    @staticmethod
    def confirm_action(parent: Any, description: str) -> bool:
        """Prompt the user to confirm an action, offering to take a snapshot first."""
        from ui.confirm_dialog import confirm_safety_action

        return confirm_safety_action(
            parent,
            description,
            check_snapshot_tool=SafetyManager.check_snapshot_tool,
            create_snapshot=SafetyManager.create_snapshot,
        )
