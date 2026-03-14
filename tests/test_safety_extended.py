"""Extended tests for utils/safety.py SafetyManager.

Covers check_dnf_lock, check_snapshot_tool, create_snapshot, and
confirm_action with both success and failure paths, edge cases,
and UI interaction scenarios.
"""

import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from services.security.safety import SafetyManager


# ---------------------------------------------------------------------------
# check_dnf_lock
# ---------------------------------------------------------------------------


class TestCheckDnfLock(unittest.TestCase):
    """Tests for SafetyManager.check_dnf_lock.

    Note: ``os`` is lazily imported inside the method, so we patch
    ``os.path.exists`` at the global ``os`` module level rather than
    ``services.security.safety.os.path.exists``.
    """

    @patch("services.security.safety.subprocess.check_call")
    @patch("os.path.exists", return_value=True)
    def test_locked_when_pid_file_exists(self, mock_exists, mock_check_call):
        """Returns True immediately when /var/run/dnf.pid exists."""
        result = SafetyManager.check_dnf_lock()
        self.assertTrue(result)
        mock_exists.assert_called_once_with("/var/run/dnf.pid")
        mock_check_call.assert_not_called()

    @patch("services.security.safety.subprocess.check_call", return_value=0)
    @patch("os.path.exists", return_value=False)
    def test_locked_when_pgrep_finds_process(self, mock_exists, mock_check_call):
        """Returns True when pid file absent but pgrep finds dnf/yum/rpm."""
        result = SafetyManager.check_dnf_lock()
        self.assertTrue(result)
        mock_check_call.assert_called_once_with(
            ["pgrep", "-f", "dnf|yum|rpm"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )

    @patch(
        "services.security.safety.subprocess.check_call",
        side_effect=subprocess.CalledProcessError(1, "pgrep"),
    )
    @patch("os.path.exists", return_value=False)
    def test_not_locked_when_nothing_running(self, mock_exists, mock_check_call):
        """Returns False when pid file absent and no matching processes."""
        result = SafetyManager.check_dnf_lock()
        self.assertFalse(result)

    @patch(
        "services.security.safety.subprocess.check_call",
        side_effect=subprocess.CalledProcessError(2, "pgrep"),
    )
    @patch("os.path.exists", return_value=False)
    def test_not_locked_pgrep_syntax_error(self, mock_exists, mock_check_call):
        """Returns False on pgrep syntax/other error (exit code 2)."""
        result = SafetyManager.check_dnf_lock()
        self.assertFalse(result)

    @patch("services.security.safety.subprocess.check_call")
    @patch("os.path.exists", return_value=True)
    def test_pid_file_short_circuits_pgrep(self, mock_exists, mock_check_call):
        """Pgrep is never called when pid file already signals a lock."""
        SafetyManager.check_dnf_lock()
        mock_check_call.assert_not_called()

    @patch("services.security.safety.subprocess.check_call")
    @patch("os.path.exists", return_value=False)
    def test_pgrep_called_with_correct_timeout(self, mock_exists, mock_check_call):
        """Pgrep call uses timeout=10."""
        SafetyManager.check_dnf_lock()
        _, kwargs = mock_check_call.call_args
        self.assertEqual(kwargs["timeout"], 10)

    @patch("services.security.safety.subprocess.check_call")
    @patch("os.path.exists", return_value=False)
    def test_pgrep_stdout_stderr_devnull(self, mock_exists, mock_check_call):
        """Pgrep suppresses stdout and stderr."""
        SafetyManager.check_dnf_lock()
        _, kwargs = mock_check_call.call_args
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)

    @patch("services.security.safety.subprocess.check_call")
    @patch("os.path.exists", return_value=False)
    def test_pgrep_pattern_matches_dnf_yum_rpm(self, mock_exists, mock_check_call):
        """Pgrep uses the pattern 'dnf|yum|rpm' to find processes."""
        SafetyManager.check_dnf_lock()
        cmd = mock_check_call.call_args[0][0]
        self.assertEqual(cmd, ["pgrep", "-f", "dnf|yum|rpm"])

    @patch("services.security.safety.subprocess.check_call", return_value=0)
    @patch("os.path.exists", return_value=False)
    def test_return_type_is_bool(self, mock_exists, mock_check_call):
        """Return value is always a boolean."""
        result = SafetyManager.check_dnf_lock()
        self.assertIsInstance(result, bool)


