"""Selenium AT-SPI helpers for native Qt widgets and the guest Polkit agent."""

from __future__ import annotations

import os
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

from selenium.webdriver.common.by import By


_driver = None


def use_driver(driver) -> None:
    global _driver
    _driver = driver


def _literal(text: str) -> str:
    if "'" not in text:
        return "'" + text + "'"
    if '"' not in text:
        return '"' + text + '"'
    raise ValueError("Use accessible names without both quote characters in selectors.")


class Accessible:
    def __init__(self, element, selector: str):
        self.element = element
        self.selector = selector

    def click(self) -> None:
        # Discover bounds through Selenium and use AT-SPI's native X11 input.
        # Qt's custom item/control actions do not consistently expose Press.
        import pyatspi
        rect = self.element.rect
        assert self.element.is_enabled(), "Accessible control is disabled"
        assert "showing" in self._source().get("states", ""), "Accessible control is not visible"
        pyatspi.Registry.generateMouseEvent(int(rect["x"] + rect["width"] / 2),
                                            int(rect["y"] + rect["height"] / 2), "b1c")

    @property
    def sensitive(self) -> bool:
        return self.element.is_enabled()

    @property
    def checked(self) -> bool:
        return "checked" in self._source().get("states", "").lower()

    @property
    def description(self) -> str:
        return self._source().get("description", "")

    def _source(self):
        # WebDriver's AT-SPI attribute endpoint exposes states; descriptions are
        # carried by page source. Resolve by the stable accessible name/role.
        name = self.element.get_dom_attribute("name")
        identifier = self.element.get_dom_attribute("accessibility-id")
        for node in ET.fromstring(_driver.page_source).iter():
            role = self.selector.rsplit("//", 1)[1].split("[", 1)[0]
            if (node.get("name") == name and (role == "*" or node.tag == role)
                    and (not identifier or node.get("accessibility-id") == identifier)):
                return node
        raise AssertionError(f"Accessible node disappeared: {name}")


def wait_for_node(name: str, *, role: str | None = None, timeout: float = 20, enabled: bool = False):
    print(f"Waiting for accessible control: {name!r}", flush=True)
    tag = "*" if role is None else role.replace(" ", "_")
    selector = f"//{tag}[@name={_literal(name)}]"
    if role == "combo box" and name == "DNF parallel downloads":
        # Qt exposes a combo's selected label as its name, while its enclosing
        # setting row retains the stable setting title.
        selector = f"//panel[@name={_literal(name)}]//combo_box"
    selector += "[contains(@states, 'showing')]"
    if enabled:
        selector += "[contains(@states, 'enabled')]"
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            return Accessible(_driver.find_element(By.XPATH, selector), selector)
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise AssertionError(f"AT-SPI node {name!r} was not found: {last_error}")


def wait_for_node_containing(fragment: str, *, role: str, timeout: float = 20):
    """Find one visible native control whose accessible name contains text."""
    tag = role.replace(" ", "_")
    selector = f"//{tag}[contains(@name,{_literal(fragment)}) and contains(@states, 'showing')]"
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            return Accessible(_driver.find_element(By.XPATH, selector), selector)
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise AssertionError(f"AT-SPI node containing {fragment!r} was not found: {last_error}")


def click(name: str, *, timeout: float = 20):
    node = wait_for_node(name, timeout=timeout)
    node.click()
    return node


def wait_until(predicate, *, timeout: float = 30, message: str = "condition did not become true") -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.25)
    raise AssertionError(message)


def wait_for_description(description: str, *, timeout: float = 30):
    print(f"Waiting for feedback: {description!r}", flush=True)
    selector = f"//*[starts-with(@description,{_literal(description)}) and contains(@states, 'showing')]"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return Accessible(_driver.find_element(By.XPATH, selector), selector)
        except Exception:
            time.sleep(0.25)
    raise AssertionError(f"AT-SPI description {description!r} was not found")


def select_search(text: str) -> None:
    search = wait_for_node("Search tweaks", role="text")
    search.element.clear()
    search.element.send_keys(text)


def choose_next_value() -> None:
    combo = wait_for_node("DNF parallel downloads", role="combo box", enabled=True)
    combo.click()
    wait_for_node("5 (Fast)", role="list item").click()


def confirm_yes() -> None:
    click("Yes", timeout=15)


def cancel_dialog() -> None:
    click("Cancel", timeout=20)


def wait_for_polkit_password(timeout: float = 30):
    selector = "//application[@name='polkit-kde-authentication-agent-1']//password_text"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return Accessible(_driver.find_element(By.XPATH, selector), selector)
        except Exception:
            time.sleep(0.25)
    raise AssertionError("The guest Polkit password field did not appear.")


def authenticate_polkit(*, allow_cached: bool = False) -> None:
    try:
        field = wait_for_polkit_password(timeout=5 if allow_cached else 30)
    except AssertionError:
        if allow_cached:
            return
        raise
    # WebDriver logs are not enabled; collected reports are additionally redacted.
    credential = json.loads(Path(os.environ["LOOFI_E2E_CREDENTIALS_PATH"]).read_text())
    # Protected Qt password widgets require native key events. The upstream
    # WebDriver fallback returns HTTP 404 after synthesizing successful input.
    import pyatspi
    field.click()
    for character in credential["password"]:
        pyatspi.Registry.generateKeyboardEvent(ord(character), None, pyatspi.KEY_SYM)
        time.sleep(0.03)
    selector = ("//application[@name='polkit-kde-authentication-agent-1']//button"
                "[(@name='OK' or @name='Authenticate') and contains(@states,'showing') and contains(@states,'enabled')]")
    button = _driver.find_element(By.XPATH, selector)
    Accessible(button, selector).click()
