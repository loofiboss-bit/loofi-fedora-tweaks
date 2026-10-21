"""Selenium AT-SPI helpers for native Qt widgets and the guest Polkit agent."""

from __future__ import annotations

import os
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
import time
from threading import Event
import xml.etree.ElementTree as ET

from selenium.webdriver.common.by import By


_driver = None


def observe_refresh(read_enabled: Callable[[], bool], started: Event, completed: Event, stop: Event,
                    *, timeout: float = 90, poll_interval: float = 0.01) -> None:
    """Observe an enabled→disabled→enabled refresh cycle, never just a ready button.

    The caller owns the thread and propagates read failures. ``stop`` is set on
    every exit so cancellation, timeout and exceptions terminate observation.
    ``read_enabled`` must invalidate any AT-SPI cache before reading live state.
    """
    if timeout <= 0 or poll_interval <= 0:
        raise ValueError("Observation timeout and poll interval must be positive")
    ready_seen = False
    try:
        deadline = time.monotonic() + timeout
        while not stop.is_set() and time.monotonic() < deadline:
            enabled = read_enabled()
            if stop.is_set():
                return
            if enabled and not started.is_set():
                ready_seen = True
            elif not enabled and ready_seen:
                started.set()
            elif enabled and started.is_set():
                completed.set()
                return
            time.sleep(poll_interval)
    finally:
        stop.set()


def use_driver(driver) -> None:
    global _driver
    _driver = driver


def _wayland_input() -> bool:
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        return False
    if not os.environ.get("KWIN_PID"):
        raise AssertionError("Wayland input requires the guest compositor PID")
    return True


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
        x, y = int(rect["x"] + rect["width"] / 2), int(rect["y"] + rect["height"] / 2)
        if _wayland_input():
            _driver.execute("actions", {"actions": [{
                "type": "pointer", "id": "loofi-guest-mouse", "parameters": {"pointerType": "mouse"},
                "actions": [{"type": "pointerMove", "duration": 0, "x": x, "y": y, "origin": "viewport"},
                            {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}],
            }]})
        else:
            pyatspi.Registry.generateMouseEvent(x, y, "b1c")

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
    if role == "action button":
        tag = "*[self::button or self::push_button or self::toggle_button or self::check_box]"
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


def wait_for_setting_feedback(setting: str, value: str, *, restored: bool = False,
                              session_activation: bool = False, timeout: float = 90) -> None:
    """Verify the requested and read-back values on one exact setting row."""
    status = wait_for_node(setting + " status", timeout=timeout)

    def matches() -> bool:
        description = status.description
        return (description.startswith("Saved —")
                and f"Requested: {value} · Verified: {value}" in description
                and (not restored or "Previous value restored." in description)
                and (not session_activation or "Session activation:" in description))

    wait_until(matches, timeout=timeout,
               message=f"{setting} did not report requested and verified value {value!r}"
                       + (" after restoration" if restored else ""))


def select_search(text: str) -> None:
    search = wait_for_node("Search tweaks", role="text")
    search.element.clear()
    search.element.send_keys(text)


def choose_next_value() -> None:
    combo = wait_for_node("DNF parallel downloads", role="combo box", enabled=True)
    combo.click()
    wait_for_node("5 downloads", role="list item").click()


def confirm_yes() -> None:
    # ReviewedActionDialog keeps the exact setting scope and recovery guidance
    # beside the single approval. System-wide operations require checking the
    # explicit no-automatic-rollback acknowledgement before applying.
    try:
        wait_for_node("Accept that this action has no automatic rollback", timeout=1).click()
    except AssertionError:
        pass
    click("Apply and verify", timeout=15)


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