# ---------------------------------------------------------------------------
# check_snapshot_tool
# ---------------------------------------------------------------------------


class TestCheckSnapshotTool(unittest.TestCase):
    """Tests for SafetyManager.check_snapshot_tool."""

    @patch("services.security.safety.cached_which")
    def test_timeshift_preferred_over_snapper(self, mock_which):
        """Returns 'timeshift' when both tools are available."""
        mock_which.side_effect = lambda x: f"/usr/bin/{x}"
        result = SafetyManager.check_snapshot_tool()
        self.assertEqual(result, "timeshift")

    @patch("services.security.safety.cached_which")
    def test_returns_timeshift_when_only_timeshift(self, mock_which):
        """Returns 'timeshift' when only timeshift is installed."""
        mock_which.side_effect = lambda x: (
            "/usr/bin/timeshift" if x == "timeshift" else None
        )
        result = SafetyManager.check_snapshot_tool()
        self.assertEqual(result, "timeshift")

    @patch("services.security.safety.cached_which")
    def test_returns_snapper_when_only_snapper(self, mock_which):
        """Returns 'snapper' when only snapper is installed."""
        mock_which.side_effect = lambda x: (
            "/usr/bin/snapper" if x == "snapper" else None
        )
        result = SafetyManager.check_snapshot_tool()
        self.assertEqual(result, "snapper")

    @patch("services.security.safety.cached_which", return_value=None)
    def test_returns_none_when_no_tool(self, mock_which):
        """Returns None when neither tool is installed."""
        result = SafetyManager.check_snapshot_tool()
        self.assertIsNone(result)

    @patch("services.security.safety.cached_which")
    def test_checks_timeshift_before_snapper(self, mock_which):
        """Checks timeshift first; does not check snapper if timeshift found."""
        mock_which.return_value = "/usr/bin/timeshift"
        SafetyManager.check_snapshot_tool()
        self.assertEqual(mock_which.call_args_list[0], call("timeshift"))

    @patch("services.security.safety.cached_which")
    def test_return_type_is_string_or_none(self, mock_which):
        """Return value is always a string or None, never another type."""
        mock_which.return_value = None
        result = SafetyManager.check_snapshot_tool()
        self.assertIsNone(result)

        mock_which.return_value = "/usr/bin/timeshift"
        result = SafetyManager.check_snapshot_tool()
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# create_snapshot
# ---------------------------------------------------------------------------


