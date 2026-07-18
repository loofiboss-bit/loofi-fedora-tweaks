#!/usr/bin/env python3
"""Validate the v16 Phase 7 real-shell UI and accessibility matrix.

The automated run renders the real ``MainWindow`` for the complete
theme/mode/viewport/font-scale/locale product.  It keeps host state isolated,
rejects asynchronous commands, checks shell geometry and semantic contrast,
and retains compact contact sheets instead of hundreds of raw frames.

Live runs use the same checks through the Wayland or X11 Qt backend and record
the actual session, screen, accessibility, and compositor evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "loofi-fedora-tweaks"
IMAGE_ROOT = ROOT / "docs" / "images" / "v16" / "phase7"
REPORT_ROOT = ROOT / "docs" / "reports"

THEMES = ("system", "dark", "light", "highcontrast")
NAVIGATION_MODES = ("standard", "advanced")
VIEWPORTS = ((860, 720), (1280, 720), (1366, 768), (1920, 1080), (2560, 1440))
FONT_SCALES = (100, 125, 140, 150, 200)
LOCALE_FIXTURES = ("en", "en-long")

STANDARD_ROUTES = (
    "atlas_dashboard",
    "software:apps",
    "system_info",
    "network",
    "desktop",
    "settings",
)
ADVANCED_ROUTES = (
    "performance",
    "development",
    "profiles",
    "community",
    "ai-lab",
    "virtualization",
)

_LONG_ENGLISH_DESTINATIONS = (
    "Home and recommended next actions",
    "Software and operating system updates",
    "System and detailed hardware information",
    "Network, privacy, and security controls",
    "Desktop and workspace configuration",
    "Application settings and behavior",
    "Advanced specialist administration tools",
)
_LONG_ENGLISH_PAGE_TITLE = "System information and Fedora environment details"
_LONG_ENGLISH_PAGE_DESCRIPTION = (
    "Review operating system, hardware, and technical details without changing the system."
)


@dataclass(frozen=True)
class MatrixCase:
    """One real-shell validation or screenshot-catalog cell."""

    theme: str
    navigation_mode: str
    viewport: tuple[int, int]
    scale_percent: int
    locale_fixture: str
    route_id: str = "atlas_dashboard"

    @property
    def case_id(self) -> str:
        width, height = self.viewport
        return (
            f"{self.theme}__{self.navigation_mode}__{width}x{height}"
            f"__scale-{self.scale_percent:03d}__{self.locale_fixture}"
            f"__{self.route_id.replace(':', '-')}"
        )


def build_automated_matrix() -> tuple[MatrixCase, ...]:
    """Return the complete 4 x 2 x 5 x 5 x 2 automated contract."""
    return tuple(
        MatrixCase(theme, mode, viewport, scale, locale_fixture)
        for theme in THEMES
        for mode in NAVIGATION_MODES
        for viewport in VIEWPORTS
        for scale in FONT_SCALES
        for locale_fixture in LOCALE_FIXTURES
    )


def build_live_matrix() -> tuple[MatrixCase, ...]:
    """Return an orthogonal live-backend matrix without redundant cross-product churn."""
    cases: list[MatrixCase] = []
    for theme_index, theme in enumerate(THEMES):
        for mode_index, mode in enumerate(NAVIGATION_MODES):
            for index, (viewport, scale) in enumerate(zip(VIEWPORTS, FONT_SCALES)):
                locale_fixture = LOCALE_FIXTURES[(theme_index + mode_index + index) % 2]
                cases.append(
                    MatrixCase(theme, mode, viewport, scale, locale_fixture)
                )
    return tuple(cases)


def build_catalog_matrix() -> tuple[MatrixCase, ...]:
    """Return 24 representative frames covering every axis and route family."""
    cases: list[MatrixCase] = []
    route_sets = {
        "standard": STANDARD_ROUTES,
        "advanced": ADVANCED_ROUTES,
    }
    for theme_index, theme in enumerate(THEMES):
        for mode_index, mode in enumerate(NAVIGATION_MODES):
            for slot in range(3):
                index = ((theme_index % 2) * 3) + slot
                route_id = route_sets[mode][index]
                cases.append(
                    MatrixCase(
                        theme=theme,
                        navigation_mode=mode,
                        viewport=VIEWPORTS[(theme_index + slot) % len(VIEWPORTS)],
                        scale_percent=FONT_SCALES[(theme_index + slot) % len(FONT_SCALES)],
                        locale_fixture=LOCALE_FIXTURES[
                            (theme_index + mode_index + slot) % len(LOCALE_FIXTURES)
                        ],
                        route_id=route_id,
                    )
                )
    return tuple(cases)


def validate_static_contract() -> list[str]:
    """Return repository-contract errors without importing PyQt or probing the host."""
    errors: list[str] = []
    matrix = build_automated_matrix()
    catalog = build_catalog_matrix()
    if len(matrix) != 400:
        errors.append("automated matrix must contain 400 cells")
    if len(catalog) != 24:
        errors.append("screenshot catalog must contain 24 representative cells")
    if {case.theme for case in matrix} != set(THEMES):
        errors.append("automated matrix does not cover every theme")
    if {case.navigation_mode for case in matrix} != set(NAVIGATION_MODES):
        errors.append("automated matrix does not cover both navigation modes")
    if {case.viewport for case in matrix} != set(VIEWPORTS):
        errors.append("automated matrix does not cover every viewport")
    if {case.scale_percent for case in matrix} != set(FONT_SCALES):
        errors.append("automated matrix does not cover every scale")
    if {case.locale_fixture for case in matrix} != set(LOCALE_FIXTURES):
        errors.append("automated matrix does not cover both locale fixtures")
    if any(not locale.startswith("en") for locale in LOCALE_FIXTURES):
        errors.append("Phase 7 fixtures must preserve the English-only product contract")
    if not set(STANDARD_ROUTES).issubset({case.route_id for case in catalog}):
        errors.append("catalog does not cover all Standard destinations")

    required_focus_selectors = (
        "QPushButton:focus",
        "QToolButton:focus",
        "QComboBox:focus",
        "QTreeWidget:focus",
        "QFrame#clickableCard:focus",
    )
    stylesheet = (SOURCE / "assets" / "base.qss").read_text(encoding="utf-8")
    for selector in required_focus_selectors:
        if selector not in stylesheet:
            errors.append(f"visible focus selector missing: {selector}")

    main_window = (SOURCE / "ui" / "main_window.py").read_text(encoding="utf-8")
    main_entry = (SOURCE / "main.py").read_text(encoding="utf-8")
    confirm_dialog = (SOURCE / "ui" / "confirm_dialog.py").read_text(encoding="utf-8")
    if "QTranslator" in main_entry or "QLocale.system" in main_entry:
        errors.append("GUI startup still loads system-locale translations")
    if (SOURCE / "resources" / "translations" / "sv.ts").exists():
        errors.append("non-English translation source remains packaged")
    if 'self.setAccessibleName(self.tr("Loofi Fedora Tweaks"))' not in main_window:
        errors.append("MainWindow accessible name contract is missing")
    if "self._status_label.setAccessibleDescription(text)" not in main_window:
        errors.append("result-state accessible description contract is missing")
    if "self.setAccessibleName(self.tr(\"Confirm action: %1\")" not in confirm_dialog:
        errors.append("confirmation-dialog accessible name contract is missing")
    return errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _settle(application: Any, cycles: int = 4) -> None:
    for _ in range(cycles):
        application.processEvents()


def _command_output(command: Sequence[str], timeout: int = 10) -> str:
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return ""
    return (completed.stdout or completed.stderr).strip()


def _git_value(*args: str) -> str:
    return _command_output(("git", *args))


def _apply_case(
    application: Any,
    window: Any,
    case: MatrixCase,
    base_point_size: float,
) -> list[str]:
    from PyQt6.QtCore import Qt
    from core.navigation import NavigationMode
    from ui.components import SectionItem
    from ui.design import ThemeManager

    mode = (
        NavigationMode.ADVANCED
        if case.navigation_mode == "advanced"
        else NavigationMode.STANDARD
    )
    window._rebuild_sidebar_for_navigation_mode(mode)

    font = application.font()
    font.setPointSizeF(base_point_size * case.scale_percent / 100.0)
    application.setFont(font)
    if not ThemeManager().apply(application, case.theme):
        return ["theme application failed"]

    window.resize(*case.viewport)
    window.show()
    _settle(application)
    if not window.switch_to_route(case.route_id):
        return [f"route did not resolve: {case.route_id}"]
    _settle(application)

    if case.locale_fixture == "en-long":
        for index in range(window.sidebar.topLevelItemCount()):
            item = window.sidebar.topLevelItem(index)
            if item is None:
                continue
            label = _LONG_ENGLISH_DESTINATIONS[
                index % len(_LONG_ENGLISH_DESTINATIONS)
            ]
            item.setData(0, Qt.ItemDataRole.AccessibleTextRole, label)
            item.setToolTip(0, label)
            if not window._sidebar_collapsed:
                item.setText(0, label)
        window._breadcrumb_frame.set_content(
            "System",
            _LONG_ENGLISH_PAGE_TITLE,
            _LONG_ENGLISH_PAGE_DESCRIPTION,
        )
        navigator = window.destination_host.navigator
        stressed = tuple(
            SectionItem(
                section.section_id,
                f"{section.label} och avancerade inställningar",
                section.description or _LONG_ENGLISH_PAGE_DESCRIPTION,
                section.status,
                section.icon,
            )
            for section in navigator.sections()
        )
        navigator.set_sections(stressed)
    _settle(application)
    return []


def _case_issues(application: Any, window: Any, case: MatrixCase) -> list[str]:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QScrollArea

    issues: list[str] = []
    strict_viewport = application.platformName() == "offscreen"
    rendered_width = window.width()
    if strict_viewport and (window.width(), window.height()) != case.viewport:
        issues.append(
            f"requested viewport {case.viewport} rendered as {(window.width(), window.height())}"
        )
    if rendered_width < 1180 and not window._sidebar_collapsed:
        issues.append("sidebar did not collapse below the wide breakpoint")
    if rendered_width >= 1180 and window._sidebar_collapsed:
        issues.append("sidebar remained collapsed at the wide breakpoint")
    if window.destination_host.is_compact() != (rendered_width < 900):
        issues.append("section navigator did not match the compact breakpoint")

    if not window.accessibleName() or not window.accessibleDescription():
        issues.append("MainWindow accessibility metadata is incomplete")
    if not window._breadcrumb_frame.accessibleName():
        issues.append("page title is not exposed through the page header")
    if not window.sidebar.accessibleName():
        issues.append("primary navigation has no accessible name")

    for index in range(window.sidebar.topLevelItemCount()):
        item = window.sidebar.topLevelItem(index)
        if item is None:
            continue
        accessible = item.data(0, Qt.ItemDataRole.AccessibleTextRole)
        if not str(accessible or "").strip():
            issues.append(f"sidebar row {index} has no accessible text")
        if not window._sidebar_collapsed and not item.text(0).strip():
            issues.append(f"expanded sidebar row {index} has no visible label")

    navigator = window.destination_host.navigator
    for index, section in enumerate(navigator.sections()):
        if not section.label.strip() or "…" in section.label:
            issues.append(f"section {index} has an empty or elided label")
        accessible = navigator.selector.itemData(
            index,
            Qt.ItemDataRole.AccessibleTextRole,
        )
        if not str(accessible or "").strip():
            issues.append(f"section {index} has no accessible selector text")

    for scroll_area in window.findChildren(QScrollArea):
        if not scroll_area.isVisible():
            continue
        horizontal = scroll_area.horizontalScrollBar()
        if horizontal is not None and horizontal.maximum() > 0:
            issues.append(
                f"unintended horizontal scrolling in {scroll_area.objectName() or scroll_area.__class__.__name__}"
            )

    palette = application.property("loofiSemanticPalette")
    failures = palette.contrast_failures() if hasattr(palette, "contrast_failures") else {"palette": 0.0}
    if failures:
        issues.append(f"semantic contrast failures: {sorted(failures)}")
    if ":focus" not in application.styleSheet():
        issues.append("visible focus styling is absent from the active stylesheet")

    central = window.centralWidget()
    for name, widget in (
        ("sidebar", window._sidebar_container),
        ("page header", window._breadcrumb_frame),
        ("content", window.content_area),
    ):
        top_left = widget.mapTo(central, widget.rect().topLeft())
        bottom_right = widget.mapTo(central, widget.rect().bottomRight())
        if top_left.x() < -1 or bottom_right.x() > central.width() + 1:
            issues.append(f"{name} extends beyond the horizontal shell geometry")
    return list(dict.fromkeys(issues))


def _keyboard_and_accessibility_issues(application: Any, window: Any) -> list[str]:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QDialog, QPushButton, QVBoxLayout
    from ui.components import EmptyState, InlineNotice, LoadingState
    from ui.confirm_dialog import ConfirmActionDialog

    issues: list[str] = []
    window.resize(1280, 720)
    window.switch_to_route("system_info")
    if application.platformName() != "offscreen":
        window.raise_()
        window.activateWindow()
        handle = window.windowHandle()
        if handle is not None:
            handle.requestActivate()
    _settle(application)

    window.sidebar.setFocus()
    _settle(application)
    if window.sidebar.focusPolicy() == Qt.FocusPolicy.NoFocus:
        issues.append("primary navigation is excluded from keyboard focus")
    before = window.sidebar.currentIndex().row()
    QTest.keyClick(window.sidebar, Qt.Key.Key_Down)
    _settle(application)
    after = window.sidebar.currentIndex().row()
    if window.sidebar.topLevelItemCount() > 1 and before == after:
        issues.append("primary navigation did not respond to keyboard-only movement")

    window.switch_to_route("system_info")
    _settle(application)
    navigator = window.destination_host.navigator
    control = navigator.selector if navigator.is_compact() else navigator.rail
    control.setFocus()
    _settle(application)
    if control.focusPolicy() == Qt.FocusPolicy.NoFocus:
        issues.append("section navigation is excluded from keyboard focus")
    if navigator.rail.count() > 1:
        before_section = navigator.active_section_id()
        QTest.keyClick(control, Qt.Key.Key_Down)
        _settle(application)
        if navigator.active_section_id() == before_section:
            issues.append("section navigation did not respond to keyboard-only movement")

    state_dialog = QDialog(window)
    state_dialog.setWindowTitle("Accessible state smoke")
    state_dialog.setAccessibleName("Accessible state smoke")
    state_layout = QVBoxLayout(state_dialog)
    states = (
        LoadingState("Reading system state"),
        EmptyState("No results", "Change the filter to continue"),
        InlineNotice("Completed", "No changes were needed", kind="success"),
    )
    for state in states:
        state_layout.addWidget(state)
        if not state.accessibleName() or not state.accessibleDescription():
            issues.append(f"{state.__class__.__name__} accessibility metadata is incomplete")
    state_dialog.show()
    _settle(application)
    state_dialog.close()
    state_dialog.deleteLater()

    confirmation = ConfirmActionDialog(
        parent=window,
        action="Remove selected packages",
        description="Review the package list before continuing.",
        undo_hint="The packages can be installed again later.",
        offer_snapshot=True,
        command_preview="dnf remove example",
        risk_level=ConfirmActionDialog.RISK_HIGH,
    )
    confirmation.show()
    _settle(application)
    if not confirmation.accessibleName() or not confirmation.accessibleDescription():
        issues.append("confirmation dialog accessibility metadata is incomplete")
    focusable = [
        button
        for button in confirmation.findChildren(QPushButton)
        if button.isVisible() and button.isEnabled()
    ]
    if not focusable or any(not (button.accessibleName() or button.text()) for button in focusable):
        issues.append("confirmation dialog has unnamed keyboard controls")
    QTest.keyClick(confirmation, Qt.Key.Key_Escape)
    _settle(application)
    if confirmation.result() != QDialog.DialogCode.Rejected:
        issues.append("confirmation dialog could not be cancelled from the keyboard")
    confirmation.deleteLater()
    return issues


def _interaction_issues(application: Any, window: Any) -> list[str]:
    """Exercise mouse, wheel/touchpad-equivalent, and resize input paths."""
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent
    from PyQt6.QtTest import QTest

    issues: list[str] = []
    collapsed_before = window._sidebar_collapsed
    QTest.mouseClick(
        window._sidebar_toggle,
        Qt.MouseButton.LeftButton,
        pos=window._sidebar_toggle.rect().center(),
    )
    _settle(application)
    if window._sidebar_collapsed == collapsed_before:
        issues.append("sidebar control did not respond to mouse activation")
    else:
        QTest.mouseClick(
            window._sidebar_toggle,
            Qt.MouseButton.LeftButton,
            pos=window._sidebar_toggle.rect().center(),
        )
        _settle(application)

    old_size = window.size()
    window.resize(860, 720)
    _settle(application)
    window.resize(1280, 720)
    _settle(application)
    if window.size() == old_size and old_size.width() != 1280:
        issues.append("window did not respond to resize behavior")

    current = window.content_area.currentWidget()
    if current is not None:
        position = current.rect().center()
        wheel = QWheelEvent(
            QPointF(position),
            QPointF(current.mapToGlobal(position)),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        application.sendEvent(current, wheel)
        _settle(application)
        if not wheel.isAccepted():
            issues.append("content did not accept touchpad/wheel-equivalent input")
    return issues


def _save_contact_sheet(group: str, frames: Sequence[dict[str, Any]], output_dir: Path) -> Path:
    from PyQt6.QtCore import QRect, QSize, Qt
    from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen

    columns = 3
    cell_width, cell_height = 420, 275
    header_height = 56
    rows = (len(frames) + columns - 1) // columns
    sheet = QImage(
        QSize(columns * cell_width, header_height + rows * cell_height),
        QImage.Format.Format_RGB32,
    )
    sheet.fill(QColor("#171a20"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.setPen(QPen(QColor("#f3f4f6")))
    title_font = QFont()
    title_font.setBold(True)
    title_font.setPointSize(14)
    painter.setFont(title_font)
    painter.drawText(
        QRect(16, 0, sheet.width() - 32, header_height),
        Qt.AlignmentFlag.AlignVCenter,
        group,
    )
    label_font = QFont()
    label_font.setPointSize(8)
    painter.setFont(label_font)
    for index, record in enumerate(frames):
        source = QImage(str(record["temporary_path"]))
        if source.isNull():
            raise RuntimeError(f"failed to read catalog frame: {record['temporary_path']}")
        row, column = divmod(index, columns)
        x = column * cell_width
        y = header_height + row * cell_height
        label = str(record["label"])
        painter.drawText(
            QRect(x + 8, y, cell_width - 16, 28),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )
        target = QRect(x + 10, y + 30, cell_width - 20, cell_height - 40)
        scaled = source.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawImage(
            target.x() + (target.width() - scaled.width()) // 2,
            target.y() + (target.height() - scaled.height()) // 2,
            scaled,
        )
        painter.setPen(QPen(QColor("#5d6470")))
        painter.drawRect(target)
        painter.setPen(QPen(QColor("#f3f4f6")))
    painter.end()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{group}.png"
    if not sheet.save(str(output), "PNG"):
        raise RuntimeError(f"failed to save contact sheet: {output}")
    return output


def _capture_catalog(
    application: Any,
    window: Any,
    base_point_size: float,
    output_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    issues: list[str] = []
    by_group: dict[str, list[dict[str, Any]]] = {}
    with tempfile.TemporaryDirectory(prefix="loofi-v16-phase7-catalog-") as temporary:
        raw_dir = Path(temporary)
        for case in build_catalog_matrix():
            case_issues = _apply_case(application, window, case, base_point_size)
            case_issues.extend(_case_issues(application, window, case))
            issues.extend(f"{case.case_id}: {issue}" for issue in case_issues)
            output = raw_dir / f"{case.case_id}.png"
            pixmap = window.grab()
            if pixmap.isNull() or not pixmap.save(str(output), "PNG"):
                issues.append(f"{case.case_id}: screenshot capture failed")
                continue
            group = f"{case.theme}__{case.navigation_mode}"
            record = {
                "case_id": case.case_id,
                "group": group,
                "label": (
                    f"{case.route_id} · {case.viewport[0]}x{case.viewport[1]} · "
                    f"{case.scale_percent}% · {case.locale_fixture}"
                ),
                "sha256": _sha256(output),
                "captured_dimensions": [pixmap.width(), pixmap.height()],
                "temporary_path": str(output),
            }
            records.append(record)
            by_group.setdefault(group, []).append(record)

        sheets: list[dict[str, Any]] = []
        for group, frames in sorted(by_group.items()):
            output = _save_contact_sheet(group, frames, output_dir)
            sheets.append(
                {
                    "group": group,
                    "path": str(output.relative_to(ROOT)),
                    "sha256": _sha256(output),
                    "frame_count": len(frames),
                }
            )
        for record in records:
            record.pop("temporary_path", None)
    return records, sheets, issues


def _host_evidence(application: Any, compositor_scale: int | None) -> dict[str, Any]:
    screen = application.primaryScreen()
    geometry = screen.geometry() if screen is not None else None
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
        "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
        "qt_platform": application.platformName(),
        "display": os.environ.get("DISPLAY", ""),
        "wayland_display": os.environ.get("WAYLAND_DISPLAY", ""),
        "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR", ""),
        "declared_compositor_scale_percent": compositor_scale,
        "screen_geometry": (
            [geometry.width(), geometry.height()] if geometry is not None else []
        ),
        "device_pixel_ratio": screen.devicePixelRatio() if screen is not None else None,
        "kscreen": _command_output(("kscreen-doctor", "-o")),
        "xrandr": _command_output(("xrandr", "--current")),
        "orca": _command_output(("orca", "--version")),
        "atspi_python": _command_output(
            (
                sys.executable,
                "-c",
                "import pyatspi; print('available')",
            )
        ),
    }


def run_validation(
    *,
    scope: str,
    backend: str,
    report_path: Path,
    capture_catalog: bool,
    compositor_scale: int | None,
) -> dict[str, Any]:
    """Run the selected real-shell matrix and write one evidence manifest."""
    os.environ["QT_QPA_PLATFORM"] = backend
    os.environ["QT_LINUX_ACCESSIBILITY"] = "0" if backend == "offscreen" else "1"
    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))

    from PyQt6.QtCore import QCoreApplication, QEvent
    from PyQt6.QtWidgets import QApplication
    from capture_v16_phase0 import guarded_subprocesses, isolated_capture_home
    from core.plugins.registry import PluginRegistry
    from ui.community_tab import CommunityTab
    from ui.desktop_tab import DesktopTab
    from ui.main_window import MainWindow
    from ui.network_tab import NetworkTab
    from ui.software_tab import _ApplicationsSubTab
    from utils.command_runner import CommandRunner
    from utils.settings import SettingsManager

    application = QApplication.instance() or QApplication(["validate-v16-phase7"])
    base_font = application.font()
    base_point_size = base_font.pointSizeF() if base_font.pointSizeF() > 0 else 10.0
    if scope == "automated":
        cases = build_automated_matrix()
    elif scope == "live":
        cases = build_live_matrix()
    else:
        cases = ()
    errors = validate_static_contract()
    case_records: list[dict[str, Any]] = []
    catalog_records: list[dict[str, Any]] = []
    contact_sheets: list[dict[str, Any]] = []

    def reject_command(*_args, **_kwargs):
        raise RuntimeError("Phase 7 validation rejected an asynchronous command")

    with isolated_capture_home(), ExitStack() as stack:
        stack.enter_context(guarded_subprocesses())
        stack.enter_context(patch.object(MainWindow, "_check_first_run", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_initialize_background_services", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_schedule_post_render_services", lambda self: None))
        stack.enter_context(patch.object(CommandRunner, "run_command", reject_command))
        stack.enter_context(patch.object(_ApplicationsSubTab, "on_activate", lambda self: None))
        stack.enter_context(patch.object(CommunityTab, "on_activate", lambda self: None))
        stack.enter_context(patch.object(NetworkTab, "_initial_load", lambda self: None))
        stack.enter_context(patch.object(DesktopTab, "_detect_displays", lambda self: None))
        stack.enter_context(patch.object(DesktopTab, "_load_session_info", lambda self: None))

        SettingsManager._reset_instance()
        PluginRegistry.reset()
        window = MainWindow()
        window.show()
        _settle(application)
        try:
            for case in cases:
                issues = _apply_case(application, window, case, base_point_size)
                issues.extend(_case_issues(application, window, case))
                unique_issues = list(dict.fromkeys(issues))
                errors.extend(f"{case.case_id}: {issue}" for issue in unique_issues)
                case_records.append(
                    {
                        **asdict(case),
                        "viewport": list(case.viewport),
                        "rendered_viewport": [window.width(), window.height()],
                        "case_id": case.case_id,
                        "status": "passed" if not unique_issues else "failed",
                        "issues": unique_issues,
                    }
                )

            interaction_errors = _keyboard_and_accessibility_issues(
                application, window
            )
            interaction_errors.extend(_interaction_issues(application, window))
            errors.extend(f"interaction: {issue}" for issue in interaction_errors)

            if capture_catalog:
                catalog_records, contact_sheets, catalog_errors = _capture_catalog(
                    application,
                    window,
                    base_point_size,
                    IMAGE_ROOT / "contact-sheets",
                )
                errors.extend(catalog_errors)
        finally:
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            _settle(application, 2)
            application.setFont(base_font)

    errors = list(dict.fromkeys(errors))
    payload: dict[str, Any] = {
        "schema_version": 1,
        "release": "v16.0.0 Clarity",
        "phase": 7,
        "scope": scope,
        "backend": backend,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_value("rev-parse", "HEAD"),
        "git_worktree_clean": not bool(_git_value("status", "--short")),
        "matrix_contract": {
            "themes": list(THEMES),
            "navigation_modes": list(NAVIGATION_MODES),
            "viewports": [list(viewport) for viewport in VIEWPORTS],
            "font_scales": list(FONT_SCALES),
            "locale_fixtures": list(LOCALE_FIXTURES),
            "complete_automated_cells": len(build_automated_matrix()),
            "executed_cells": len(case_records),
            "real_main_window": True,
        },
        "safety": {
            "temporary_home_and_xdg": True,
            "background_services_disabled": True,
            "asynchronous_commands_rejected": True,
            "mutating_subprocesses_rejected": True,
        },
        "interaction": {
            "keyboard_navigation": "passed" if not interaction_errors else "failed",
            "visible_focus": "passed" if not any("focus" in error for error in interaction_errors) else "failed",
            "confirmation_dialog": "passed" if not any("confirmation" in error for error in interaction_errors) else "failed",
            "mouse": "passed" if not any("mouse" in error for error in interaction_errors) else "failed",
            "touchpad_wheel_equivalent": "passed" if not any("wheel" in error for error in interaction_errors) else "failed",
            "resize": "passed" if not any("resize" in error for error in interaction_errors) else "failed",
            "errors": interaction_errors,
        },
        "contrast": {
            "text_minimum": 4.5,
            "interactive_focus_minimum": 3.0,
            "status": "passed" if not any("contrast" in error for error in errors) else "failed",
        },
        "host": _host_evidence(application, compositor_scale),
        "cases": case_records,
        "catalog_frames": catalog_records,
        "contact_sheets": contact_sheets,
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _default_report(scope: str, backend: str, compositor_scale: int | None) -> Path:
    if scope == "automated":
        return REPORT_ROOT / "V16_PHASE7_AUTOMATED.json"
    if scope == "catalog":
        return REPORT_ROOT / "V16_PHASE7_CATALOG.json"
    suffix = "WAYLAND" if backend == "wayland" else "X11"
    if compositor_scale is not None:
        suffix += f"_{compositor_scale}"
    return REPORT_ROOT / f"V16_PHASE7_{suffix}.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=("contract", "automated", "catalog", "live"),
        default="automated",
    )
    parser.add_argument(
        "--backend",
        choices=("offscreen", "wayland", "xcb"),
        default="offscreen",
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--compositor-scale", type=int, choices=FONT_SCALES)
    parser.add_argument("--no-catalog", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.scope == "contract":
        errors = validate_static_contract()
        payload = {
            "phase": 7,
            "automated_cells": len(build_automated_matrix()),
            "catalog_cells": len(build_catalog_matrix()),
            "status": "passed" if not errors else "failed",
            "errors": errors,
        }
    else:
        report = args.report or _default_report(
            args.scope,
            args.backend,
            args.compositor_scale,
        )
        payload = run_validation(
            scope=args.scope,
            backend=args.backend,
            report_path=report,
            capture_catalog=not args.no_catalog,
            compositor_scale=args.compositor_scale,
        )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"v16 Phase 7 validation: {payload['status']}")
        if args.scope != "contract":
            print(str(report.relative_to(ROOT)))
        for error in payload["errors"]:
            print(f"- {error}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
