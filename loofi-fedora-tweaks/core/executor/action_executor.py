"""
Centralized action execution with bounded command vectors.

All system-level actions route through this executor.
Provides: preview mode, dry-run, structured results, action logging.

Usage:
    from core.executor.action_executor import ActionExecutor

    # Preview what would happen:
    result = ActionExecutor().preview("dnf", ["check-update"])

    # Execute for real:
    result = ActionExecutor().execute("dnf", ["check-update"])

    # With privilege escalation:
    result = ActionExecutor().execute("dnf", ["clean", "all"], privileged=True)

    # Legacy classmethod API (backward compatible):
    result = ActionExecutor.run("dnf", ["check-update"], preview=True)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.executor.action_result import ActionResult
from core.executor.base_executor import BaseActionExecutor
from core.executor.command_policy import CommandValidationError, validate_command
from core.privacy import redact_command, redact_payload, redact_text
from core.state.atomic_io import advisory_lock, atomic_write_text
from core.execution_policy import ExecutionAuthority, blocked_execution_message, execution_allowed
from core.tweak_commands import KWIN_SUPPORT

logger = logging.getLogger(__name__)

# Limits
COMMAND_TIMEOUT = 120  # seconds
MAX_STDOUT = 4000
MAX_KWIN_SUPPORT = 1024 * 1024
MAX_STDERR = 2000
MAX_LOG_ENTRIES = 500

# Action log location
_LOG_DIR = os.path.join(
    os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
    "loofi-fedora-tweaks",
)
_ACTION_LOG_FILE = os.path.join(_LOG_DIR, "action_log.jsonl")


def _private_log_line(line: str) -> str:
    """Sanitize historical entries as well as newly appended actions."""
    try:
        entry = json.loads(line)
    except (ValueError, TypeError):
        return redact_text(line, limit=2**63 - 1)
    if isinstance(entry, dict) and isinstance(entry.get("cmd"), list) and all(isinstance(part, str) for part in entry["cmd"]):
        entry["cmd"] = redact_command(entry["cmd"])
    return json.dumps(redact_payload(entry))


class ActionExecutor(BaseActionExecutor):
    """
    Synchronous subprocess-based executor (concrete implementation).

    Features:
    - Preview mode: returns what would execute, without running.
    - Dry-run mode (global): logs but never executes.
    - Structured ActionResult for every call.
    - JSON-lines action log for diagnostics export.
    - Flatpak-aware: auto-wraps with flatpak-spawn when inside sandbox.
    - pkexec integration for privilege escalation.
    """

    _dry_run_global: bool = False

    def execute(
        self,
        command: str,
        args: Optional[List[str]] = None,
        *,
        privileged: bool = False,
        timeout: int = COMMAND_TIMEOUT,
        action_id: str = "",
        env: Optional[Dict[str, str]] = None,
        authority: ExecutionAuthority = "legacy",
    ) -> ActionResult:
        """
        Execute a system command and return a structured result.

        Args:
            command: The executable name or path.
            args: Command arguments.
            privileged: If True, use pkexec for privilege escalation.
            timeout: Max seconds to wait.
            action_id: Optional ID for correlating with action definitions.
            env: Optional extra environment variables.

        Returns:
            ActionResult containing success status, output, and metadata.
        """
        args = args or []

        if not execution_allowed(command, args, authority=authority, action_id=action_id):
            result = ActionResult.fail(
                blocked_execution_message(command, args),
                exit_code=126,
                action_id=action_id,
                data={"execution_policy": "blocked", "authority": authority},
            )
            self._log_action([command, *args], result)
            return result

        # Global dry-run intercept
        if self._dry_run_global:
            return self.preview(
                command, args, privileged=privileged, action_id=action_id
            )

        try:
            cmd = self._build_command(command, args, privileged=privileged)
        except CommandValidationError as exc:
            result = ActionResult.fail(str(exc), exit_code=126, action_id=action_id)
            self._log_action([command] + args, result)
            return result

        # Execute
        result = self._execute_subprocess(
            cmd, timeout=timeout, action_id=action_id, env=env
        )
        self._log_action(cmd, result)
        return result

    def preview(
        self,
        command: str,
        args: Optional[List[str]] = None,
        *,
        privileged: bool = False,
        action_id: str = "",
    ) -> ActionResult:
        """
        Preview what would be executed without running the command.

        Args:
            command: The executable name or path.
            args: Command arguments.
            privileged: If True, would use pkexec for privilege escalation.
            action_id: Optional ID for correlating with action definitions.

        Returns:
            ActionResult with preview=True and command details in data field.
        """
        args = args or []
        try:
            cmd = self._build_command(command, args, privileged=privileged)
        except CommandValidationError as exc:
            result = ActionResult.fail(str(exc), exit_code=126, action_id=action_id)
            self._log_action([command] + args, result)
            return result

        result = ActionResult.previewed(cmd[0], cmd[1:], action_id=action_id)
        self._log_action(cmd, result)
        return result

    @classmethod
    def set_global_dry_run(cls, enabled: bool):
        """Enable/disable global dry-run mode."""
        cls._dry_run_global = enabled

    # ========== Legacy classmethod API (backward compatible) ==========
    @classmethod
    def run(
        cls,
        command: str,
        args: Optional[List[str]] = None,
        *,
        preview: bool = False,
        pkexec: bool = False,
        timeout: int = COMMAND_TIMEOUT,
        action_id: str = "",
        env: Optional[Dict[str, str]] = None,
        authority: ExecutionAuthority = "legacy",
    ) -> ActionResult:
        """
        Legacy classmethod API for backward compatibility.

        DEPRECATED: Use ActionExecutor().execute() or .preview() instead.

        Args:
            command: The executable name or path.
            args: Command arguments.
            preview: If True, return what would run without executing.
            pkexec: If True, prepend pkexec for privilege escalation.
            timeout: Max seconds to wait.
            action_id: Optional ID for correlating with action definitions.
            env: Optional extra environment variables.
        """
        executor = cls()
        if preview:
            return executor.preview(
                command, args, privileged=pkexec, action_id=action_id
            )
        else:
            return executor.execute(
                command,
                args,
                privileged=pkexec,
                timeout=timeout,
                action_id=action_id,
                env=env,
                authority=authority,
            )

    def _build_command(
        self, command: str, args: List[str], *, privileged: bool = False
    ) -> List[str]:
        """Build the final command list, handling Flatpak and privilege escalation."""
        validate_command(command, args)
        cmd = [command] + args

        # Privilege escalation via pkexec
        if privileged:
            cmd = ["pkexec"] + cmd

        # Flatpak sandbox detection
        if os.path.exists("/.flatpak-info") and cmd[0] != "flatpak-spawn":
            cmd = ["flatpak-spawn", "--host"] + cmd

        return cmd

    def _execute_subprocess(
        self,
        cmd: List[str],
        *,
        timeout: int,
        action_id: str,
        env: Optional[Dict[str, str]],
    ) -> ActionResult:
        """Run the subprocess and return an ActionResult."""
        run_env = None
        if env:
            run_env = {**os.environ, **env}

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=run_env,
            )

            # Only this reviewed read needs the complete DBus string tuple for
            # runtime verification. Persistence still uses ActionResult's 4000
            # character serialization cap; support details are never log text.
            support_read = tuple(cmd) in {KWIN_SUPPORT, ("flatpak-spawn", "--host", *KWIN_SUPPORT)}
            raw_stdout = proc.stdout or ""
            if support_read and len(raw_stdout) > MAX_KWIN_SUPPORT:
                return ActionResult.fail("KWin runtime information exceeded the supported size.", exit_code=-1, action_id=action_id)
            stdout = raw_stdout[:MAX_KWIN_SUPPORT if support_read else MAX_STDOUT]
            stderr = (proc.stderr or "")[:MAX_STDERR]

            if proc.returncode == 0:
                return ActionResult(
                    success=True,
                    message="KWin runtime information read." if support_read else stdout.strip()[:300] or "OK",
                    exit_code=0,
                    stdout=stdout,
                    stderr=stderr,
                    action_id=action_id,
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"Exit {proc.returncode}: {stderr.strip()[:300]}",
                    exit_code=proc.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    action_id=action_id,
                )

        except subprocess.TimeoutExpired:
            return ActionResult.fail(
                f"Command timed out after {timeout}s",
                exit_code=-1,
                action_id=action_id,
            )
        except FileNotFoundError:
            return ActionResult.fail(
                f"Command not found: {cmd[0]}",
                exit_code=127,
                action_id=action_id,
            )
        except OSError as exc:
            return ActionResult.fail(
                f"OS error: {exc}",
                exit_code=-1,
                action_id=action_id,
            )

    def _log_action(self, cmd: List[str], result: ActionResult):
        """Append action to JSON-lines log file."""
        try:
            directory = Path(_LOG_DIR)
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.chmod(0o700)
            path = Path(_ACTION_LOG_FILE)
            entry = redact_payload({
                "ts": result.timestamp, "cmd": redact_command(cmd), "success": result.success,
                "exit_code": result.exit_code, "preview": result.preview, "message": redact_text(result.message, limit=200),
            })
            with advisory_lock(path):
                lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
                lines.append(json.dumps(entry))
                lines = [_private_log_line(line) for line in lines[-MAX_LOG_ENTRIES:]]
                atomic_write_text(path, "\n".join(lines) + "\n", mode=0o600, keep_backup=False)
        except OSError:
            pass  # Logging must not fail an otherwise valid action.

    def _trim_log(self):
        """Keep log file bounded under the same lock used by writers."""
        try:
            path = Path(_ACTION_LOG_FILE)
            with advisory_lock(path):
                if not path.exists():
                    return
                Path(_LOG_DIR).chmod(0o700)
                lines = [_private_log_line(line) for line in path.read_text(encoding="utf-8").splitlines()[-MAX_LOG_ENTRIES:]]
                atomic_write_text(path, "\n".join(lines) + "\n", mode=0o600, keep_backup=False)
        except OSError:
            pass

    @classmethod
    def get_action_log(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """Read recent action log entries for diagnostics export."""
        try:
            path = Path(_ACTION_LOG_FILE)
            if not path.exists():
                return []
            with advisory_lock(path):
                Path(_LOG_DIR).chmod(0o700)
                path.chmod(0o600)
                lines = path.read_text(encoding="utf-8").splitlines()
            entries = []
            for line in lines[-limit:]:
                try:
                    entries.append(json.loads(_private_log_line(line)))
                except json.JSONDecodeError:
                    continue
            return entries
        except OSError:
            return []

    @classmethod
    def export_diagnostics(cls) -> Dict[str, Any]:
        """Export full diagnostics bundle (action log + system info)."""
        from version import __version__

        return {
            "version": __version__,
            "exported_at": time.time(),
            "action_log": cls.get_action_log(limit=100),
            "dry_run_global": cls._dry_run_global,
        }
