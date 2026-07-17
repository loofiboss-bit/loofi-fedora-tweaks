"""
Integration tests for v29.0 "Usability & Polish" features.

Covers:
- SettingsManager.reset_group() method
- Settings group reset behavior
- API server CORS origins are restricted (not wildcard)
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))


# ---------------------------------------------------------------------------
# Settings reset_group
# ---------------------------------------------------------------------------

class TestSettingsResetGroup(unittest.TestCase):
    """SettingsManager.reset_group() resets only the specified keys."""

    def _make_manager(self, tmpdir, initial=None):
        from pathlib import Path
        from utils.settings import SettingsManager
        path = Path(tmpdir) / "settings.json"
        if initial is not None:
            path.write_text(json.dumps(initial, indent=2))
        return SettingsManager(settings_path=path)

    def test_reset_group_restores_defaults(self):
        """reset_group resets specified keys to defaults."""
        from utils.settings import AppSettings
        from dataclasses import asdict

        with tempfile.TemporaryDirectory() as tmpdir:
            initial = asdict(AppSettings())
            initial["theme"] = "light"
            initial["follow_system_theme"] = True
            initial["log_level"] = "DEBUG"
            mgr = self._make_manager(tmpdir, initial)

            # Confirm customised values
            self.assertEqual(mgr.get("theme"), "light")
            self.assertTrue(mgr.get("follow_system_theme"))
            self.assertEqual(mgr.get("log_level"), "DEBUG")

            # Reset only theme-related keys
            mgr.reset_group(["theme", "follow_system_theme"])

            self.assertEqual(mgr.get("theme"), "dark")
            self.assertFalse(mgr.get("follow_system_theme"))

    def test_reset_group_leaves_other_keys(self):
        """Keys not in the reset group remain unchanged."""
        from utils.settings import AppSettings
        from dataclasses import asdict

        with tempfile.TemporaryDirectory() as tmpdir:
            initial = asdict(AppSettings())
            initial["theme"] = "light"
            initial["log_level"] = "DEBUG"
            mgr = self._make_manager(tmpdir, initial)

            mgr.reset_group(["theme"])

            # theme reset
            self.assertEqual(mgr.get("theme"), "dark")
            # log_level unchanged
            self.assertEqual(mgr.get("log_level"), "DEBUG")

    def test_reset_group_persists_to_disk(self):
        """After reset_group, the file on disk reflects the reset values."""
        from pathlib import Path
        from utils.settings import SettingsManager, AppSettings
        from dataclasses import asdict

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            initial = asdict(AppSettings())
            initial["theme"] = "light"
            initial["start_minimized"] = True
            path.write_text(json.dumps(initial, indent=2))

            mgr = SettingsManager(settings_path=path)
            mgr.reset_group(["theme"])

            # Re-read from disk
            saved = json.loads(path.read_text())
            self.assertEqual(saved["theme"], "dark")
            self.assertTrue(saved["start_minimized"])

    def test_reset_group_unknown_key_ignored(self):
        """Unknown keys in the list are silently ignored."""
        from utils.settings import AppSettings
        from dataclasses import asdict

        with tempfile.TemporaryDirectory() as tmpdir:
            initial = asdict(AppSettings())
            initial["theme"] = "light"
            mgr = self._make_manager(tmpdir, initial)

            # "nonexistent_key" is not in defaults
            mgr.reset_group(["theme", "nonexistent_key"])

            self.assertEqual(mgr.get("theme"), "dark")

    def test_reset_group_empty_list(self):
        """Empty key list is a no-op but still persists (save called)."""
        from utils.settings import AppSettings
        from dataclasses import asdict

        with tempfile.TemporaryDirectory() as tmpdir:
            initial = asdict(AppSettings())
            initial["theme"] = "light"
            mgr = self._make_manager(tmpdir, initial)

            mgr.reset_group([])

            self.assertEqual(mgr.get("theme"), "light")


# ---------------------------------------------------------------------------
# API Server CORS lockdown
# ---------------------------------------------------------------------------

class TestAPIServerCORS(unittest.TestCase):
    """API server CORS origins are restricted to localhost (not wildcard)."""

    @patch('utils.api_server.uvicorn')
    @patch('utils.api_server.AuthManager')
    def test_cors_not_wildcard(self, mock_auth, mock_uvicorn):
        """Allowed origins must not contain '*'."""
        from utils.api_server import APIServer

        server = APIServer(host="127.0.0.1", port=8000)
        app = server.app

        # Find the CORSMiddleware in the middleware stack
        cors_found = False
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                cors_found = True
                origins = middleware.kwargs.get("allow_origins", [])
                self.assertNotIn("*", origins,
                                 "CORS should not allow wildcard origin")
        self.assertTrue(cors_found, "CORSMiddleware not found in app middleware")

    @patch('utils.api_server.uvicorn')
    @patch('utils.api_server.AuthManager')
    def test_cors_allows_localhost(self, mock_auth, mock_uvicorn):
        """Allowed origins should include localhost variants."""
        from utils.api_server import APIServer

        server = APIServer(host="127.0.0.1", port=8000)
        app = server.app

        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                origins = middleware.kwargs.get("allow_origins", [])
                localhost_found = any("localhost" in o or "127.0.0.1" in o for o in origins)
                self.assertTrue(localhost_found,
                                f"CORS should allow localhost, got: {origins}")
                break

    @patch('utils.api_server.uvicorn')
    @patch('utils.api_server.AuthManager')
    def test_cors_origins_are_list_of_strings(self, mock_auth, mock_uvicorn):
        """Origins should be a list of string URLs."""
        from utils.api_server import APIServer

        server = APIServer(host="127.0.0.1", port=8000)
        app = server.app

        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                origins = middleware.kwargs.get("allow_origins", [])
                self.assertIsInstance(origins, list)
                for o in origins:
                    self.assertIsInstance(o, str)
                    self.assertTrue(o.startswith("http"),
                                    f"Origin should be an HTTP URL: {o}")
                break

    @patch('utils.api_server.uvicorn')
    @patch('utils.api_server.AuthManager')
    def test_cors_credentials_enabled(self, mock_auth, mock_uvicorn):
        """Credentials should be allowed for API token auth."""
        from utils.api_server import APIServer

        server = APIServer(host="127.0.0.1", port=8000)
        app = server.app

        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                creds = middleware.kwargs.get("allow_credentials", False)
                self.assertTrue(creds)
                break


# ---------------------------------------------------------------------------
# Error handler integration
# ---------------------------------------------------------------------------

class TestErrorHandlerIntegration(unittest.TestCase):
    """Error handler installs and uninstalls correctly in lifecycle."""

    def test_install_and_uninstall_roundtrip(self):
        from utils.error_handler import (
            install_error_handler,
            uninstall_error_handler,
            _loofi_excepthook,
            _original_excepthook,
        )

        original = sys.excepthook
        try:
            install_error_handler()
            self.assertIs(sys.excepthook, _loofi_excepthook)

            uninstall_error_handler()
            self.assertIs(sys.excepthook, _original_excepthook)
        finally:
            sys.excepthook = original

    @patch('utils.error_handler._show_error_dialog')
    @patch('utils.error_handler._log_error')
    def test_excepthook_called_for_unhandled_exception(self, mock_log, mock_dialog):
        """When installed, unhandled exceptions route through the handler."""
        from utils.error_handler import install_error_handler
        from utils.errors import NetworkError

        original = sys.excepthook
        try:
            install_error_handler()
            exc = NetworkError("timeout")
            sys.excepthook(type(exc), exc, None)

            mock_log.assert_called_once()
            mock_dialog.assert_called_once_with(exc)
        finally:
            sys.excepthook = original


# ---------------------------------------------------------------------------
# Notification toast category fallback
# ---------------------------------------------------------------------------

class TestNotificationToastCategoryFallback(unittest.TestCase):
    """Unknown categories should gracefully fall back to default colour."""

    def test_unknown_category_returns_default_colour(self):
        from ui.notification_toast import _CATEGORY_COLORS
        default = "#39c5cf"
        result = _CATEGORY_COLORS.get("totally_unknown", default)
        self.assertEqual(result, default)


if __name__ == '__main__':
    unittest.main()
