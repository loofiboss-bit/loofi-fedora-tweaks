"""Tests for Safe Mode persistence and API mutation guards."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))


class _MockHTTPException(Exception):
    def __init__(self, status_code=500, detail=None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class _MockRouter:
    def post(self, *args, **kwargs):
        del args, kwargs

        def decorator(func):
            return func

        return decorator


_fastapi_mock = MagicMock()
_fastapi_mock.APIRouter = _MockRouter
_fastapi_mock.Depends = lambda dependency: dependency
_fastapi_mock.HTTPException = _MockHTTPException
_fastapi_mock.status = MagicMock(
    HTTP_200_OK=200,
    HTTP_401_UNAUTHORIZED=401,
    HTTP_403_FORBIDDEN=403,
)

if 'fastapi' not in sys.modules:
    sys.modules['fastapi'] = _fastapi_mock
if 'fastapi.security' not in sys.modules:
    sys.modules['fastapi.security'] = MagicMock()

from api.routes.executor import ActionPayload, execute_action  # noqa: E402
from services.security.safe_mode import SafeModeManager  # noqa: E402
from utils.settings import AppSettings, SettingsManager  # noqa: E402


class TestSafeModeSettings(unittest.TestCase):
    """Settings-backed Safe Mode behavior."""

    def _make_manager(self, tmpdir: str) -> SettingsManager:
        return SettingsManager(settings_path=Path(tmpdir) / 'settings.json')

    def test_default_safe_mode_enabled(self):
        self.assertTrue(AppSettings().safe_mode_enabled)

    def test_safe_mode_manager_defaults_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self._make_manager(tmpdir)
            self.assertTrue(SafeModeManager.is_enabled(settings_manager=manager))

    def test_set_enabled_persists_safe_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self._make_manager(tmpdir)
            SafeModeManager.set_enabled(False, settings_manager=manager)

            reloaded = self._make_manager(tmpdir)
            self.assertFalse(SafeModeManager.is_enabled(settings_manager=reloaded))

    def test_preview_requests_allowed_while_safe_mode_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self._make_manager(tmpdir)
            self.assertTrue(
                SafeModeManager.allow_api_execution(
                    'systemctl',
                    preview=True,
                    pkexec=False,
                    settings_manager=manager,
                )
            )

    def test_read_only_command_allowed_while_safe_mode_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self._make_manager(tmpdir)
            self.assertTrue(
                SafeModeManager.allow_api_execution(
                    'uname',
                    preview=False,
                    pkexec=False,
                    settings_manager=manager,
                )
            )

    def test_mutating_command_blocked_while_safe_mode_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self._make_manager(tmpdir)
            self.assertFalse(
                SafeModeManager.allow_api_execution(
                    'systemctl',
                    preview=False,
                    pkexec=False,
                    settings_manager=manager,
                )
            )

    def test_mutating_command_allowed_after_safe_mode_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = self._make_manager(tmpdir)
            SafeModeManager.set_enabled(False, settings_manager=manager)
            self.assertTrue(
                SafeModeManager.allow_api_execution(
                    'systemctl',
                    preview=False,
                    pkexec=False,
                    settings_manager=manager,
                )
            )


class TestExecutorSafeModeGuard(unittest.TestCase):
    """Executor route should refuse blocked mutations clearly."""

    @patch('api.routes.executor.AuditLogger')
    @patch('api.routes.executor.ActionExecutor.run')
    @patch('api.routes.executor.SafetyManager.api_mutation_block_reason')
    def test_execute_action_blocks_mutation_when_safe_mode_enabled(
        self,
        mock_block_reason,
        mock_run,
        mock_audit_logger,
    ):
        mock_block_reason.return_value = 'Safe Mode is enabled and blocks mutating API execution.'
        mock_run.return_value = MagicMock(to_dict=lambda: {'preview': True}, exit_code=0)
        audit = MagicMock()
        mock_audit_logger.return_value = audit

        payload = ActionPayload(
            command='systemctl',
            args=['restart', 'demo.service'],
            preview=False,
            pkexec=False,
            action_id='safe-mode-test',
        )

        with self.assertRaises(Exception) as ctx:
            execute_action(payload, _auth='token')

        self.assertEqual(getattr(ctx.exception, 'status_code', None), 403)
        self.assertIn('Safe Mode', str(getattr(ctx.exception, 'detail', '')))
        mock_run.assert_called_once_with(
            'systemctl',
            ['restart', 'demo.service'],
            preview=True,
            pkexec=False,
            action_id='safe-mode-test',
        )
        audit.log.assert_called_once()
        self.assertEqual(audit.log.call_args[0][0], 'api.execute.blocked.safe_mode')


if __name__ == '__main__':
    unittest.main()
