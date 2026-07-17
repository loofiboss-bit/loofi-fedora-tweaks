"""Focused tests for spec-backed top-level plugin activation."""

import os
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from core.plugins.spec import BUILTIN_PLUGIN_SPECS
from ui.lazy_widget import LazyWidget
from ui.main_window import MainWindow


class TestLazyPluginShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window_shell(self):
        window = SimpleNamespace()
        window._plugin_loader = MagicMock()
        window._plugin_context = {"main_window": window}
        window.tr = lambda value: value
        window._schedule_post_render_services = MagicMock()
        window._load_plugin_widget = MethodType(MainWindow._load_plugin_widget, window)
        return window

    def test_spec_wrapper_imports_only_when_realized(self):
        window = self._window_shell()
        plugin = MagicMock()
        widget = QWidget()
        plugin.create_widget.return_value = widget
        window._plugin_loader.load_builtin_widget.return_value = widget
        spec = BUILTIN_PLUGIN_SPECS[0]

        lazy = MainWindow._wrap_spec_in_lazy(window, spec)

        window._plugin_loader.load_builtin_widget.assert_not_called()
        self.assertIs(lazy.ensure_loaded(), widget)
        window._plugin_loader.load_builtin_widget.assert_called_once_with(
            spec.id,
            context=window._plugin_context,
        )

    def test_reopening_route_reuses_lazy_widget_result(self):
        calls = 0

        def load():
            nonlocal calls
            calls += 1
            return QWidget()

        lazy = LazyWidget(load)

        first = lazy.ensure_loaded()
        second = lazy.ensure_loaded()

        self.assertIs(first, second)
        self.assertEqual(calls, 1)

    def test_import_failure_renders_page_level_error(self):
        def fail():
            raise ImportError("optional module is unavailable")

        lazy = LazyWidget(fail)

        self.assertIsNone(lazy.ensure_loaded())
        self.assertEqual(lazy.load_error, "optional module is unavailable")
        error = lazy.findChild(QLabel, "errorLabel")
        self.assertIsNotNone(error)
        self.assertIn("could not be loaded", error.text())
        self.assertIn("optional module is unavailable", error.text())

    def test_non_widget_plugin_result_becomes_error_state(self):
        window = self._window_shell()
        plugin = MagicMock()
        plugin.create_widget.return_value = object()
        window._plugin_loader.load_builtin_widget.return_value = object()
        spec = BUILTIN_PLUGIN_SPECS[0]
        lazy = MainWindow._wrap_spec_in_lazy(window, spec)

        self.assertIsNone(lazy.ensure_loaded())
        self.assertIn("did not create a QWidget", lazy.load_error)


if __name__ == "__main__":
    unittest.main()