def authenticate_polkit(*, completed: Callable[[], bool], timeout: float = 60) -> None:
    """Authenticate a visible request, or accept cached auth after state readback."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if completed():
                return
            raise AssertionError(
                "The Polkit prompt did not appear and the requested system state was not verified."
            )
        try:
            field = wait_for_polkit_password(timeout=min(1, remaining))
            break
        except AssertionError:
            if completed():
                return
    # WebDriver logs are not enabled; collected reports are additionally redacted.
    credential = json.loads(Path(os.environ["LOOFI_E2E_CREDENTIALS_PATH"]).read_text())
    # Protected Qt password widgets require native key events. The upstream
    # WebDriver fallback returns HTTP 404 after synthesizing successful input.
    import pyatspi
    field.click()
    if _wayland_input():
        actions = []
        for character in credential["password"]:
            actions.extend(({"type": "keyDown", "value": character}, {"type": "keyUp", "value": character}))
        _driver.execute("actions", {"actions": [{"type": "key", "id": "loofi-guest-keyboard", "actions": actions}]})
    else:
        for character in credential["password"]:
            pyatspi.Registry.generateKeyboardEvent(ord(character), None, pyatspi.KEY_SYM)
            time.sleep(0.03)
    selector = ("//application[@name='polkit-kde-authentication-agent-1']//button"
                "[(@name='OK' or @name='Authenticate') and contains(@states,'showing') and contains(@states,'enabled')]")
    button = _driver.find_element(By.XPATH, selector)
    Accessible(button, selector).click()


def activate_control(name: str) -> None:
    """Focus one exact accessible action, then deliver a native Space key."""
    import pyatspi
    selector = ("//*[self::button or self::check_box or self::toggle_button or self::push_button_menu or self::combo_box]"
                f"[@name={_literal(name)} and contains(@states,'enabled')]")
    node = Accessible(_driver.find_element(By.XPATH, selector), selector)
    path = node._source().get("path", "")
    assert path, f"Accessible action has no stable tree path: {name}"
    target = pyatspi.Registry.getDesktop(0)
    for index in path.split():
        target = target[int(index)]
    assert target.name == name, f"Accessible path resolved a different control: {target.name!r}, expected {name!r}"

    def focused():
        target.queryComponent().grabFocus()
        target.clear_cache_single()
        return target.getState().contains(pyatspi.STATE_FOCUSED)
    wait_until(focused, timeout=10, message=f"Control did not receive keyboard focus: {name}")
    if _wayland_input():
        _driver.execute("actions", {"actions": [{"type": "key", "id": "loofi-guest-keyboard", "actions": [
            {"type": "keyDown", "value": " "}, {"type": "keyUp", "value": " "}]}]})
    else:
        pyatspi.Registry.generateKeyboardEvent(32, None, pyatspi.KEY_SYM)


def return_to_loofi_window() -> None:
    """Activate only the suite-owned Loofi frame after an external handoff."""
    import pyatspi
    frame = wait_for_node("Loofi Fedora Tweaks", role="frame").element.rect
    x, y = int(frame["x"] + frame["width"] / 2), int(frame["y"] + 5)
    if _wayland_input():
        _driver.execute("actions", {"actions": [{
            "type": "pointer", "id": "loofi-guest-mouse", "parameters": {"pointerType": "mouse"},
            "actions": [{"type": "pointerMove", "duration": 0, "x": x, "y": y, "origin": "viewport"},
                        {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}],
        }]})
    else:
        pyatspi.Registry.generateMouseEvent(x, y, "b1c")
    time.sleep(0.5)


def press_key(key: str) -> None:
    """Deliver one navigation key to the guest's focused native control."""
    import pyatspi
    # Native popup creation follows the pointer event asynchronously.
    time.sleep(0.5)
    values = {
        "home": (0xff50, "\ue011"), "end": (0xff57, "\ue010"),
        "left": (0xff51, "\ue012"), "up": (0xff52, "\ue013"),
        "right": (0xff53, "\ue014"), "down": (0xff54, "\ue015"),
        "enter": (0xff0d, "\ue007"), "escape": (0xff1b, "\ue00c"),
    }
    symbol, value = values[key]
    if _wayland_input():
        _driver.execute("actions", {"actions": [{"type": "key", "id": "loofi-guest-keyboard", "actions": [
            {"type": "keyDown", "value": value}, {"type": "keyUp", "value": value}]}]})
    else:
        pyatspi.Registry.generateKeyboardEvent(symbol, None, pyatspi.KEY_SYM)


def select_page_tab(name: str, *, timeout: float = 10) -> None:
    """Select an application page tab through focused, verified keyboard input."""
    import pyatspi

    names = ("Catalog", "Installed", "Sources")
    if name not in names:
        raise ValueError(f"Unsupported application tab: {name}")

    def accessible_tab(tab_name: str):
        selector = f"//page_tab[@name={_literal(tab_name)} and contains(@states, 'showing')]"
        return _driver.find_element(By.XPATH, selector)

    def tab_state(tab_name: str) -> str:
        return Accessible(accessible_tab(tab_name), "//page_tab")._source().get("states", "")

    current_name = next((tab for tab in names if "selected" in tab_state(tab)), None)
    if current_name is None:
        raise AssertionError("No application page tab is selected.")
    if current_name == name:
        return

    current = Accessible(accessible_tab(current_name), "//page_tab")
    path = current._source().get("path", "")
    if not path:
        raise AssertionError("Selected application tab has no stable AT-SPI path.")
    target = pyatspi.Registry.getDesktop(0)
    # Qt exposes each page as a focusable tab, while the focus belongs to the
    # containing QTabBar. Focus that accessible tab list, then use its native
    # horizontal arrow-key behavior instead of relying on child-tab bounds.
    tab_list_path = path.rsplit(" ", 1)[0]
    for index in tab_list_path.split():
        target = target[int(index)]
    if target.getRole() != pyatspi.ROLE_PAGE_TAB_LIST:
        raise AssertionError("Application tab path did not resolve the expected tab list.")
    if not target.queryComponent().grabFocus():
        raise AssertionError("Application tab list could not receive keyboard focus.")

    def focused() -> bool:
        target.clear_cache_single()
        return target.getState().contains(pyatspi.STATE_FOCUSED)

    wait_until(focused, timeout=timeout, message="Application tab list did not receive keyboard focus.")

    current_index = names.index(current_name)
    target_index = names.index(name)
    direction = "right" if target_index > current_index else "left"
    distance = abs(target_index - current_index)
    for _ in range(distance):
        press_key(direction)
    wait_until(lambda: "selected" in tab_state(name), timeout=timeout,
               message=f"Keyboard navigation did not select the {name} application tab")