class TestCreateSnapshot(unittest.TestCase):
    """Tests for SafetyManager.create_snapshot."""

    @patch("services.security.safety.subprocess.run")
    def test_timeshift_snapshot_success(self, mock_run):
        """Returns True on successful timeshift snapshot."""
        mock_run.return_value = MagicMock(returncode=0)
        result = SafetyManager.create_snapshot("timeshift", "Test snapshot")
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            [
                "pkexec",
                "timeshift",
                "--create",
                "--comments",
                "Test snapshot",
                "--tags",
                "D",
            ],
            check=True,
            timeout=600,
        )

    @patch("services.security.safety.subprocess.run")
    def test_snapper_snapshot_success(self, mock_run):
        """Returns True on successful snapper snapshot."""
        mock_run.return_value = MagicMock(returncode=0)
        result = SafetyManager.create_snapshot("snapper", "Test snapshot")
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["pkexec", "snapper", "create", "--description", "Test snapshot"],
            check=True,
            timeout=600,
        )

    @patch("services.security.safety.subprocess.run")
    def test_timeshift_default_comment(self, mock_run):
        """Uses default comment when none provided."""
        mock_run.return_value = MagicMock(returncode=0)
        SafetyManager.create_snapshot("timeshift")
        args, kwargs = mock_run.call_args
        self.assertIn("Loofi Auto-Snapshot", args[0])

    @patch("services.security.safety.subprocess.run")
    def test_snapper_default_comment(self, mock_run):
        """Uses default comment for snapper when none provided."""
        mock_run.return_value = MagicMock(returncode=0)
        SafetyManager.create_snapshot("snapper")
        cmd = mock_run.call_args[0][0]
        self.assertIn("Loofi Auto-Snapshot", cmd)

    @patch(
        "services.security.safety.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "pkexec"),
    )
    def test_timeshift_snapshot_failure(self, mock_run):
        """Returns False when timeshift command fails."""
        result = SafetyManager.create_snapshot("timeshift", "fail")
        self.assertFalse(result)

    @patch(
        "services.security.safety.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "pkexec"),
    )
    def test_snapper_snapshot_failure(self, mock_run):
        """Returns False when snapper command fails."""
        result = SafetyManager.create_snapshot("snapper", "fail")
        self.assertFalse(result)

    @patch("services.security.safety.subprocess.run")
    def test_unknown_tool_returns_false(self, mock_run):
        """Returns False for an unrecognised tool name."""
        result = SafetyManager.create_snapshot("btrfs-snap", "test")
        self.assertFalse(result)
        mock_run.assert_not_called()

    @patch("services.security.safety.subprocess.run")
    def test_empty_tool_returns_false(self, mock_run):
        """Returns False when tool is an empty string."""
        result = SafetyManager.create_snapshot("", "test")
        self.assertFalse(result)
        mock_run.assert_not_called()

    @patch("services.security.safety.subprocess.run")
    def test_none_tool_returns_false(self, mock_run):
        """Returns False when tool is None."""
        result = SafetyManager.create_snapshot(None, "test")
        self.assertFalse(result)
        mock_run.assert_not_called()

    @patch("services.security.safety.subprocess.run")
    def test_timeout_is_600_seconds(self, mock_run):
        """Snapshot commands use a 600-second timeout."""
        mock_run.return_value = MagicMock(returncode=0)
        SafetyManager.create_snapshot("timeshift")
        _, kwargs = mock_run.call_args
        self.assertEqual(kwargs["timeout"], 600)

    @patch("services.security.safety.subprocess.run")
    def test_check_true_passed(self, mock_run):
        """Snapshot commands use check=True for CalledProcessError on failure."""
        mock_run.return_value = MagicMock(returncode=0)
        SafetyManager.create_snapshot("snapper")
        _, kwargs = mock_run.call_args
        self.assertTrue(kwargs["check"])

    @patch("services.security.safety.subprocess.run")
    def test_timeshift_uses_pkexec(self, mock_run):
        """Timeshift command starts with pkexec for privilege escalation."""
        mock_run.return_value = MagicMock(returncode=0)
        SafetyManager.create_snapshot("timeshift", "priv check")
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "pkexec")

    @patch("services.security.safety.subprocess.run")
    def test_snapper_uses_pkexec(self, mock_run):
        """Snapper command starts with pkexec for privilege escalation."""
        mock_run.return_value = MagicMock(returncode=0)
        SafetyManager.create_snapshot("snapper", "priv check")
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "pkexec")

    @patch("services.security.safety.subprocess.run")
    def test_comment_with_special_characters(self, mock_run):
        """Comment containing special characters is passed through unchanged."""
        mock_run.return_value = MagicMock(returncode=0)
        comment = "Pre-install: foo & bar 'baz'"
        SafetyManager.create_snapshot("timeshift", comment)
        cmd = mock_run.call_args[0][0]
        self.assertIn(comment, cmd)

    @patch("services.security.safety.subprocess.run")
    def test_timeshift_tag_is_daily(self, mock_run):
        """Timeshift snapshots are tagged with 'D' (daily)."""
        mock_run.return_value = MagicMock(returncode=0)
        SafetyManager.create_snapshot("timeshift", "tag check")
        cmd = mock_run.call_args[0][0]
        tag_idx = cmd.index("--tags")
        self.assertEqual(cmd[tag_idx + 1], "D")

    @patch("services.security.safety.subprocess.run")
    def test_snapper_no_shell_true(self, mock_run):
        """Snapper command does not use shell=True."""
        mock_run.return_value = MagicMock(returncode=0)
        SafetyManager.create_snapshot("snapper", "security")
        _, kwargs = mock_run.call_args
        self.assertNotIn("shell", kwargs)


# ---------------------------------------------------------------------------
# confirm_action
# ---------------------------------------------------------------------------


