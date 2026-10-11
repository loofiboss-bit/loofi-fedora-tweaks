#!/usr/bin/env python3
"""Measure isolated, offscreen GUI fixtures; never execute host operations.

Fresh-process pairs compare Qt bootstrap with the real MainWindow, or compare
two revisions of the shell with --compare-ref. This measures process startup,
imports and page construction, excluding disk-cache-cold startup, system
collection and physical desktop latency.
Workflow counts include only input actions delivered to real widgets and checked
against their resulting state/signals. They stop before authorization/execution.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((percentile * len(ordered) + 0.999999) - 1)))
    return ordered[index]


def _summary(values: list[float]) -> dict[str, object]:
    return {
        "samples_ms": [round(value, 2) for value in values],
        "p50_ms": round(median(values), 2),
        "p95_ms": round(_percentile(values, 0.95), 2),
        "max_ms": round(max(values), 2),
    }


def _git_value(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip()


def _fixture(rows: int):
    from core.tasks.applications import ApplicationRecord

    return tuple(
        ApplicationRecord(
            id=f"fixture-{index:03d}",
            name=f"Fixture application {index:03d}",
            description="A bounded performance fixture for catalog filtering.",
            category="Utilities",
            source="flatpak",
            package_id=f"org.example.Fixture{index:03d}",
            keywords=("fixture", "search"),
        )
        for index in range(rows)
    )


def _apps_page(rows: int):
    from core.catalog_models import FedoraVariant
    from core.tasks.applications import ApplicationCatalog, ApplicationContext
    from ui.install_workflow import InstallWorkflowPage

    return InstallWorkflowPage(
        catalog=ApplicationCatalog(_fixture(rows)),
        context=ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"}), online=True),
    )


class _MemorySettings:
    """Only the optional intro is exercised; no user settings are loaded/saved."""

    def __init__(self):
        self.values = {"overview_intro_dismissed": False}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        return True


class _Actions:
    """Count an observed logical input action, with a required postcondition."""

    def __init__(self, app):
        self.app = app
        self.actions: list[str] = []

    def deliver(self, description, operation, observed):
        operation()
        self.app.processEvents()
        from PyQt6.QtTest import QTest

        deadline = perf_counter() + 2
        while not observed() and perf_counter() < deadline:
            QTest.qWait(1)
        if not observed():
            raise AssertionError(f"Input action did not reach its postcondition: {description}")
        self.actions.append(description)

    def result(self, scope):
        return {"input_actions": len(self.actions), "observed_actions": self.actions, "scope": scope}


@patch("ui.native_handoff_card.QProcess.startDetached", return_value=(True, 123))
@patch("services.system.system.SystemManager.get_platform_profile", side_effect=lambda: _platform_fixture())
def _central_workflows(app, _profile, detached):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QPushButton
    from core.tasks.tweaks import BY_ID, TweakState
    from services.desktop.native_handoff import NativeHandoffLaunch
    from services.software.installed_applications import InstalledApplication, InstalledInventory
    from ui.installed_applications import InstalledApplicationsCard
    from ui.tweak_profiles import ProfileSelectionDialog
    from ui.tweaks_page import TweaksPage

    tweaks = TweaksPage(_platform_fixture())
    tweaks.resize(1100, 800)
    tweaks.show()
    tweak = BY_ID["kde-single-click"]
    before, after = tweak.choices[:2]
    tweaks.set_states((TweakState(tweak, "ready", value=before[0], choices=tweak.choices),))
    app.processEvents()
    changes, restores = [], []
    tweaks.changeRequested.connect(lambda *args: changes.append(args))
    tweaks.restoreRequested.connect(lambda *args: restores.append(args))
    recorder = _Actions(app)
    try:
        recorder.deliver("Search for Single-click", lambda: QTest.keyClicks(tweaks.search_input, "Single-click"),
                         lambda: not tweaks._rows[tweak.id][0].isHidden())
        control = tweaks._rows[tweak.id][1]
        index = control.findData(after[0])
        target = control._buttons[index] if control._buttons else control._editor
        recorder.deliver("Select the alternate click behavior", lambda: QTest.mouseClick(target, Qt.MouseButton.LeftButton),
                         lambda: changes == [(tweak.id, after[0])])
        # Inject independent verified-result fixture. No change was executed by this harness.
        tweaks.set_states((TweakState(tweak, "ready", value=after[0], choices=tweak.choices,
                                      restore_run_id="fixture-verified-run", restore_value=before[0], restore_allowed=True),))
        app.processEvents()
        recorder.deliver("Request restoration of the verified previous value",
                         lambda: QTest.mouseClick(tweaks._restore_buttons[tweak.id], Qt.MouseButton.LeftButton),
                         lambda: restores == [(tweak.id, "fixture-verified-run")])
        change_restore = recorder.result("Search/change/restore request signals only; verified outcome is injected, no action review, write or verification")
    finally:
        tweaks.close()
        tweaks.deleteLater()
        app.processEvents()

    dialog = ProfileSelectionDialog("Fixture profile review", "One independently reviewable setting",
                                    [(tweak.id, tweak.title, True)])
    dialog.show()
    app.processEvents()
    recorder = _Actions(app)
    buttons = dialog.findChild(QDialogButtonBox)
    try:
        recorder.deliver("Accept the selected setting in profile review",
                         lambda: QTest.mouseClick(buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton),
                         lambda: dialog.result() == QDialog.DialogCode.Accepted and dialog.selected_ids() == (tweak.id,))
        profile_apply = recorder.result("Pre-opened profile review acceptance only; excludes library navigation, planning and execution")
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    flatpak = InstalledApplication("Fixture Flatpak", "org.example.Fixture", "flatpak", "user",
                                   "app/org.example.Fixture/x86_64/stable")
    rpm = InstalledApplication("Fixture RPM", "fixture-rpm", "fedora", "system", "fixture-rpm")
    inventory = InstalledInventory((flatpak, rpm))
    service = Mock(snapshot=Mock(return_value=inventory))
    installed = InstalledApplicationsCard(service=service)
    installed.software_handoff._service = Mock(prepare_launch=Mock(return_value=NativeHandoffLaunch("fixture-store", ())))
    installed.apply_inventory(inventory)
    installed.resize(1100, 800)
    installed.show()
    app.processEvents()
    removals = []
    installed.actionReviewRequested.connect(lambda *args: removals.append(args))
    try:
        flatpak_button = next(button for button in installed._rows[0].findChildren(QPushButton)
                              if button.text() == "Review removal")
        recorder = _Actions(app)
        recorder.deliver("Request removal review for the exact user Flatpak",
                         lambda: QTest.mouseClick(flatpak_button, Qt.MouseButton.LeftButton),
                         lambda: removals == [("remove-installed-flatpak", {"ref": flatpak.ref, "installation": "user"})])
        removal = recorder.result("Preloaded exact Flatpak row to removal-review signal; no removal or app-data changes")
        rpm_button = next(button for button in installed._rows[1].findChildren(QPushButton)
                          if button.text() == "Open software manager")
        recorder = _Actions(app)
        recorder.deliver("Open the RPM software-manager handoff",
                         lambda: QTest.mouseClick(rpm_button, Qt.MouseButton.LeftButton),
                         lambda: detached.call_count == 1 and installed._software_manager_app == rpm)
        recorder.deliver("Refresh the installed inventory after returning",
                         lambda: QTest.mouseClick(installed.refresh_button, Qt.MouseButton.LeftButton),
                         lambda: service.snapshot.call_count == 1 and not installed._adapter.busy)
        handoff = recorder.result("RPM handoff input and return refresh with mocked native launch and synthetic inventory; excludes external tool interaction")
    finally:
        installed.cleanup()
        installed.close()
        installed.deleteLater()
        app.processEvents()
    return {"tweak_search_change_restore": change_restore, "profile_review_acceptance": profile_apply,
            "flatpak_removal_review": removal, "rpm_handoff_return_refresh": handoff}


@patch("subprocess.Popen", side_effect=AssertionError("GUI fixtures must not start host processes"))
@patch("subprocess.run", side_effect=AssertionError("GUI fixtures must not run host commands"))
@patch("utils.settings.SettingsManager.instance")
def _measure_gui(rows: int, samples: int, _settings, _host_commands, _host_processes) -> dict[str, object]:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QStackedWidget
    from ui.overview_page import OverviewPage

    _settings.return_value = _MemorySettings()
    app = QApplication.instance() or QApplication([])
    started = perf_counter()
    page = _apps_page(rows)
    app.processEvents()
    construction_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    overview = OverviewPage()
    app.processEvents()
    overview_ms = (perf_counter() - started) * 1000
    stack = QStackedWidget()
    stack.addWidget(overview)
    stack.addWidget(page)
    stack.resize(1100, 800)
    stack.show()
    app.processEvents()
    navigation_ms: list[float] = []
    first_open_ms: dict[str, float] = {}
    search_samples_ms: list[float] = []
    try:
        # Only page switching/layout is measured; no window adapters or collectors.
        for index in range(max(2, samples)):
            target = page if index % 2 == 0 else overview
            started = perf_counter()
            stack.setCurrentWidget(target)
            app.processEvents()
            elapsed = (perf_counter() - started) * 1000
            navigation_ms.append(elapsed)
            name = "apps" if target is page else "overview"
            first_open_ms.setdefault(name, round(elapsed, 2))
        stack.setCurrentWidget(page)
        for index in range(samples):
            query = f"fixture application {index % 10}"
            search = page.search_input
            search.setText(query[:-1])
            app.processEvents()
            started = perf_counter()
            QTest.keyClick(search, query[-1])
            app.processEvents()
            search_samples_ms.append((perf_counter() - started) * 1000)

        # A full text entry counts as one logical action, not as a single key.
        selected = []
        page.bundleReviewRequested.connect(selected.append)
        page.search_input.clear()
        recorder = _Actions(app)
        query = "Fixture application 000"
        recorder.deliver("Enter an exact fixture application search",
                         lambda: QTest.keyClicks(page.search_input, query),
                         lambda: page.search_input.text() == query and not page._rows["fixture-000"][2].isHidden())
        check = page._row_checks["fixture-000"]
        recorder.deliver("Select the matching application checkbox",
                         lambda: QTest.mouseClick(check, Qt.MouseButton.LeftButton),
                         lambda: page.selected_application_ids() == ("fixture-000",))
        recorder.deliver("Request an install review",
                         lambda: QTest.mouseClick(page.review_button, Qt.MouseButton.LeftButton),
                         lambda: len(selected) == 1 and selected[0].count == 1)
        install_workflow = recorder.result("Apps catalog input to review-request signal; no dialog, authorization or installation")

        # View selection is a real keyboard event; refresh is deliberately omitted.
        page.view_filter.setFocus()
        recorder = _Actions(app)
        recorder.deliver("Choose Installed with the keyboard",
                         lambda: QTest.keyClick(page.view_filter, Qt.Key.Key_Down),
                         lambda: page.view_filter.currentData() == "installed" and not page.installed_card.isHidden())
        recorder.deliver("Return to Catalog with the keyboard",
                         lambda: QTest.keyClick(page.view_filter, Qt.Key.Key_Up),
                         lambda: page.view_filter.currentData() == "catalog" and page.installed_card.isHidden())
        view_workflow = recorder.result("Local view navigation only; installed inventory is not refreshed")

        stack.setCurrentWidget(overview)
        app.processEvents()
        recorder = _Actions(app)
        recorder.deliver("Dismiss the optional introduction",
                         lambda: QTest.mouseClick(overview.dismiss_intro_button, Qt.MouseButton.LeftButton),
                         lambda: overview.intro_card.isHidden())
        recorder.deliver("Reopen the optional introduction",
                         lambda: QTest.mouseClick(overview.show_intro_button, Qt.MouseButton.LeftButton),
                         lambda: not overview.intro_card.isHidden())
        intro_workflow = recorder.result("Overview introduction visibility with in-memory settings; restart is not measured")
        central_workflows = _central_workflows(app)
        return {
            "fixture": {"catalog_rows": rows, "search_samples": samples, "navigation_samples": max(2, samples)},
            "measured_ms": {
                "apps_catalog_construction": round(construction_ms, 2),
                "overview_construction": round(overview_ms, 2),
                "first_existing_page_open": first_open_ms,
                "existing_page_navigation": _summary(navigation_ms),
                "last_key_to_filtered_list_p50": round(median(search_samples_ms), 2),
                "last_key_to_filtered_list_p95": round(_percentile(search_samples_ms, 0.95), 2),
                "last_key_to_filtered_list_max": round(max(search_samples_ms), 2),
            },
            "workflows": {"apps_search_select_review": install_workflow, "apps_view_roundtrip": view_workflow,
                          "overview_intro_roundtrip": intro_workflow, **central_workflows},
        }
    finally:
        overview.cleanup()
        page.cleanup()
        stack.close()
        stack.deleteLater()
        app.processEvents()


def measure(rows: int, samples: int) -> dict[str, object]:
    """Retain the original single-catalog API, adding navigation and observed inputs."""
    from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    report = _measure_gui(rows, samples)
    return {
        "revision": _git_value("rev-parse", "HEAD"),
        "working_tree_dirty": bool(_git_value("status", "--porcelain")),
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "pyqt": PYQT_VERSION_STR, "qt": QT_VERSION_STR, "qt_platform": os.environ.get("QT_QPA_PLATFORM", "")},
        **report,
    }


def _platform_fixture():
    from core.fedora_release_policy import FEDORA_RELEASE_POLICY
    from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType

    return PlatformProfile("fedora", int(FEDORA_RELEASE_POLICY.stable_release), "kde", "KDE Plasma",
                           "x86_64", DesktopEnvironment.KDE, SessionType.X11, DeploymentBackend.DNF5, False,
                           package_manager_command="dnf5")


@patch("ui.main_window_utility.MainWindowUtilityMixin._start_tweak_snapshot", return_value=False)
@patch("ui.dashboard_controller.DashboardController")
@patch("core.plugins.compat.CompatibilityDetector.check_plugin_compat")
@patch("services.system.system.SystemManager.get_platform_profile", side_effect=_platform_fixture)
def _shell_child(import_started, _profile, compatible, controller, _snapshot):
    """Construct real shell/routes; replace platform probes and async collector."""
    from PyQt6.QtWidgets import QApplication
    from core.plugins.metadata import CompatStatus
    from ui.main_window import MainWindow

    compatible.return_value = CompatStatus(compatible=True)
    controller.return_value.latest_snapshot = None
    app = QApplication.instance() or QApplication([])
    started = perf_counter()
    window = MainWindow()
    window.show()
    app.processEvents()
    shell_ms = (perf_counter() - started) * 1000
    import_to_ready_ms = (perf_counter() - import_started) * 1000
    started = perf_counter()
    if not window.switch_to_route("tune"):
        raise AssertionError("Tweaks route was unavailable in the KDE fixture")
    app.processEvents()
    first_page_ms = (perf_counter() - started) * 1000
    route_hops = []
    for _ in range(8):
        for route in ("overview", "tune"):
            started = perf_counter()
            if not window.switch_to_route(route):
                raise AssertionError(f"Fixture route unavailable: {route}")
            app.processEvents()
            route_hops.append((perf_counter() - started) * 1000)
    window.close()
    app.processEvents()
    return {"system_collection": "disabled: mocked dashboard and tweak snapshot",
            "import_qt_shell_first_event_pump_ms": round(import_to_ready_ms, 2),
            "shell_constructor_and_first_event_pump_ms": round(shell_ms, 2),
            "first_tweaks_route_ms": round(first_page_ms, 2), "warm_route_hops": _summary(route_hops)}


@patch("subprocess.Popen", side_effect=AssertionError("Startup fixture must not start host processes"))
@patch("subprocess.run", side_effect=AssertionError("Startup fixture must not run host commands"))
def _startup_child(target: str, rows: int, _host_commands, _host_processes) -> dict[str, object]:
    import_started = perf_counter()
    from PyQt6.QtWidgets import QApplication

    app = QApplication([])
    if target == "shell":
        return {"ready": True, "target": target, "measurements": _shell_child(import_started)}
    page = _apps_page(rows) if target == "apps" else None
    if page is not None:
        page.show()
    app.processEvents()
    if page is not None:
        page.cleanup()
        page.close()
    return {"ready": True, "target": target, "rows": rows}


def _isolated_environment(directory: str) -> dict[str, str]:
    env = dict(os.environ)
    for kind in ("CONFIG", "DATA", "CACHE", "STATE", "RUNTIME"):
        root = Path(directory) / kind.lower()
        root.mkdir(mode=0o700)
        env[f"XDG_{kind}_HOME" if kind != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(root)
    # A missing custom-XDG file triggers legacy migration from the real home.
    # Seed settings before any product import so both revisions start from the
    # same navigation/theme state, rather than the maintainer's saved settings.
    config = Path(env["XDG_CONFIG_HOME"]) / "loofi-fedora-tweaks"
    config.mkdir(mode=0o700)
    settings = {
        "theme": "dark", "follow_system_theme": False, "navigation_mode": "standard",
        "start_minimized": False, "restore_last_tab": False, "last_route_id": "overview",
        "overview_intro_dismissed": False, "favorite_routes": [], "favorite_tweaks": [],
        "hidden_routes": [], "window_geometry": {}, "check_updates_on_start": False,
    }
    (config / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    env.update(QT_QPA_PLATFORM="offscreen", LOOFI_IPC_MODE="disabled", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(ROOT / "loofi-fedora-tweaks"))
    return env


def _run_startup_child(target: str, rows: int, source: Path | None = None):
    with TemporaryDirectory(prefix="loofi-ux-startup-") as directory:
        env = _isolated_environment(directory)
        if source is not None:
            env["PYTHONPATH"] = str(source)
        started = perf_counter()
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--startup-child", target, "--rows", str(rows)],
            cwd=ROOT, env=env, capture_output=True, text=True, check=True, timeout=60,
        )
        elapsed = (perf_counter() - started) * 1000
        payload = json.loads(result.stdout)
        if payload.get("ready") is not True:
            raise RuntimeError("Startup child did not report ready")
        return elapsed, payload


def measure_startup_pairs(rows: int, pairs: int, compare_ref: str | None = None) -> dict[str, object]:
    control_name = "baseline_shell" if compare_ref else "qt_bootstrap"
    timings: dict[str, list[float]] = {control_name: [], "current_shell": []}
    observations: dict[str, list[object]] = {control_name: [], "current_shell": []}
    order: list[list[str]] = []
    with TemporaryDirectory(prefix="loofi-ux-reference-") as reference_directory:
        # Both revisions use fresh source trees without .pyc files. Disabling
        # bytecode writes alone would still read the checkout's existing cache.
        current_source = Path(reference_directory) / "current" / "loofi-fedora-tweaks"
        shutil.copytree(ROOT / "loofi-fedora-tweaks", current_source,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        source_digest = hashlib.sha256()
        for path in sorted(current_source.rglob("*")):
            if path.is_file():
                source_digest.update(str(path.relative_to(current_source)).encode() + b"\0" + path.read_bytes())
        source = None
        revision = None
        if compare_ref:
            revision = _git_value("rev-parse", "--verify", f"{compare_ref}^{{commit}}")
            archive = subprocess.run(["git", "archive", revision, "loofi-fedora-tweaks"], cwd=ROOT,
                                     check=True, capture_output=True, timeout=30)
            with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as reference:
                reference.extractall(reference_directory, filter="data")
            source = Path(reference_directory) / "loofi-fedora-tweaks"
        for index in range(pairs):
            targets = [control_name, "current_shell"] if index % 2 == 0 else ["current_shell", control_name]
            order.append(targets)
            for target in targets:
                is_control = target == control_name
                child = "qt" if is_control and compare_ref is None else "shell"
                elapsed, payload = _run_startup_child(child, rows, source if is_control else current_source)
                timings[target].append(elapsed)
                observations[target].append(payload.get("measurements", {}))
    comparison = timings
    if compare_ref:
        comparison = {name: [entry["import_qt_shell_first_event_pump_ms"] for entry in entries]
                      for name, entries in observations.items()}
    differences = [candidate - control for candidate, control in zip(comparison["current_shell"], comparison[control_name])]
    percent_changes = [(candidate / control - 1) * 100
                       for candidate, control in zip(comparison["current_shell"], comparison[control_name])]
    return {
        "scope": "Fresh Python process through shell ready, navigation and shutdown; OS disk caches are not flushed. Platform and collector are mocked.",
        "pairs": pairs, "alternating_order": order, "baseline_revision": revision,
        "current_source_tree_sha256": source_digest.hexdigest(),
        "bytecode_cache_policy": "Both source trees exclude __pycache__ and .pyc; child bytecode writes disabled.",
        "settings_policy": "Explicit private-XDG settings fixture before app imports; legacy home settings are not copied.",
        "comparison_metric": "child import/Qt/shell to first event pump" if compare_ref else "process lifecycle wall time",
        **{name: _summary(values) for name, values in timings.items()},
        "child_observations": observations,
        "paired_current_minus_control_ms": _summary(differences),
        "paired_change_percent": [round(value, 2) for value in percent_changes],
        "paired_change_percent_p50": round(median(percent_changes), 2),
    }


def _rpm_metadata(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        while chunk := artifact.read(1024 * 1024):
            digest.update(chunk)
    return {"path": str(path.resolve()), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=500, help="Primary synthetic catalog size and startup fixture size.")
    parser.add_argument("--catalog-sizes", default="50,200,500", help="Comma-separated additional catalog sizes.")
    parser.add_argument("--samples", type=int, default=30, help="Last-key latency and page-switch samples per size.")
    parser.add_argument("--startup-pairs", type=int, default=5, help="Alternating fresh-process Qt/Apps pairs; zero skips them.")
    parser.add_argument("--compare-ref", help="Compare real shell startup/navigation with this Git revision in alternating process pairs.")
    parser.add_argument("--rpm", type=Path, help="Record the exact candidate RPM hash; does not install it.")
    parser.add_argument("--startup-child", choices=("qt", "apps", "shell"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        sizes = sorted({args.rows, *(int(value) for value in args.catalog_sizes.split(","))})
    except ValueError:
        parser.error("--catalog-sizes must contain comma-separated integers")
    if min(sizes) < 1 or args.samples < 1 or args.startup_pairs < 0:
        parser.error("catalog sizes and --samples must be positive, and --startup-pairs nonnegative")
    if args.startup_child:
        with TemporaryDirectory(prefix="loofi-ux-child-") as directory:
            isolated = _isolated_environment(directory)
            os.environ.update({key: value for key, value in isolated.items() if key.startswith("XDG_") or key in
                               {"QT_QPA_PLATFORM", "LOOFI_IPC_MODE", "PYTHONDONTWRITEBYTECODE"}})
            print(json.dumps(_startup_child(args.startup_child, args.rows)))
        return 0
    startup = measure_startup_pairs(args.rows, args.startup_pairs, args.compare_ref) if args.startup_pairs else {"status": "not requested"}
    with TemporaryDirectory(prefix="loofi-ux-gui-") as directory:
        isolated = _isolated_environment(directory)
        # Isolate before importing app modules whose state paths are module constants.
        os.environ.update({key: value for key, value in isolated.items() if key.startswith("XDG_") or key in
                           {"QT_QPA_PLATFORM", "LOOFI_IPC_MODE", "PYTHONDONTWRITEBYTECODE"}})
        report = measure(args.rows, args.samples)
        report["additional_catalogs"] = [_measure_gui(size, args.samples) for size in sizes if size != args.rows]
        report["process_startup"] = startup
        if args.rpm:
            report["rpm_artifact"] = _rpm_metadata(args.rpm)
        report["limits"] = ["Synthetic catalog; no installed-app inventory or system collection.",
                            "Offscreen MainWindow uses a Fedora/KDE fixture and mocked collector; native handoffs are not measured.",
                            "Workflow counts stop at observed navigation/review signals, excluding changes, restore and Polkit.",
                            "Fresh processes are not proof of filesystem-cache-cold startup; comparison requires --compare-ref."]
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
