"""Guest session detection must preserve real desktop identity."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from e2e.guest.runner import _session_environment


class TestGuestSessionEnvironment(TestCase):
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