class TestConfirmAction(unittest.TestCase):
    """Tests for SafetyManager.confirm_action dialog integration."""

    def _make_parent(self):
        parent = MagicMock()
        parent.setDisabled = MagicMock()
        return parent

    def _make_dialog(self, *, accepted: bool, snapshot_requested: bool = False):
        dialog = MagicMock()
        dialog.DialogCode.Accepted = 1
        dialog.exec.return_value = 1 if accepted else 0
        dialog.snapshot_requested = snapshot_requested
        return dialog

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value=None)
    def test_cancel_returns_false(self, mock_tool, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=False)

        self.assertFalse(SafetyManager.confirm_action(parent, "install packages"))

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value=None)
    def test_continue_without_snapshot_returns_true(self, mock_tool, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=True, snapshot_requested=False)

        self.assertTrue(SafetyManager.confirm_action(parent, "remove package"))

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.create_snapshot", return_value=True)
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value="timeshift")
    @patch("PyQt6.QtWidgets.QMessageBox")
    def test_snapshot_and_continue_success(self, mock_msgbox, mock_tool, mock_snap, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=True, snapshot_requested=True)

        self.assertTrue(SafetyManager.confirm_action(parent, "install foo"))
        mock_snap.assert_called_once()
        mock_msgbox.information.assert_called_once()

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.create_snapshot", return_value=False)
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value="snapper")
    @patch("PyQt6.QtWidgets.QMessageBox")
    def test_snapshot_failure_shows_warning(self, mock_msgbox, mock_tool, mock_snap, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=True, snapshot_requested=True)

        self.assertTrue(SafetyManager.confirm_action(parent, "remove bar"))
        mock_msgbox.warning.assert_called_once()
        mock_msgbox.information.assert_not_called()

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.create_snapshot", return_value=True)
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value="timeshift")
    @patch("PyQt6.QtWidgets.QMessageBox")
    def test_parent_disabled_during_snapshot(self, mock_msgbox, mock_tool, mock_snap, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=True, snapshot_requested=True)

        SafetyManager.confirm_action(parent, "do stuff")
        self.assertEqual(parent.setDisabled.call_args_list[0], call(True))
        self.assertEqual(parent.setDisabled.call_args_list[1], call(False))

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value=None)
    def test_dialog_receives_risk_registry_context(self, mock_tool, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=False)

        SafetyManager.confirm_action(parent, "Full System Update")

        kwargs = mock_dialog_cls.call_args.kwargs
        self.assertEqual(kwargs["action_key"], "dnf_update")
        self.assertEqual(kwargs["risk_level"], "medium")
        self.assertIn("Restore", kwargs["undo_hint"])
        self.assertIn("snapshot", kwargs["description"].lower())

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.create_snapshot", return_value=True)
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value="timeshift")
    @patch("PyQt6.QtWidgets.QMessageBox")
    def test_snapshot_comment_derives_from_description(self, mock_msgbox, mock_tool, mock_snap, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=True, snapshot_requested=True)

        SafetyManager.confirm_action(parent, "install heavy packages")
        self.assertEqual(mock_snap.call_args[0][1], "Pre-install")

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.create_snapshot", return_value=False)
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value="snapper")
    @patch("PyQt6.QtWidgets.QMessageBox")
    def test_snapshot_failure_still_returns_true(self, mock_msgbox, mock_tool, mock_snap, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=True, snapshot_requested=True)

        self.assertTrue(SafetyManager.confirm_action(parent, "update system"))

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value="snapper")
    def test_dialog_offers_snapshot_when_tool_available(self, mock_tool, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=False)

        SafetyManager.confirm_action(parent, "test action")
        self.assertTrue(mock_dialog_cls.call_args.kwargs["offer_snapshot"])

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.create_snapshot", return_value=True)
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value="timeshift")
    @patch("PyQt6.QtWidgets.QMessageBox")
    def test_create_snapshot_receives_correct_tool(self, mock_msgbox, mock_tool, mock_snap, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=True, snapshot_requested=True)

        SafetyManager.confirm_action(parent, "upgrade kernel")
        self.assertEqual(mock_snap.call_args[0][0], "timeshift")

    @patch("ui.confirm_dialog.ConfirmActionDialog")
    @patch("services.security.safety.SafetyManager.create_snapshot", return_value=False)
    @patch("services.security.safety.SafetyManager.check_snapshot_tool", return_value="timeshift")
    @patch("PyQt6.QtWidgets.QMessageBox")
    def test_parent_reenabled_after_failed_snapshot(self, mock_msgbox, mock_tool, mock_snap, mock_dialog_cls):
        parent = self._make_parent()
        mock_dialog_cls.return_value = self._make_dialog(accepted=True, snapshot_requested=True)

        SafetyManager.confirm_action(parent, "risky op")
        self.assertEqual(parent.setDisabled.call_args_list[-1], call(False))


if __name__ == "__main__":
    unittest.main()
