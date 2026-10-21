"""AT-SPI helpers for the real Fedora KDE desktop session."""

from __future__ import annotations

import os
import hashlib
import json
import re
import subprocess
from collections.abc import Iterator

import pytest

from pathlib import Path

# Fail before importing desktop automation: this suite must never drive the host.
marker = Path("/etc/loofi-e2e-guest")
if not marker.is_file() or marker.read_text().strip() != "loofi-fedora-tweaks-e2e":
    raise pytest.UsageError("Native GUI E2E tests require the dedicated Loofi guest VM.")
if subprocess.run(["systemd-detect-virt", "--vm"], capture_output=True, text=True, check=False).stdout.strip() not in {"qemu", "kvm"}:
    raise pytest.UsageError("Native GUI E2E tests require QEMU virtualization.")

from helpers import application_environment, record_application_runtime, wait_for_node, use_driver
from selenium import webdriver
from selenium.webdriver.common.options import ArgOptions
from selenium.webdriver.remote.remote_connection import RemoteConnection
import time
import urllib.request


@pytest.fixture(scope="session")
def app_process_registry() -> list[subprocess.Popen[str]]:
    return []


@pytest.fixture(scope="session")
def loofi_app(app_process_registry: list[subprocess.Popen[str]]) -> Iterator[subprocess.Popen[str]]:
    log_dir = "/var/tmp/loofi-e2e"
    os.makedirs(log_dir, mode=0o700, exist_ok=True)
    log_handle = open(os.path.join(log_dir, "application.log"), "a", encoding="utf-8")
    app_env = os.environ.copy()
    app_env.pop("LOOFI_E2E_POLKIT_PASSWORD", None)
    app_env.pop("LOOFI_E2E_CREDENTIALS_PATH", None)
    server_env = app_env.copy()
    server_env.pop("LD_LIBRARY_PATH", None)
    server_env.pop("LD_PRELOAD", None)
    app_env = application_environment()
    # The upstream Wayland helper logs synthesized characters at qDebug level.
    # Its child environment must never record Polkit credential key events.
    server_env["QT_LOGGING_RULES"] = "*.debug=false"
    if server_env.get("XDG_SESSION_TYPE") == "wayland":
        # The pinned KDE driver uses its built guest inputsynth for Wayland;
        # falling back to AT-SPI X11 events would silently lose native input.
        if not server_env.get("KWIN_PID") or not server_env.get("WAYLAND_DISPLAY"):
            raise RuntimeError("Wayland automation requires the actual guest KWin PID and display.")
    else:
        server_env.pop("KWIN_PID", None)  # X11 uses AT-SPI native input.
    server = None
    driver = None
    process = None
    try:
        server = subprocess.Popen(
            ["/usr/bin/python3", "-m", "flask", "--app", "/var/tmp/loofi-e2e/selenium-webdriver-at-spi.py",
             "run", "--host", "127.0.0.1", "--port", "4723"],
            stdout=log_handle, stderr=subprocess.STDOUT, env=server_env,
        )
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen("http://127.0.0.1:4723/status", timeout=2):
                    break
            except OSError:
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("The guest Selenium AT-SPI server did not start.")
                time.sleep(0.5)
        options = ArgOptions()
        options.set_capability("appium:app", "Root")
        options.set_capability("timeouts", {"implicit": 200})
        RemoteConnection.set_timeout(30)
        driver = webdriver.Remote("http://127.0.0.1:4723", options=options)
        use_driver(driver)
        process = subprocess.Popen(
            ["/usr/bin/loofi-fedora-tweaks"],
            stdin=subprocess.DEVNULL, stdout=log_handle, stderr=subprocess.STDOUT,
            text=True, close_fds=True, env=app_env,
        )
        app_process_registry.append(process)
        wait_for_node("Loofi Fedora Tweaks", role="frame", timeout=90)
        record_application_runtime(process)
        try:
            wait_for_node("Open Loofi", timeout=3).click()
        except AssertionError:
            pass
        yield process
    finally:
        try:
            if driver is not None:
                driver.quit()
        finally:
            use_driver(None)
            for child in (*app_process_registry, server):
                if child is not None and child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=10)
            log_handle.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.failed:
        print(str(report.longrepr), flush=True)
        registry = item.funcargs.get("app_process_registry", [])
        print("Suite-owned app process status: " + json.dumps([
            {"pid": process.pid, "exit_code": process.poll()} for process in registry
        ]), flush=True)
        from helpers import _driver
        if _driver is not None:
            try:
                stem = re.sub(r"[^A-Za-z0-9_-]", "_", item.name)[:120]
                name = stem + "-" + hashlib.sha256(item.nodeid.encode()).hexdigest()[:12] + "-accessibility.xml"
                work = Path("/var/tmp/loofi-e2e")
                (work / name).write_text(_driver.page_source)
                manifest = work / "failure-artifacts.json"
                artifacts = json.loads(manifest.read_text()) if manifest.exists() else []
                manifest.write_text(json.dumps(sorted(set(artifacts + [name]))))
            except Exception:
                pass
