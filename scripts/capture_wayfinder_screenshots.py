"""Capture Wayfinder fixture screenshots offscreen without host changes.

Usage: QT_SCALE_FACTOR=1.5 python3 scripts/capture_wayfinder_screenshots.py /tmp/wayfinder-150
"""

from __future__ import annotations

import os
import sys
import tempfile
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "loofi-fedora-tweaks"))

from PyQt6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType  # noqa: E402
from core.tasks.tweaks import TweakState, default_for, visible_tweaks  # noqa: E402

PROFILE = PlatformProfile(
    os_id="fedora", fedora_version=44, variant_id="workstation", variant_name="Fedora Workstation",
    architecture="x86_64", desktop=DesktopEnvironment.KDE, session_type=SessionType.WAYLAND,
    deployment_backend=DeploymentBackend.DNF5, is_atomic=False, reboot_pending=False, package_manager_command="dnf5",
)
CHANGED = {"kde-dolphin-editable-location", "kde-edge-tiling"}


def demo_states() -> tuple[TweakState, ...]:
    states = []
    for tweak in visible_tweaks(PROFILE):
        if not tweak.choices:
            states.append(TweakState(tweak, "unavailable", message="No service values in this rendering fixture."))
            continue
        value = default_for(tweak) or tweak.choices[0][0]
        if tweak.id in CHANGED:
            value = next(v for v, _label in tweak.choices if v != value)
        states.append(TweakState(tweak, "ready", value=value, choices=tweak.choices))
    return tuple(states)


def main(out: Path) -> None:
    fixture_home = Path(tempfile.mkdtemp(prefix="wayfinder-render-"))
    # Isolate all app persistence before importing UI modules.
    with ExitStack() as scope:
        scope.enter_context(patch("pathlib.Path.home", return_value=fixture_home))
        capture(out)


def capture(out: Path) -> None:
    app = QApplication([])
    from ui.design import ThemeManager
    ThemeManager().apply(app, "system")
    from ui.main_window import MainWindow
    from ui.tweaks_page import TweaksPage

    patches = [
        patch("ui.main_window.MainWindow._check_first_run"),
        patch("ui.main_window.MainWindow._initialize_background_services"),
        patch("ui.main_window.MainWindow._start_tweak_snapshot", return_value=True),
        patch("ui.main_window.SystemManager.is_atomic", return_value=False),
        patch("ui.main_window.SystemManager.get_platform_profile", return_value=PROFILE),
    ]
    for item in patches:
        item.start()
    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    out.mkdir(parents=True, exist_ok=True)

    focus_checks = []

    def snap(name: str, route: str) -> None:
        window.switch_to_route(route)
        for _ in range(5):
            app.processEvents()
        if route == "tweaks":
            page = window.findChild(TweaksPage)
            if page is not None:
                page.set_states(demo_states())
                for _ in range(5):
                    app.processEvents()
        window._breadcrumb_frame.settings_button.setFocus()
        for area in window.findChildren(QScrollArea):
            scrollbar = area.verticalScrollBar()
            if scrollbar is not None:
                scrollbar.setValue(0)
        app.processEvents()
        window.grab().save(str(out / f"{name}.png"))
        print("saved", name)
        for _ in range(20):
            window.focusNextChild()
            app.processEvents()
            focused = app.focusWidget()
            if focused is not None:
                assert focused.isVisibleTo(window), focused.objectName()
        focus_checks.append({"capture": name, "focus_traversals": 20,
                             "logical_size": [window.width(), window.height()],
                             "device_pixel_ratio": window.devicePixelRatioF()})

    for width, height in ((900, 650), (1280, 800)):
        window.resize(width, height)
        for route in ("tweaks", "apps", "updates", "health", "settings", "activity"):
            snap(f"{route}-{width}x{height}", route)
    for theme in ("light", "dark", "highcontrast"):
        window.load_theme(theme)
        snap(f"tweaks-{theme}-1280x800", "tweaks")
    (out / "rendering-checks.json").write_text(json.dumps(focus_checks, indent=2) + "\n")
    window.cleanup(0.5)
    window.close()
    window.deleteLater()


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/images/wayfinder"))
