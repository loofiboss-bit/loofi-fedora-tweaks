"""Capture v32 documentation screenshots offscreen (no system changes).

Usage: QT_QPA_PLATFORM=offscreen python3 scripts/capture_v32_screenshots.py docs/images
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "loofi-fedora-tweaks"))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.platform.profile import DeploymentBackend, DesktopEnvironment, PlatformProfile, SessionType  # noqa: E402
from core.tasks.tweaks import TweakState, default_for, visible_tweaks  # noqa: E402

PROFILE = PlatformProfile(
    os_id="fedora", fedora_version=44, variant_id="workstation", variant_name="Fedora Workstation",
    architecture="x86_64", desktop=DesktopEnvironment.GNOME, session_type=SessionType.WAYLAND,
    deployment_backend=DeploymentBackend.DNF5, is_atomic=False, reboot_pending=False, package_manager_command="dnf5",
)
CHANGED = {"gnome-hot-corners", "gnome-accent-color"}


def demo_states() -> tuple[TweakState, ...]:
    states = []
    for tweak in visible_tweaks(PROFILE):
        value = default_for(tweak) or tweak.choices[0][0]
        if tweak.id in CHANGED:
            value = next(v for v, _label in tweak.choices if v != value)
        states.append(TweakState(tweak, "ready", value=value, choices=tweak.choices))
    return tuple(states)


def main(out: Path) -> None:
    app = QApplication([])
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
    window.resize(1280, 820)
    window.show()
    out.mkdir(parents=True, exist_ok=True)

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
        window.grab().save(str(out / f"{name}.png"))
        print("saved", name)

    for name, route in (("tweaks", "tweaks"), ("apps", "apps"), ("updates", "updates"), ("health", "health"), ("settings", "settings")):
        try:
            snap(name, route)
        except Exception as exc:  # report and continue with the other pages
            print("failed", name, exc)
    window.cleanup(0.5)
    window.close()
    window.deleteLater()


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/images/v32"))
