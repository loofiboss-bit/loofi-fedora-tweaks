"""
Safety Manager — system snapshot and pre-action safety checks.

Migrated from utils/safety.py in v2.0.0.
"""

import logging
import subprocess
from typing import Optional

from services.security.risk import RiskRegistry
from services.security.safe_mode import SafeModeManager
from services.system.system import cached_which

logger = logging.getLogger(__name__)


class SafetyManager:
    """Pre-action safety checks and snapshot management."""

    @staticmethod
    def api_mutation_block_reason(
        command: str,
        *,
        preview: bool,
        pkexec: bool = False,
    ) -> Optional[str]:
        """Return a refusal message when Safe Mode blocks execution."""
        if SafeModeManager.allow_api_execution(
            command,
            preview=preview,
            pkexec=pkexec,
        ):
            return None

        return SafeModeManager.mutation_refusal_message(command)

    @staticmethod
    def _resolve_action_id(description: str, action_id: Optional[str] = None) -> Optional[str]:
        """Resolve a risk action ID from an explicit value or human-readable label."""
        return action_id or RiskRegistry.resolve_action_id(description)

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
    def confirm_action(parent, description: str, action_id: Optional[str] = None) -> bool:
        """
        Prompt the user to confirm an action, offering to take a snapshot first.

        Note: This method imports PyQt6 lazily. The snapshot creation runs
        with processEvents() calls to avoid a full UI freeze.

        Args:
            parent: Parent QWidget for the dialog.
            description: Human-readable action description.

        Returns:
            True if the action should proceed, False otherwise.
        """
        from PyQt6.QtWidgets import QMessageBox
        from ui.confirm_dialog import ConfirmActionDialog

        tool = SafetyManager.check_snapshot_tool()
        resolved_action_id = SafetyManager._resolve_action_id(description, action_id)
        risk_entry = RiskRegistry.get_risk(resolved_action_id) if resolved_action_id else None
        detail = "It is recommended to create a system snapshot before proceeding."
        if risk_entry:
            detail = f"{risk_entry.description}. {detail}"

        dialog = ConfirmActionDialog(
            parent=parent,
            action=description,
            description=detail,
            undo_hint=RiskRegistry.get_revert_instructions(resolved_action_id or "") or "",
            offer_snapshot=bool(tool),
            risk_level=risk_entry.level.value if risk_entry else "",
            action_key=resolved_action_id or "",
        )

        if dialog.exec() != dialog.DialogCode.Accepted:
            return False

        if tool and dialog.snapshot_requested:
            # Show a progress message while snapshot runs
            parent.setDisabled(True)

            success = SafetyManager.create_snapshot(tool, f"Pre-{description.split(' ')[0]}")

            parent.setDisabled(False)

            if not success:
                QMessageBox.warning(
                    parent,
                    "Snapshot Failed",
                    "Could not create snapshot. Proceeding regardless...",
                )
            else:
                QMessageBox.information(parent, "Snapshot Created", "System snapshot created successfully.")

        return True
