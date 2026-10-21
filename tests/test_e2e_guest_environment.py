"""Guest session detection must preserve real desktop identity."""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from e2e.guest.runner import _crash_diagnostics, _session_environment


class TestGuestSessionEnvironment(TestCase):
    @patch("e2e.guest.runner.shutil.which", return_value="/usr/bin/tool")
    @patch("e2e.guest.runner.subprocess.run")
    def test_crash_diagnostics_keep_frames_and_exclude_coredump_environment(self, run, which):
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout="python3: general protection fault in libQt6Gui.so\n"),
            SimpleNamespace(returncode=0, stdout=("Signal: 11 (SEGV)\nExecutable: /usr/bin/python3\n"
                                                "Environment: TOKEN=private\nStack trace of thread 123:\n"
                                                "#0 QAccessible::queryAccessibleInterface\n")),
        ]
        result = _crash_diagnostics()
        self.assertIn("libQt6Gui", result["kernel"]["text"])
        self.assertIn("#0 QAccessible", result["coredumps"]["text"])
        self.assertNotIn("TOKEN", result["coredumps"]["text"])
        self.assertNotIn("private", result["coredumps"]["text"])
        self.assertTrue(all(call.kwargs["timeout"] == 30 for call in run.call_args_list))

    def _read_text(path, **kwargs):
        return "Uid:\t1000 1000 1000 1000\n"

    def _read_wayland(path):
        if path.name == "cmdline":
            return b"/usr/bin/kwin_wayland\0--xwayland\0"
        return b"XDG_SESSION_TYPE=wayland\0WAYLAND_DISPLAY=wayland-0\0DISPLAY=:1\0XDG_RUNTIME_DIR=/run/user/1000\0DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus\0"

    @patch("e2e.guest.runner.shutil.which", return_value="/usr/local/bin/helper")
    @patch.object(Path, "read_bytes", _read_wayland)
    @patch.object(Path, "read_text", _read_text)
    @patch.object(Path, "glob", return_value=[Path("/proc/321")])
    def test_wayland_uses_wayland_platform_even_when_xwayland_exists(self, glob, which):
        env = _session_environment(1000)
        self.assertEqual(env["QT_QPA_PLATFORM"], "wayland")
        self.assertEqual(env["KWIN_PID"], "321")
        self.assertEqual(env["WAYLAND_DISPLAY"], "wayland-0")
        self.assertEqual(env["QT_LOGGING_RULES"], "*.debug=false")

    @patch("e2e.guest.runner.shutil.which", return_value=None)
    @patch.object(Path, "read_bytes", _read_wayland)
    @patch.object(Path, "read_text", _read_text)
    @patch.object(Path, "glob", return_value=[Path("/proc/321")])
    def test_missing_helpers_are_actionable_and_not_qualified_as_x11(self, glob, which):
        with self.assertRaisesRegex(RuntimeError, "Wayland automation requires KDE helper binaries"):
            _session_environment(1000)
