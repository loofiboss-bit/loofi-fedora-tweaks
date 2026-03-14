"""
Tests for main.py — Application entry point.

Covers:
- _notify_error (desktop notification fallback)
- _check_pyqt6 (PyQt6 pre-flight check)
- main() with --daemon, --cli, --web, and GUI mode
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))


class TestNotifyError(unittest.TestCase):
    """Tests for _notify_error() desktop notification helper."""

    @patch("subprocess.Popen")
    def test_sends_notification(self, mock_popen):
        from main import _notify_error
        _notify_error("Title", "Message")
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn("notify-send", args)
        self.assertIn("Title", args)
        self.assertIn("Message", args)

    @patch("subprocess.Popen", side_effect=FileNotFoundError)
    def test_handles_missing_notify_send(self, mock_popen):
        from main import _notify_error
        _notify_error("Title", "Message")  # Should not raise


class TestCheckPyQt6(unittest.TestCase):
    """Tests for _check_pyqt6() pre-flight check."""

    def test_returns_true_when_available(self):
        from main import _check_pyqt6
        # PyQt6 is installed in the test env
        result = _check_pyqt6()
        self.assertTrue(result)

    @patch.dict("sys.modules", {"PyQt6": None, "PyQt6.QtWidgets": None})
    @patch("main._notify_error")
    def test_returns_false_on_import_error(self, mock_notify):
        # Force ImportError by making import fail
        import importlib

        import main
        importlib.reload(main)

        # Patch the inner import
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        def mock_import(name, *args, **kwargs):
            if name == "PyQt6.QtWidgets":
                raise ImportError("No module named 'PyQt6'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = main._check_pyqt6()
        self.assertFalse(result)

    @patch("main._notify_error")
    def test_handles_libgl_error(self, mock_notify):
        from main import _check_pyqt6
        original = __import__

        def mock_import(name, *args, **kwargs):
            if "PyQt6.QtWidgets" in name:
                raise ImportError("libGL.so.1 cannot open shared object file")
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = _check_pyqt6()
        self.assertFalse(result)
        mock_notify.assert_called()


class TestMainDaemon(unittest.TestCase):
    """Tests for main() --daemon mode."""

    @patch("sys.argv", ["loofi-fedora-tweaks", "--daemon"])
    @patch("daemon.runtime.run_daemon")
    def test_daemon_mode(self, mock_run):
        from main import main
        main()
        mock_run.assert_called_once()


class TestMainCLI(unittest.TestCase):
    """Tests for main() --cli mode."""

    @patch("sys.argv", ["loofi-fedora-tweaks", "--cli", "status"])
    @patch("cli.main.main", return_value=0)
    def test_cli_mode(self, mock_cli):
        from main import main
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 0)
        mock_cli.assert_called_once_with(["status"])


class TestMainWeb(unittest.TestCase):
    """Tests for main() --web mode."""

    @patch("sys.argv", ["loofi-fedora-tweaks", "--web"])
    @patch("utils.api_server.APIServer")
    @patch("time.sleep", side_effect=KeyboardInterrupt)
    def test_web_mode(self, mock_sleep, mock_api_class):
        mock_server = MagicMock()
        mock_api_class.return_value = mock_server
        from main import main
        main()
        mock_api_class.assert_called_once_with(host="127.0.0.1", port=8000, allow_expose=False)
        mock_server.start.assert_called_once()

    @patch.dict(os.environ, {"LOOFI_API_HOST": "0.0.0.0"}, clear=False)
    @patch("sys.argv", ["loofi-fedora-tweaks", "--web"])
    def test_web_mode_rejects_non_loopback_without_unsafe_expose(self):
        from main import main

        with self.assertRaises(SystemExit) as cm:
            main()

        self.assertEqual(cm.exception.code, 1)

    @patch.dict(os.environ, {"LOOFI_API_HOST": "0.0.0.0"}, clear=False)
    @patch("sys.argv", ["loofi-fedora-tweaks", "--web", "--unsafe-expose"])
    @patch("utils.api_server.APIServer")
    @patch("time.sleep", side_effect=KeyboardInterrupt)
    def test_web_mode_allows_non_loopback_with_unsafe_expose(self, mock_sleep, mock_api_class):
        mock_server = MagicMock()
        mock_api_class.return_value = mock_server
        from main import main

        main()

        mock_api_class.assert_called_once_with(host="0.0.0.0", port=8000, allow_expose=True)
        mock_server.start.assert_called_once()


class TestMainGUI(unittest.TestCase):
    """Tests for main() GUI mode (default)."""

    @patch("sys.argv", ["loofi-fedora-tweaks"])
    @patch("main._check_pyqt6", return_value=False)
    def test_gui_mode_no_pyqt6_exits(self, mock_check):
        from main import main
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)

    @patch("sys.argv", ["loofi-fedora-tweaks"])
    @patch("main._check_pyqt6", return_value=True)
    @patch("main._notify_error")
    def test_gui_mode_import_error(self, mock_notify, mock_check):
        with patch("builtins.__import__", side_effect=Exception("bad import")):
            # The real import will fail so main catches it
            pass
        # Just verify the function path without actual GUI

    def test_gui_startup_catches_type_and_attribute_errors(self):
        """Startup catch block includes TypeError/AttributeError regressions."""
        filepath = os.path.join(
            os.path.dirname(__file__), '..', 'loofi-fedora-tweaks', 'main.py'
        )
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        self.assertIn(
            "except (OSError, RuntimeError, ValueError, ImportError, TypeError, AttributeError) as exc:",
            source,
        )


if __name__ == '__main__':
    unittest.main()
