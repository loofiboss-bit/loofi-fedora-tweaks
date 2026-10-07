"""Render the real control-center shell with isolated, deterministic fixtures.

No host commands, hardware sampling, or maintenance scans are performed.
Each process captures all maintained primary/tool views in three themes/sizes.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
from contextlib import ExitStack

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "loofi-fedora-tweaks"))


def fixture_snapshot():
    from services.system.dashboard import DashboardSnapshot, MetricReading
    stamp = 1791300000.0
    readings = (
        MetricReading("cpu.usage", "cpu", "CPU", 24.5, "%", "ready", "/proc/stat", stamp),
        MetricReading("memory.usage", "memory", "Memory", 41.0, "%", "ready", "/proc/meminfo", stamp, detail="6.6 GiB / 16.0 GiB"),
        MetricReading("gpu:intel", "gpu", "Intel graphics", None, "%", "unavailable", "/sys/class/drm", None, reason="This driver has no supported unprivileged load counter"),
        MetricReading("storage:system", "storage", "System and home", 38.0, "%", "ready", "statvfs", stamp, detail="190.0 GiB used / 500.0 GiB total"),
        MetricReading("network.receive", "network", "Network receive", 524288.0, "B/s", "ready", "/proc/net/dev", stamp),
        MetricReading("network.send", "network", "Network send", 32768.0, "B/s", "ready", "/proc/net/dev", stamp),
        MetricReading("disk.read", "disk", "Disk read", 8388608.0, "B/s", "ready", "/proc/diskstats", stamp),
        MetricReading("disk.write", "disk", "Disk write", 1048576.0, "B/s", "ready", "/proc/diskstats", stamp),
        MetricReading("temperature:cpu", "temperature", "CPU package", 52.0, "°C", "ready", "/sys/class/hwmon", stamp, high=85.0, critical=100.0),
        MetricReading("battery:example", "battery", "Battery", 78.0, "%", "ready", "/sys/class/power_supply", stamp, detail="Discharging"),
        MetricReading("battery:health", "battery", "Battery health", 93.0, "%", "ready", "/sys/class/power_supply", stamp),
    )
    maintenance = {
        "updates": {"status": "recorded", "detail": "System, Flatpak, and firmware observations", "sampled_at": stamp,
                    "sources": ({"source": "system", "status": "available", "count": 3, "sampled_at": stamp, "stale": False},)},
        "health": {"status": "partial", "detail": "A saved check needs review", "sampled_at": stamp},
        "activity": {"status": "complete", "detail": "A desktop setting was independently verified", "sampled_at": stamp, "verified": True},
    }
    return DashboardSnapshot(readings, {"hostname": "Example Fedora computer", "os": "Fedora Linux 44", "desktop": "KDE Plasma",
                                        "deployment": "DNF5", "cpu": "Example 8-core processor", "kernel": "Example kernel"},
                             stamp, maintenance, (12.0, 30.0, 18.0, 40.0))


def capture(out: Path, scale: str, large_text: bool, installed_view: bool = False):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_SCALE_FACTOR"] = scale
    fixture_root = Path(tempfile.mkdtemp(prefix="loofi-control-center-render-"))
    isolated_env = {f"XDG_{name}_HOME": str(fixture_root / name.lower()) for name in ("CONFIG", "DATA", "CACHE", "STATE")}
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication, QAbstractButton, QComboBox, QLabel, QScrollArea, QStyle, QStyleOptionComboBox, QTableWidget
    from ui.design import semantic_qcolor
    from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType
    from core.navigation.routes import all_shell_routes
    profile = PlatformProfile(os_id="fedora", fedora_version=44, variant_id="kde", variant_name="Fedora KDE",
                              architecture="x86_64", desktop=DesktopEnvironment.KDE, session_type=SessionType.WAYLAND,
                              deployment_backend=DeploymentBackend.DNF5, is_atomic=False, reboot_pending=False, package_manager_command="dnf5")
    with ExitStack() as scope:
        scope.enter_context(patch.dict(os.environ, isolated_env))
        scope.enter_context(patch("pathlib.Path.home", return_value=fixture_root))
        scope.enter_context(patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")))
        scope.enter_context(patch("subprocess.check_output", return_value=b""))
        scope.enter_context(patch("subprocess.Popen", side_effect=AssertionError("Unexpected host process during rendering")))
        scope.enter_context(patch("PyQt6.QtCore.QProcess.start", side_effect=AssertionError("Unexpected Qt host process during rendering")))
        from utils.zram import ZramConfig
        from services.security.secureboot import SecureBootStatus
        scope.enter_context(patch("utils.kernel.KernelManager.get_current_params", return_value=["quiet", "rhgb"]))
        scope.enter_context(patch("utils.zram.ZramManager.get_current_config", return_value=ZramConfig(True, 8192, 50, "zstd", 16384)))
        scope.enter_context(patch("utils.zram.ZramManager.get_current_usage", return_value=(1024, 8192)))
        scope.enter_context(patch("services.security.SecureBootManager.get_status", return_value=SecureBootStatus(True, False, False, "Example status")))
        scope.enter_context(patch("services.security.SecureBootManager.has_keys", return_value=False))
        scope.enter_context(patch("services.system.ProcessManager.get_all_processes", return_value=[]))
        scope.enter_context(patch("services.network.NetworkMonitor.get_all_interfaces", return_value=[]))
        scope.enter_context(patch("services.network.NetworkMonitor.get_active_connections", return_value=[]))
        scope.enter_context(patch("utils.storage.StorageManager.list_disks", return_value=[]))
        scope.enter_context(patch("utils.storage.StorageManager.list_mounts", return_value=[]))
        for fact, value in {
            "get_hostname": "Example Fedora computer", "get_kernel_version": "Example kernel",
            "get_fedora_release": "Fedora Linux 44", "get_cpu_model": "Example 8-core processor",
            "get_ram_usage": "6.6 GiB / 16.0 GiB", "get_disk_usage": "190.0 GiB / 500.0 GiB",
            "get_uptime": "2 hours", "get_battery_status": "78% (discharging)",
        }.items():
            scope.enter_context(patch("utils.system_info_utils." + fact, return_value=value))
        from ui.main_window import MainWindow
        from ui.design import ThemeManager
        from ui.overview_page import OverviewPage
        from ui.tweaks_page import TweaksPage
        from core.tasks.tweaks import TweakState, default_for, visible_tweaks
        from core.plugins.registry import PluginRegistry
        from utils.settings import SettingsManager
        PluginRegistry.reset()
        SettingsManager._reset_instance()
        sample = fixture_snapshot()
        from services.software.installed_applications import InstalledApplication, InstalledInventory
        installed = InstalledInventory(applications=(
            InstalledApplication("Example browser", "org.example.Browser", "flatpak", "user", "app/org.example.Browser/x86_64/stable", "1.0", "120 MB"),
            InstalledApplication("Example browser", "org.example.Browser", "flatpak", "system", "app/org.example.Browser/x86_64/stable", "1.0", "120 MB"),
            InstalledApplication("Example RPM", "example", "fedora", "system", "example", "1.0", "20 MB"),
        ))
        scope.enter_context(patch("services.software.installed_applications.InstalledApplicationService.snapshot", return_value=installed))
        scope.enter_context(patch("services.system.dashboard.DashboardService.collect", return_value=sample))
        scope.enter_context(patch("ui.main_window.MainWindow._check_first_run"))
        scope.enter_context(patch("ui.main_window.MainWindow._initialize_background_services"))
        scope.enter_context(patch("ui.main_window.MainWindow._start_tweak_snapshot", return_value=True))
        scope.enter_context(patch("ui.main_window.SystemManager.get_platform_profile", return_value=profile))
        app = QApplication.instance() or QApplication([])
        if large_text:
            font = QFont(app.font())
            font.setPointSizeF(max(10.0, font.pointSizeF()) * 2)
            app.setFont(font)
        ThemeManager().apply(app, "light")
        window = MainWindow()
        window.apply_advanced_tools(True)
        window.show()
        out.mkdir(parents=True, exist_ok=True)
        results = []
        candidates = ["overview", "tweaks", "apps", "updates", "health", "activity", "settings"]
        for shell_route in all_shell_routes():
            if shell_route.advanced:
                candidates.extend((shell_route.default_route_id, *shell_route.route_ids))
        routes = []
        seen = set()
        for requested in dict.fromkeys(candidates):
            assert window.switch_to_route(requested), requested
            for _ in range(4):
                app.processEvents()
            canonical = window._active_route_id
            if canonical not in seen:
                routes.append(requested)
                seen.add(canonical)
        try:
            for theme in ("light", "dark", "highcontrast"):
                window.load_theme(theme)
                for width, height in ((900, 650), (1280, 800), (1600, 900)):
                    window.resize(width, height)
                    for route in routes:
                        assert window.switch_to_route(route), route
                        for _ in range(8):
                            app.processEvents()
                        overview = window.findChild(OverviewPage)
                        if route == "overview" and overview is not None:
                            for step in range(16):
                                readings = tuple(replace(item, sampled_at=sample.collected_at + step * 2,
                                                         value=(item.value * (0.8 + step % 5 * 0.08) if item.group in {"cpu", "network", "disk"} and item.value is not None else item.value)) for item in sample.metrics)
                                overview.set_snapshot(replace(sample, metrics=readings, collected_at=sample.collected_at + step * 2))
                        if route == "tweaks":
                            page = window.findChild(TweaksPage)
                            page.set_states(tuple(TweakState(tweak, "ready", value=default_for(tweak) or tweak.choices[0][0], choices=tweak.choices)
                                                  for tweak in visible_tweaks(profile) if tweak.choices))
                        if route == "apps" and installed_view:
                            from ui.install_workflow import InstallWorkflowPage
                            install = window.findChild(InstallWorkflowPage)
                            install.installed_card.apply_inventory(installed)
                            install.view_filter.setCurrentIndex(install.view_filter.findData("installed"))
                        for area in window.findChildren(QScrollArea):
                            area.verticalScrollBar().setValue(0)
                        app.processEvents()
                        name = f"{route.replace(':', '-')}-{theme}-{width}x{height}"
                        window.grab().save(str(out / f"{name}.png"))
                        entry = window._sidebar_index.get(window._active_plugin_id)
                        lazy = entry.page_widget if entry is not None else None
                        assert not getattr(lazy, "load_error", ""), (route, getattr(lazy, "load_error", ""))
                        horizontal = []
                        wrapped_label_clipping = []
                        control_text_clipping = []
                        table_theme_issues = []
                        for label in window.findChildren(QLabel):
                            if label.isVisibleTo(window) and label.wordWrap():
                                required = label.heightForWidth(label.width())
                                if required > label.height() + 1:
                                    wrapped_label_clipping.append({"name": label.objectName(), "text": label.text(),
                                                                   "height": label.height(), "required": required})
                        for button in window.findChildren(QAbstractButton):
                            if not button.isVisibleTo(window) or not button.text().strip():
                                continue
                            icon_width = button.iconSize().width() + 8 if not button.icon().isNull() else 0
                            available = max(0, button.contentsRect().width() - icon_width - 18)
                            required = button.fontMetrics().horizontalAdvance(button.text())
                            if required > available + 1:
                                control_text_clipping.append({"type": "button", "name": button.objectName(), "text": button.text(), "available": available, "required": required})
                        for combo in window.findChildren(QComboBox):
                            if not combo.isVisibleTo(window) or not combo.currentText().strip():
                                continue
                            option = QStyleOptionComboBox()
                            combo.initStyleOption(option)
                            edit_rect = combo.style().subControlRect(
                                QStyle.ComplexControl.CC_ComboBox,
                                option,
                                QStyle.SubControl.SC_ComboBoxEditField,
                                combo,
                            )
                            required = combo.fontMetrics().horizontalAdvance(combo.currentText())
                            if required > max(0, edit_rect.width()) + 1:
                                control_text_clipping.append({"type": "combobox", "name": combo.objectName(), "text": combo.currentText(), "available": edit_rect.width(), "required": required})
                        for table in window.findChildren(QTableWidget):
                            if not table.isVisibleTo(window):
                                continue
                            for row_index in range(table.rowCount()):
                                for column in range(table.columnCount()):
                                    item = table.item(row_index, column)
                                    if item is None:
                                        continue
                                    rect = table.visualItemRect(item)
                                    required = table.fontMetrics().horizontalAdvance(item.text())
                                    if required > max(0, rect.width() - 12) + 1:
                                        table_theme_issues.append({"table": table.objectName(), "row": row_index, "column": column, "text": item.text(), "available": rect.width(), "required": required})
                                    semantic = item.data(Qt.ItemDataRole.UserRole + 90)
                                    if semantic and item.foreground().color() != semantic_qcolor(str(semantic)):
                                        table_theme_issues.append({"table": table.objectName(), "row": row_index, "column": column, "semantic_color": semantic, "issue": "stale after theme change"})
                        for area in window.findChildren(QScrollArea):
                            if area.isVisibleTo(window) and area.horizontalScrollBar().maximum() > 0:
                                horizontal.append(area.objectName())
                        for _ in range(20):
                            window.focusNextChild()
                            app.processEvents()
                            focused = app.focusWidget()
                            if focused is not None:
                                assert focused.isVisibleTo(window), (name, focused.objectName())
                        results.append({"capture": name, "scale": scale, "large_text": large_text,
                                        "actual_size": [window.width(), window.height()], "horizontal_ranges": horizontal, "focus_traversals": 20,
                                        "route": route, "canonical_route": window._active_route_id,
                                        "wrapped_label_clipping": wrapped_label_clipping,
                                        "control_text_clipping": control_text_clipping,
                                        "table_theme_issues": table_theme_issues})
            # Exercise longer translated descriptions without introducing fake UI data.
            window.switch_to_route("tweaks")
            page = window.findChild(TweaksPage)
            for row, _control in page._rows.values():
                row.description_label.setText("This longer translated description explains the scope and the effect of this setting in supported desktop applications. " * 2)
            window.resize(900, 650)
            app.processEvents()
            window.grab().save(str(out / "long-descriptions-highcontrast-900x650.png"))
        finally:
            window.cleanup()
            window.close()
            app.processEvents()
        (out / "rendering-checks.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps({"captures": len(results), "scale": scale, "large_text": large_text,
                          "routes": routes, "wrapped_label_clipping_views": sum(bool(result["wrapped_label_clipping"]) for result in results),
                          "control_text_clipping_views": sum(bool(result["control_text_clipping"]) for result in results),
                          "table_theme_issue_views": sum(bool(result["table_theme_issues"]) for result in results),
                          "horizontal_scroll_views": sum(bool(result["horizontal_ranges"]) for result in results)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", default="1")
    parser.add_argument("--large-text", action="store_true")
    parser.add_argument("--installed-view", action="store_true", help="Capture the Installed Apps view")
    arguments = parser.parse_args()
    capture(arguments.output, arguments.scale, arguments.large_text, arguments.installed_view)
