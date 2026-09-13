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
