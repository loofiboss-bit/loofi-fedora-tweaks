"""v32 catalog breadth, default values, and changed-from-default UI."""

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QToolButton

from core.tasks.tweaks import BY_ID, TWEAKS, TweakState, default_for, visible_tweaks
from core.tweak_commands import valid_value
from ui.tweaks_page import TweaksPage


def _profile(desktop: str) -> SimpleNamespace:
    return SimpleNamespace(
        is_fedora=True,
        desktop=SimpleNamespace(value=desktop),
        deployment_backend=SimpleNamespace(value="dnf5"),
    )


class TestV32TweakCatalog(unittest.TestCase):
    def test_catalog_has_at_least_fifty_controls(self) -> None:
        self.assertGreaterEqual(len(TWEAKS), 50)
        self.assertEqual(len({t.id for t in TWEAKS}), len(TWEAKS))
        self.assertEqual(len({t.action_id for t in TWEAKS}), len(TWEAKS))

    def test_each_desktop_has_enough_controls(self) -> None:
        self.assertGreaterEqual(len(visible_tweaks(_profile("gnome"))), 35)
        self.assertGreaterEqual(len(visible_tweaks(_profile("kde"))), 18)

    def test_defaults_are_valid_curated_choices(self) -> None:
        for tweak in TWEAKS:
            default = default_for(tweak)
            if tweak.id == "kde-color":
                self.assertEqual(default, "")
                continue
            with self.subTest(tweak=tweak.id):
                self.assertTrue(default, "missing default")
                self.assertTrue(valid_value(tweak.id, default))
                if tweak.choices:  # power-profile choices are read from the system
                    self.assertIn(default, {value for value, _label in tweak.choices})


class TestV32TweakPageDefaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_changed_rows_offer_reset_and_filter(self) -> None:
        page = TweaksPage(_profile("gnome"))
        try:
            requests = []
            page.changeRequested.connect(lambda tid, value: requests.append((tid, value)))
            tweak = BY_ID["gnome-hot-corners"]
            other = BY_ID["gnome-edge-tiling"]
            choices = tweak.choices
            page.set_states((
                TweakState(tweak, "ready", value="false", choices=choices),
                TweakState(other, "ready", value="true", choices=other.choices),
            ))
            reset = page._reset_buttons["gnome-hot-corners"]
            self.assertEqual(reset.text(), "Use Loofi standard value")
            self.assertFalse(reset.isHidden())
            self.assertTrue(page._reset_buttons["gnome-edge-tiling"].isHidden())
            reset.click()
            self.assertEqual(requests, [("gnome-hot-corners", "true")])
            page.changed_only.setChecked(True)
            self.assertIn("Loofi's standard value", page.changed_only.toolTip())
            self.assertFalse(page._rows["gnome-hot-corners"][0].isHidden())
            self.assertTrue(page._rows["gnome-edge-tiling"][0].isHidden())
        finally:
            page.close()

    def test_details_distinguish_loofi_standard_from_user_scope(self) -> None:
        page = TweaksPage(_profile("gnome"))
        try:
            tweak = BY_ID["gnome-hot-corners"]
            page.set_states((TweakState(tweak, "ready", value="false", choices=tweak.choices),))
            menu_button = page._rows[tweak.id][0].findChild(QToolButton, "tweakRowActions")
            details = menu_button.menu().actions()[1].defaultWidget()
            self.assertIsInstance(details, QLabel)
            self.assertIn("Loofi standard:", details.text())
            self.assertIn("Current user", details.text())
        finally:
            page.close()

    def test_snapshot_progress_cancel_and_partial_count_are_visible(self) -> None:
        page = TweaksPage(_profile("gnome"))
        try:
            cancellations = []
            page.cancelSnapshotRequested.connect(lambda: cancellations.append(True))
            page.set_busy(True, "Reading settings", cancellable=True)
            page.snapshotProgress.emit(2, 4)
            self.assertIn("2 of 4", page.status_label.text())
            self.assertFalse(page.cancel_snapshot_button.isHidden())
            page.cancel_snapshot_button.click()
            self.assertEqual(cancellations, [True])

            first, second = BY_ID["gnome-hot-corners"], BY_ID["gnome-edge-tiling"]
            page.set_states((
                TweakState(first, "ready", value="true", choices=first.choices),
                TweakState(second, "unavailable", message="Not checked because the 20-second setting inspection limit was reached."),
            ))
            self.assertIn("1 of 2 settings checked", page.status_label.text())
            self.assertIn("remain unknown", page.status_label.text())
            self.assertTrue(page.cancel_snapshot_button.isHidden())
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
