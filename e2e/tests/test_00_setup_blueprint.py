"""Targeted portable-setup and interrupted-review check in Fedora KDE."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from core.actions.operation_controller import OperationController
from core.tasks.setup_configurations import (
    SetupApplication,
    SetupDocument,
    SetupLibrary,
    SetupProgressStore,
    compare_setup,
    parse_setup,
    serialize_setup,
    setup_app_from_installed,
)
from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweaks import _profile_desktop, snapshot
from services.software.installed_applications import InstalledApplicationService
from services.system import SystemManager


def test_setup_export_import_preview_and_interrupted_review(tmp_path: Path) -> None:
    """Exercise the actual Fedora inventory, import preview, and restart state."""
    profile = SystemManager.get_platform_profile()
    assert _profile_desktop(profile) == "kde"
    controller = OperationController()
    states = snapshot(profile, controller.orchestrator.runtime, tweak_ids=("kde-single-click",))
    setting = next(state for state in states if state.tweak.id == "kde-single-click")
    assert setting.status == "ready", setting.message

    inventory = InstalledApplicationService().snapshot()
    assert "fedora" not in inventory.unknown_sources, inventory.errors
    installed_rpm = next((item for item in inventory.applications if item.source == "fedora"), None)
    assert installed_rpm is not None, "The isolated Fedora guest needs at least one visible installed RPM app."
    present = setup_app_from_installed(installed_rpm)
    absent = SetupApplication("fedora", "loofi-blueprint-e2e-absent", "loofi-blueprint-e2e-absent", name="Blueprint absent test package")
    document = SetupDocument("Blueprint E2E", (present, absent),
                             TweakProfile("Blueprint KDE", "kde", ((setting.tweak.id, setting.value),)))

    exported = serialize_setup(document)
    imported = SetupLibrary(tmp_path / "setup-library.json")
    identifier = imported.add(parse_setup(exported))
    assert imported.get(identifier) == document
    assert imported.get(identifier).applications[0] == present
    preview_path = tmp_path / "portable.json"
    preview_path.write_bytes(exported)

    # The modal is checked in its own offscreen Qt process so this data-format
    # test does not depend on AT-SPI or hide the separately tracked Qt defect.
    preview = '''
import sys
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox
from core.tasks.setup_configurations import parse_setup
from ui.setup_configurations import SetupConfigurationsPage
app = QApplication.instance() or QApplication([])
page = SetupConfigurationsPage()
document = parse_setup(open(sys.argv[1], "rb").read())
def accept_preview():
    dialogs = [item for item in QApplication.topLevelWidgets() if isinstance(item, QDialog) and item.isVisible()]
    if not dialogs:
        QTimer.singleShot(10, accept_preview)
        return
    buttons = dialogs[-1].findChild(QDialogButtonBox)
    if buttons is None or buttons.button(QDialogButtonBox.StandardButton.Ok) is None:
        raise RuntimeError("Import preview has no accessible confirmation control.")
    buttons.button(QDialogButtonBox.StandardButton.Ok).click()
QTimer.singleShot(0, accept_preview)
if not page._show_import_preview(document):
    raise RuntimeError("Portable import preview was not accepted.")
page.close()
'''
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_LINUX_ACCESSIBILITY_ALWAYS_ON": "0"}
    subprocess.run([sys.executable, "-c", preview, str(preview_path)], check=True, timeout=30,
                   capture_output=True, text=True, env=environment)

    comparison = compare_setup(document, identifier, inventory, states, current_desktop="kde")
    assert [entry.status for entry in comparison.entries] == ["present", "missing", "matches"]
    present_step = f"app:{present.identity}"
    missing_step = f"app:{absent.identity}"
    setting_step = f"setting:{setting.tweak.id}"
    progress_path = tmp_path / "setup-runs.json"
    crash_writer = r"""
import os
import sys
from pathlib import Path
from core.tasks.setup_configurations import SetupProgressStore

path, setup_id, digest, present_step, missing_step, setting_step = sys.argv[1:]
progress = SetupProgressStore(Path(path))
run_id = progress.start(setup_id, digest, (present_step, missing_step, setting_step))
for step, plan_id, action_run_id in (
    (present_step, "e2e-plan-present", "e2e-run-present"),
    (missing_step, "e2e-plan-missing", "e2e-run-missing"),
    (setting_step, "e2e-plan-setting", "e2e-run-setting"),
):
    progress.update(run_id, step, "running", plan_id=plan_id, action_run_id=action_run_id)
os._exit(86)
"""
    crashed = subprocess.run(
        [sys.executable, "-c", crash_writer, str(progress_path), identifier, document.digest,
         present_step, missing_step, setting_step],
        check=False, timeout=30, capture_output=True, text=True,
    )
    assert crashed.returncode == 86, crashed.stderr

    reopened = SetupProgressStore(progress_path)
    reopened.reconcile(identifier, document.digest, comparison)
    old_run = reopened.list()[0]
    assert old_run["status"] == "partial"
    assert old_run["steps"][present_step]["status"] == "satisfied"
    assert old_run["steps"][present_step]["plan_id"] == "e2e-plan-present"
    assert old_run["steps"][present_step]["run_id"] == "e2e-run-present"
    assert old_run["steps"][missing_step]["status"] == "interrupted"
    assert old_run["steps"][setting_step]["status"] == "satisfied"

    next_review = reopened.start(identifier, document.digest, (missing_step,))
    new_run = next(item for item in reopened.list() if item["id"] == next_review)
    assert new_run["steps"][missing_step] == {"status": "not_started"}
    assert [entry.status for entry in comparison.entries] == ["present", "missing", "matches"]
