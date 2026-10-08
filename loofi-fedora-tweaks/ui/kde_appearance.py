"""Managed asynchronous native cursor-settings discovery and launch."""

from __future__ import annotations

from typing import Any


class CursorSettingsMixin:
    """Keep native cursor handoffs on the existing window-owned worker."""

    def _refresh_cursor_settings_handoff(self: Any, page: Any) -> bool:
        """Discover the fixed native X11 alternative on the managed reader."""
        from core.catalog_models import NativeHandoffId
        from services.desktop.native_handoff import NativeHandoffService

        if (self._utility_operation_adapter is not None or getattr(self, "_pending_runtime_shutdown", None)
                or getattr(self, "_runtime_cleaned", False) or not getattr(page, "cursor_settings_buttons", {})):
            return False
        adapter = self._new_utility_operation_adapter(phase="inspection")
        page.set_busy(True)

        def completed(availability: Any) -> None:
            page.set_busy(False)
            page.set_cursor_settings_availability(availability.available, availability.detail)

        adapter.finished.connect(completed)
        adapter.failed.connect(lambda message: page.set_cursor_settings_availability(False, str(message)))
        adapter.stopped.connect(lambda: page.set_busy(False))
        return bool(adapter.start(lambda: NativeHandoffService(probe_timeout=0.75).availability(
            NativeHandoffId.CURSOR_SETTINGS, profile=page.profile,
        )))

    def _open_cursor_settings(self: Any, page: Any) -> bool:
        """Revalidate asynchronously before opening the native cursor module."""
        from core.catalog_models import NativeHandoffId
        from services.desktop.native_handoff import NativeHandoffService
        from PyQt6.QtCore import QProcess

        if (self._utility_operation_adapter is not None or getattr(self, "_pending_runtime_shutdown", None)
                or getattr(self, "_runtime_cleaned", False) or not getattr(page, "cursor_settings_buttons", {})):
            return False
        adapter = self._new_utility_operation_adapter(phase="inspection")
        page.set_busy(True, self.tr("Checking Cursor Settings before opening…"))

        def completed(launch: Any) -> None:
            if getattr(self, "_pending_runtime_shutdown", None) or getattr(self, "_runtime_cleaned", False):
                return
            if launch is None:
                page.set_cursor_settings_availability(False, self.tr("Cursor Settings is unavailable. Refresh to check again."))
                return
            result = QProcess.startDetached(launch.program, list(launch.arguments))
            started = result[0] if isinstance(result, tuple) else bool(result)
            page.set_busy(False, self.tr("Cursor Settings opened. Refresh after making a change.") if started else self.tr("Cursor Settings could not be started."))

        adapter.finished.connect(completed)
        adapter.failed.connect(lambda message: page.set_cursor_settings_availability(False, str(message)))
        adapter.stopped.connect(lambda: page.set_busy(False))
        return bool(adapter.start(lambda: NativeHandoffService(probe_timeout=0.75).prepare_launch(
            NativeHandoffId.CURSOR_SETTINGS, profile=page.profile,
        )))
