"""Session-specific native guest input without host desktop interaction."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch


class TestGuestNativeInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name = "loofi_e2e_native_helpers"
        by = ModuleType("selenium.webdriver.common.by")
        by.By = Mock()
        modules = {key: ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common")}
        modules["selenium.webdriver.common.by"] = by
        path = Path(__file__).resolve().parents[1] / "e2e/tests/helpers.py"
        spec = importlib.util.spec_from_file_location(name, path)
        cls.helpers = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(cls.helpers)

    def setUp(self):
        self.driver = Mock()
        self.helpers.use_driver(self.driver)
        self.element = Mock()
        self.element.rect = {"x": 20, "y": 40, "width": 100, "height": 60}
        self.element.is_enabled.return_value = True
        self.node = self.helpers.Accessible(self.element, "//button")
        self.node._source = Mock(return_value={"states": "showing enabled"})
        self.pyatspi = ModuleType("pyatspi")
        self.pyatspi.Registry = Mock()

    def tearDown(self):
        self.helpers.use_driver(None)

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland", "KWIN_PID": "123"})
    def test_wayland_click_uses_compositor_actions(self):
        with patch.dict(sys.modules, {"pyatspi": self.pyatspi}):
            self.node.click()
        self.pyatspi.Registry.generateMouseEvent.assert_not_called()
        command, payload = self.driver.execute.call_args.args
        self.assertEqual(command, "actions")
        self.assertEqual(payload["actions"][0]["actions"][0]["x"], 70)
        self.assertEqual(payload["actions"][0]["actions"][0]["y"], 70)
        self.assertEqual(payload["actions"][0]["actions"][1]["type"], "pointerDown")
        self.assertEqual(payload["actions"][0]["actions"][2]["type"], "pointerUp")

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11", "KWIN_PID": "123"})
    def test_x11_uses_native_atspi_even_with_inherited_compositor_pid(self):
        with patch.dict(sys.modules, {"pyatspi": self.pyatspi}):
            self.node.click()
        self.pyatspi.Registry.generateMouseEvent.assert_called_once_with(70, 70, "b1c")
        self.driver.execute.assert_not_called()

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland", "KWIN_PID": ""})
    def test_wayland_missing_compositor_never_falls_back_to_x11(self):
        with patch.dict(sys.modules, {"pyatspi": self.pyatspi}):
            with self.assertRaisesRegex(AssertionError, "compositor PID"):
                self.node.click()
        self.pyatspi.Registry.generateMouseEvent.assert_not_called()
        self.driver.execute.assert_not_called()

    def test_global_search_clears_prior_text_and_scopes_result_to_dialog(self):
        search = Mock()
        with patch.object(self.helpers, "wait_for_node", return_value=search), patch.object(self.helpers.Accessible, "click"):
            self.helpers.open_search_result("Install Apps", "Apps")
        search.element.clear.assert_called_once()
        search.element.send_keys.assert_called_once_with("Install Apps")
        selector = self.driver.find_element.call_args.args[1]
        self.assertIn("//dialog[@name='Search Loofi'", selector)
        self.assertIn("//list[@name='Search results']//list_item", selector)

    def test_restart_uses_the_live_process_after_an_earlier_guide_restart(self):
        original, replacement = Mock(), Mock()
        original.poll.return_value = 0
        replacement.poll.return_value = None
        self.assertIs(self.helpers.current_app_process([original, replacement]), replacement)

    def test_ambiguous_live_apps_are_not_silently_selected(self):
        first, second = Mock(), Mock()
        first.poll.return_value = second.poll.return_value = None
        with self.assertRaisesRegex(AssertionError, "found 2"):
            self.helpers.current_app_process([first, second])

    @patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
    def test_accessible_activation_requires_focus_before_native_space(self):
        self.pyatspi.STATE_FOCUSED = 12
        self.pyatspi.KEY_SYM = 2
        target = Mock()
        target.name = "Skip step"
        target.queryComponent.return_value.grabFocus.return_value = True
        target.getState.return_value.contains.return_value = True
        desktop = {3: {2: target}}
        self.pyatspi.Registry.getDesktop.return_value = desktop
        with patch.dict(sys.modules, {"pyatspi": self.pyatspi}), patch.object(
            self.helpers.Accessible, "_source", return_value=ET.Element("button", {"path": "3 2"})
        ):
            self.helpers.activate_control("Skip step")
        target.queryComponent.return_value.grabFocus.assert_called_once()
        target.getState.return_value.contains.assert_called_with(12)
        self.pyatspi.Registry.generateKeyboardEvent.assert_called_once_with(32, None, 2)
