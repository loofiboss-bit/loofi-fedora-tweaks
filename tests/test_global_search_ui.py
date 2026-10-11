"""UI contract tests for the shared v15 global-search surface."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from core.navigation import FedoraVariant, GlobalSearchModel, NavigationContext, SearchFilter, SearchResultKind  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QKeyEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from ui.global_search import GlobalSearchDialog  # noqa: E402


class TestGlobalSearchDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _model():
        return GlobalSearchModel(
            NavigationContext(
                fedora_variant=FedoraVariant.TRADITIONAL,
                capabilities=frozenset({"fedora", "dnf5"}),
            )
        )

    def test_primary_search_activation_returns_canonical_navigation_descriptor(self):
        callback = MagicMock()
        dialog = GlobalSearchDialog(self._model(), callback)
        self.addCleanup(dialog.close)
        for label, target in (("Tweaks", "utility:tune"), ("Apps", "utility:install"), ("Health", "utility:fix"), ("Activity", "activity")):
            with self.subTest(page=label):
                callback.reset_mock()
                dialog.search_input.setText(label)
                item = dialog.results_list.item(0)
                result = item.data(Qt.ItemDataRole.UserRole)
                self.assertEqual((result.label, result.route_id), (label, target))
                dialog._activate_item(item)
                callback.assert_called_once_with(result)

    def test_search_navigation_keeps_task_focus_without_starting_operations(self):
        from ui.main_window_interactions import MainWindowInteractionMixin

        host = MagicMock()
        host.switch_to_route.return_value = True
        result = next(item for item in self._model().task_results() if item.task_id == "install:flatpaks")
        self.assertTrue(MainWindowInteractionMixin._activate_global_search_result(host, result))
        host.switch_to_route.assert_called_once_with("install")
        host._focus_utility_task.assert_called_once_with("install:flatpaks", "install")
        host._preselect_action_center.assert_not_called()
        host._start_utility_operation.assert_not_called()

    def test_guide_search_result_is_labeled_and_activates_navigation_only(self):
        callback = MagicMock()
        dialog = GlobalSearchDialog(self._model(), callback)
        dialog.search_input.setText("battery")

        item = next(
            dialog.results_list.item(row)
            for row in range(dialog.results_list.count())
            if dialog.results_list.item(row).data(Qt.ItemDataRole.UserRole).kind is SearchResultKind.GUIDE
        )
        result = item.data(Qt.ItemDataRole.UserRole)
        self.assertEqual(result.kind, SearchResultKind.GUIDE)
        self.assertEqual((result.route_id, result.guide_id), ("overview", "solve-a-problem"))
        self.assertIn("Guide", item.text())

        dialog._activate_item(item)

        callback.assert_called_once_with(result)
        self.assertIsNone(result.action_id)

    def test_actions_filter_uses_same_dialog_and_model(self):
        dialog = GlobalSearchDialog(
            self._model(),
            MagicMock(),
            search_filter=SearchFilter.ACTIONS,
        )

        self.assertTrue(dialog._visible_results)
        self.assertTrue(
            all(
                result.kind is SearchResultKind.ACTION
                for result in dialog._visible_results
            )
        )

    def test_activation_returns_descriptor_without_executing_action(self):
        callback = MagicMock()
        dialog = GlobalSearchDialog(
            self._model(),
            callback,
            search_filter=SearchFilter.ACTIONS,
        )
        item = dialog.results_list.item(0)

        dialog._activate_item(item)

        callback.assert_called_once_with(item.data(Qt.ItemDataRole.UserRole))

    def test_keyboard_down_and_up_change_selection(self):
        dialog = GlobalSearchDialog(self._model(), MagicMock())
        self.assertGreater(dialog.results_list.count(), 1)

        dialog.keyPressEvent(
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        )
        self.assertEqual(dialog.results_list.currentRow(), 1)

        dialog.keyPressEvent(
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        )
        self.assertEqual(dialog.results_list.currentRow(), 0)

    def test_enter_activates_current_result(self):
        callback = MagicMock()
        dialog = GlobalSearchDialog(self._model(), callback)

        dialog.keyPressEvent(
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        )

        callback.assert_called_once()

    def test_legacy_command_palette_delegates_to_global_search(self):
        from ui.command_palette import CommandPalette

        with patch("ui.command_palette.GlobalSearchModel") as model_cls:
            model_cls.return_value = GlobalSearchModel()
            palette = CommandPalette(MagicMock())

        self.assertIsInstance(palette, GlobalSearchDialog)


if __name__ == "__main__":
    unittest.main()