def application_environment() -> dict[str, str]:
    """Apply an explicitly qualified runtime to application children only."""
    env = os.environ.copy()
    for key in ("LOOFI_E2E_POLKIT_PASSWORD", "LOOFI_E2E_CREDENTIALS_PATH", "LD_PRELOAD", "LD_LIBRARY_PATH"):
        env.pop(key, None)
    directory = env.get("LOOFI_E2E_QT_RUNTIME_DIR")
    if directory:
        expected = Path("/var/tmp/loofi-e2e/qt-runtime")
        evidence = json.loads((expected.parent / "qt-runtime-evidence.json").read_text())
        if directory != str(expected) or evidence.get("passed") is not True or evidence.get("runtime_library_dir") != directory:
            raise RuntimeError("Application corrected Qt runtime has no successful guest qualification.")
        library = expected / "libQt6Widgets.so.6.11.2"
        if hashlib.sha256(library.read_bytes()).hexdigest() != evidence.get("runtime_sha256"):
            raise RuntimeError("Application corrected Qt runtime changed after qualification.")
        env["LD_LIBRARY_PATH"] = directory
    return env


def record_application_runtime(process) -> None:
    """Read actual application mappings after startup, including every restart."""
    directory = os.environ.get("LOOFI_E2E_QT_RUNTIME_DIR")
    if not directory:
        return
    work = Path("/var/tmp/loofi-e2e")
    manifest = json.loads((work / "qt-runtime-request.json").read_text())["manifest"]
    mappings = (Path("/proc") / str(process.pid) / "maps").read_text()
    paths = {line.split(maxsplit=5)[5].strip() for line in mappings.splitlines() if len(line.split(maxsplit=5)) == 6}
    expected = {"Widgets": (Path(directory) / "libQt6Widgets.so.6.11.2", manifest["runtime_sha256"])}
    for name in ("Core", "Gui"):
        dependency = manifest["dependency_libraries"][name]
        expected[name] = (Path(dependency["path"]), dependency["sha256"])
    observed = {}
    for name, (path, checksum) in expected.items():
        if str(path) not in paths or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise RuntimeError(f"Application did not map the expected Qt{name} library.")
        observed[name] = {"path": str(path), "sha256": checksum}
    target = work / "qt-runtime-applications.json"
    records = json.loads(target.read_text()) if target.exists() else []
    records.append({"launch": "installed RPM Bash wrapper; library path inherited by ordinary app children, cleared by pkexec", "pid": process.pid, "phase": os.environ.get("LOOFI_E2E_PHASE", "normal"), "libraries": observed})
    target.write_text(json.dumps(records, indent=2) + "\n")


def current_app_process(registry):
    """Refuse ambiguous ownership instead of selecting a stale fixture PID."""
    live = [process for process in registry if process.poll() is None]
    assert len(live) == 1, f"Expected one live suite-owned app process, found {len(live)}"
    return live[0]


def restart_app(process, registry):
    """Restart only the suite-owned process, preserving its on-disk state."""
    import subprocess
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    env = application_environment()
    with open("/var/tmp/loofi-e2e/application.log", "a", encoding="utf-8") as log:
        restarted = subprocess.Popen(["/usr/bin/loofi-fedora-tweaks"], stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT, text=True, close_fds=True, env=env)
    registry.append(restarted)
    wait_for_node("Loofi Fedora Tweaks", role="frame", timeout=90)
    record_application_runtime(restarted)
    return restarted


def open_search_result(query: str, label: str, *, timeout: float = 30) -> None:
    """Open a result in the global dialog, never a hidden combo's list item."""
    try:
        search = wait_for_node("Global search", role="text", timeout=0.3)
    except AssertionError:
        click("Search routes, settings, and actions")
        search = wait_for_node("Global search", role="text")
    search.element.clear()
    search.element.send_keys(query)
    selector = ("//dialog[@name='Search Loofi' and contains(@states,'showing')]"
                "//list[@name='Search results']//list_item[contains(@name," + _literal(label) + ")]")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = Accessible(_driver.find_element(By.XPATH, selector), selector)
            result.click()
            return
        except Exception:
            time.sleep(0.25)
    raise AssertionError(f"Global search result was not available: {label}")
