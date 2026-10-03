"""v32 catalog breadth, default values, and changed-from-default UI."""

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

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
            self.assertFalse(reset.isHidden())
            self.assertTrue(page._reset_buttons["gnome-edge-tiling"].isHidden())
            reset.click()
            self.assertEqual(requests, [("gnome-hot-corners", "true")])
            page.changed_only.setChecked(True)
            self.assertFalse(page._rows["gnome-hot-corners"][0].isHidden())
            self.assertTrue(page._rows["gnome-edge-tiling"][0].isHidden())
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
