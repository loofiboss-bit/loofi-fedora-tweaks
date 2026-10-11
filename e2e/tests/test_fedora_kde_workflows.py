"""Real desktop workflows run only inside the disposable Fedora KDE guest."""

from __future__ import annotations

import os
import re
import subprocess
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import helpers

from helpers import (
    authenticate_polkit,
    cancel_dialog,
    choose_next_value,
    click,
    confirm_yes,
    select_search,
    wait_for_description,
    wait_for_node,
    wait_for_node_containing,
    wait_for_polkit_password,
    wait_until,
)


def dnf_parallel_downloads() -> str:
    result = subprocess.run(
        ["dnf5", "--dump-main-config"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    for line in result.stdout.splitlines():
        match = re.match(r"\s*max_parallel_downloads\s*=\s*(\S+)", line)
        if match:
            return match.group(1)
    raise AssertionError("dnf5 --dump-main-config did not report max_parallel_downloads")


def wait_for_feedback(name: str, timeout: int = 90) -> None:
    wait_for_description(name, timeout=timeout)


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def test_polkit_helper_waits_for_a_delayed_password_prompt() -> None:
    password_field = Mock()
    wait_for_password = Mock(side_effect=[AssertionError("not ready"), AssertionError("not ready"), password_field])
    completion = Mock(return_value=False)
    pyatspi = ModuleType("pyatspi")
    keyboard_event = Mock()
    pyatspi.Registry = SimpleNamespace(generateKeyboardEvent=keyboard_event)
    pyatspi.KEY_SYM = 1

    with (
        patch("helpers.wait_for_polkit_password", side_effect=wait_for_password),
        patch("helpers._driver", Mock()),
        patch("helpers.Accessible.click"),
        patch("helpers.Path.read_text", return_value='{"password":"x"}'),
        patch("helpers.time.sleep"),
        patch.dict("os.environ", {"LOOFI_E2E_CREDENTIALS_PATH": "/tmp/loofi-e2e-credentials.json"}),
        patch.dict("sys.modules", {"pyatspi": pyatspi}),
    ):
        authenticate_polkit(completed=completion, timeout=5)

    assert wait_for_password.call_count == 3
    assert completion.call_count == 2
    keyboard_event.assert_called_once_with(ord("x"), None, pyatspi.KEY_SYM)


def test_polkit_helper_accepts_cached_authorization_only_after_readback() -> None:
    wait_for_password = Mock(side_effect=AssertionError("prompt is cached"))
    completion = Mock(side_effect=[False, False, True])

    with patch("helpers.wait_for_polkit_password", side_effect=wait_for_password):
        authenticate_polkit(completed=completion, timeout=5)

    assert wait_for_password.call_count == 3
    assert completion.call_count == 3


def dolphin_full_path_enabled() -> bool:
    result = subprocess.run(
        ["kreadconfig6", "--file", "dolphinrc", "--group", "General", "--key", "ShowFullPath", "--default", "false"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    assert result.stdout.strip().lower() in {"true", "false"}
    return result.stdout.strip().lower() == "true"


def _has_node(name: str) -> bool:
    try:
        wait_for_node(name, timeout=0.1)
        return True
    except AssertionError:
        return False


def test_navigation_user_setting_verification_and_restore(loofi_app) -> None:
    wait_for_node("Tweaks", role="table cell").click()
    wait_for_node("Fedora tweaks", timeout=30)

    select_search("Show full path in location bar")
    control = wait_for_node("Show full path in location bar", role="check box", timeout=30)
    assert control.sensitive, "Dolphin setting should be available in the Fedora KDE guest"
    before = control.checked
    assert dolphin_full_path_enabled() == before
    control.click()
    wait_for_feedback("Saved — Saved setting verified: " + ("Off" if before else "On"))
    assert dolphin_full_path_enabled() != before

    restore_name = "Restore previous value for Show full path in location bar"
    wait_until(lambda: _has_node(restore_name), timeout=30, message="verified change did not offer restoration")
    click(restore_name)
    confirm_yes()
    wait_for_feedback("Saved — Previous value restored and verified: " + ("On" if before else "Off"))
    assert dolphin_full_path_enabled() == before

    wait_for_node("Activity", role="table cell").click()
    wait_for_node("Activity search", role="text", timeout=30)
    wait_for_node("Tweaks", role="table cell").click()
    wait_for_node("Fedora tweaks", timeout=30)


def test_cancelled_system_confirmation_does_not_change_dnf(loofi_app) -> None:
    wait_for_node("Tweaks", role="table cell").click()
    before = dnf_parallel_downloads()
    assert before == "3", "golden Fedora baseline should retain the Fedora default"
    select_search("DNF parallel downloads")
    wait_for_node("DNF parallel downloads", role="combo box", timeout=60, enabled=True)
    choose_next_value()
    wait_for_node("Change system setting", timeout=20)
    cancel_dialog()
    assert dnf_parallel_downloads() == before


def test_polkit_denial_and_authorized_change_restore(loofi_app, app_process_registry) -> None:
    wait_for_node("Tweaks", role="table cell").click()
    before = dnf_parallel_downloads()
    assert before == "3"
    select_search("DNF parallel downloads")
    wait_for_node("DNF parallel downloads", role="combo box", timeout=60, enabled=True)

    choose_next_value()
    wait_for_node("Change system setting", timeout=20)
    confirm_yes()
    wait_for_polkit_password(timeout=30)
    cancel_dialog()
    wait_until(lambda: dnf_parallel_downloads() == before, timeout=30, message="cancelled Polkit request changed DNF configuration")
    status = wait_for_node("DNF parallel downloads status", timeout=30)
    wait_until(lambda: status.description.startswith("Error —")
               and any(code in status.description for code in ("Exit 126:", "Exit 127:"))
               and any(reason in status.description for reason in ("Not authorized", "Request dismissed")),
               timeout=30, message="cancelled Polkit request did not show actionable error feedback")
    # The operation adapter performs a fresh read after denied authorization.
    wait_for_node("DNF parallel downloads", role="combo box", timeout=60, enabled=True)

    choose_next_value()
    wait_for_node("Change system setting", timeout=20)
    confirm_yes()
    authenticate_polkit(completed=lambda: dnf_parallel_downloads() == "5")
    wait_for_feedback("Saved — Saved setting verified: 5 (Fast)", timeout=90)
    assert dnf_parallel_downloads() == "5"

    restarted_app = None
    application_log = None
    try:
        _stop_process(loofi_app)
        app_env = os.environ.copy()
        app_env.pop("LOOFI_E2E_POLKIT_PASSWORD", None)
        app_env.pop("LOOFI_E2E_CREDENTIALS_PATH", None)
        application_log = open("/var/tmp/loofi-e2e/application.log", "a", encoding="utf-8")
        restarted_app = subprocess.Popen(
            ["/usr/bin/loofi-fedora-tweaks"],
            stdin=subprocess.DEVNULL,
            stdout=application_log,
            stderr=subprocess.STDOUT,
            text=True,
            close_fds=True,
            env=app_env,
        )
        app_process_registry.append(restarted_app)
        wait_for_node("Loofi Fedora Tweaks", role="frame", timeout=90)
        wait_for_node("Tweaks", role="table cell").click()
        select_search("DNF parallel downloads")
        combo = wait_for_node("DNF parallel downloads", role="combo box", timeout=60, enabled=True)
        assert combo.element.get_dom_attribute("name") == "5 (Fast)", "reopened app did not read the saved DNF value"
        assert dnf_parallel_downloads() == "5", "DNF value did not persist across an application restart"

        restore_name = "Restore previous value for DNF parallel downloads"
        wait_until(lambda: _has_node(restore_name), timeout=30, message="persisted change history did not offer restoration")
        click(restore_name)
        wait_for_node("Restore previous value", timeout=30)
        confirm_yes()
        authenticate_polkit(completed=lambda: dnf_parallel_downloads() == before)
        wait_for_feedback("Saved — Previous value restored and verified: 3 (Fedora default)", timeout=90)
        assert dnf_parallel_downloads() == before, "DNF restore feedback did not match the real system state"
    finally:
        if application_log is not None:
            application_log.close()


def test_device_troubleshooting_profiles_are_reachable_from_health_and_search(loofi_app) -> None:
    wait_for_node("Health", role="table cell").click()
    profiles = (
        ("charging", "Battery or power problem", "Battery charge, AC power, and energy profile"),
        ("docking", "Display or docking problem", "Connected displays, active modes, and scale"),
        ("touchpad", "Keyboard or touchpad problem", "Keyboard, pointer, and touchpad metadata"),
        ("print queue", "Printer or print queue problem", "CUPS service, queue state, and current-user jobs"),
    )
    for _query, symptom, _check_label in profiles:
        wait_for_node(symptom, role="panel")
    for query, symptom, check_label in profiles:
        click("Search routes, settings, and actions")
        search = wait_for_node("Global search", role="text")
        search.element.send_keys(query)
        wait_for_node_containing(symptom, role="list item").click()
        selected = wait_for_node(symptom, role="panel")
        assert "Selected symptom" in selected.description
        wait_for_node_containing(check_label, role="label")
