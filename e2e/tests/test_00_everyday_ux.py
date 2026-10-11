"""Everyday guide and native handoff qualification before longer settings flows."""
import os
import subprocess
import threading

from helpers import observe_refresh, wait_for_node, wait_for_node_containing, wait_until
from test_fedora_kde_workflows import dnf_parallel_downloads, dolphin_full_path_enabled


def test_guide_progress_survives_restart_and_resumes_without_mutation(loofi_app, app_process_registry) -> None:
    """Real guide interaction persists skips and opens the next existing route."""
    import json
    from pathlib import Path
    from helpers import activate_control, current_app_process, open_search_result, press_key, restart_app

    before_dnf = dnf_parallel_downloads()
    before_dolphin = dolphin_full_path_enabled()
    open_search_result("Make Fedora yours", "Make Fedora yours")
    activate_control("Show guide steps and progress")
    activate_control("Skip step")
    progress_path = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "loofi-fedora-tweaks/guides.json"
    wait_until(lambda: json.loads(progress_path.read_text()).get("steps", {}).get(
        "make-fedora-yours:find-settings", {}).get("state") == "skipped",
        timeout=10, message="Guide skip did not reach persisted readback")
    progress = json.loads(progress_path.read_text())
    assert progress["active_guide"] == "make-fedora-yours"
    assert progress["steps"]["make-fedora-yours:find-settings"]["state"] == "skipped"
    assert "evidence_id" not in progress["steps"]["make-fedora-yours:find-settings"] or not progress["steps"]["make-fedora-yours:find-settings"]["evidence_id"]

    running = current_app_process(app_process_registry)
    restart_app(running, app_process_registry)
    # The shell restores the saved selection once Overview is constructed.
    wait_for_node("Overview", role="table cell").click()
    wait_for_node("Active Fedora guide: Make Fedora yours", timeout=30).click()
    press_key("home")
    press_key("enter")
    wait_for_node("Search tweaks", role="text", timeout=30)
    assert json.loads(progress_path.read_text())["steps"]["make-fedora-yours:find-settings"]["state"] == "skipped"
    assert dnf_parallel_downloads() == before_dnf
    assert dolphin_full_path_enabled() == before_dolphin


def _discover_pids() -> set[str]:
    result = subprocess.run(["pgrep", "-x", "plasma-discover"], capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode in {0, 1}, result.stderr
    return set(result.stdout.split())


def test_catalog_miss_opens_real_discover_and_returns_to_installed_apps(loofi_app) -> None:
    """A handoff starts the native store; it never claims package completion."""
    import pyatspi
    from helpers import activate_control, open_search_result, press_key, return_to_loofi_window
    before_packages = subprocess.run(["rpm", "-qa"], capture_output=True, text=True, check=True, timeout=30).stdout.splitlines()
    assert not _discover_pids(), "Discover must not be running in the clean guest before the handoff"
    open_search_result("Install Apps", "Apps")
    search = wait_for_node("Search applications", role="text", timeout=30)
    search.element.send_keys("loofi-e2e-no-catalog-match")
    activate_control("Open Discover or GNOME Software")
    wait_until(lambda: bool(_discover_pids()), timeout=30, message="native handoff did not start Discover")
    # Process readback is independent of Loofi's launch status. Close only the
    # process that this clean guest interaction started, then refresh inventory.
    for pid in _discover_pids():
        os.kill(int(pid), 15)
    wait_until(lambda: not _discover_pids(), timeout=30, message="Discover did not close")
    return_to_loofi_window()
    wait_for_node("Catalog", role="combo box").element.click()
    press_key("home")
    press_key("down")
    press_key("enter")
    wait_for_node("Installed", role="combo box", timeout=30)
    wait_for_node("Installation inventory checked.", timeout=90)
    refresh = wait_for_node("Refresh installed applications", timeout=90, enabled=True)
    target = pyatspi.Registry.getDesktop(0)
    for index in refresh._source().get("path").split():
        target = target[int(index)]
    assert target.name == "Refresh installed applications"
    started, completed, stop = threading.Event(), threading.Event(), threading.Event()
    errors = []

    def read_refresh_enabled():
        target.clear_cache_single()
        return target.getState().contains(pyatspi.STATE_ENABLED)

    def observe_refresh_cycle():
        try:
            observe_refresh(read_refresh_enabled, started, completed, stop, timeout=90)
        except Exception as exc:
            errors.append(str(exc))

    observer = threading.Thread(target=observe_refresh_cycle, daemon=True)
    observer.start()
    try:
        refresh.element.click()
        assert started.wait(10), "Refresh did not start an inventory check"
        assert completed.wait(90), f"Refresh did not complete an inventory check: {errors}"
    finally:
        stop.set()
        observer.join(timeout=5)
    assert not observer.is_alive() and not errors
    wait_for_node("Installation inventory checked.", timeout=30)
    search.element.clear()
    search.element.send_keys("Discover")
    wait_for_node_containing("Discover", role="panel", timeout=30)
    after_packages = subprocess.run(["rpm", "-qa"], capture_output=True, text=True, check=True, timeout=30).stdout.splitlines()
    assert sorted(after_packages) == sorted(before_packages), "native discovery changed installed RPM packages"
