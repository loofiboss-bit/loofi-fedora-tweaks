"""Actual reboot persistence checkpoint, run twice in one owned guest overlay."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from helpers import activate_control, click, open_search_result, wait_for_node, wait_for_setting_feedback
from test_fedora_kde_workflows import dolphin_full_path_enabled


CHECKPOINT = Path("/var/tmp/loofi-e2e/reboot-checkpoint.json")


def guide_path() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "loofi-fedora-tweaks/guides.json"


@pytest.mark.skipif(os.environ.get("LOOFI_E2E_PHASE") != "before-reboot", reason="requires explicit host reboot orchestration")
def test_prepare_real_guest_reboot_checkpoint(loofi_app) -> None:
    """Persist a real setting and guide progress; host runner reboots next."""
    before = dolphin_full_path_enabled()
    open_search_result("Make Fedora yours", "Make Fedora yours")
    progress = json.loads(guide_path().read_text())
    # The before-reboot phase includes the independently verified guide-resume
    # scenario. Keep its next unfinished step intact rather than skipping more.
    assert progress["active_guide"] == "make-fedora-yours"
    assert progress["steps"]["make-fedora-yours:find-settings"]["state"] == "skipped"
    wait_for_node("Tweaks", role="table cell").click()
    search = wait_for_node("Search tweaks", role="text")
    search.element.clear()
    search.element.send_keys("Show full path in location bar")
    control = wait_for_node("Show full path in location bar", role="check box", timeout=60, enabled=True)
    assert control.checked == before
    control.click()
    wait_for_setting_feedback("Show full path in location bar", "Off" if before else "On", session_activation=True)
    assert dolphin_full_path_enabled() != before
    CHECKPOINT.write_text(json.dumps({"boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                                      "dolphin_before": before, "guides": progress}))
    CHECKPOINT.chmod(0o600)


@pytest.mark.skipif(os.environ.get("LOOFI_E2E_PHASE") != "after-reboot", reason="requires actual host-orchestrated guest reboot")
def test_saved_setting_and_guide_survive_actual_guest_reboot(loofi_app) -> None:
    checkpoint = json.loads(CHECKPOINT.read_text())
    assert Path("/proc/sys/kernel/random/boot_id").read_text().strip() != checkpoint["boot_id"], "guest did not reboot"
    before = checkpoint["dolphin_before"]
    assert dolphin_full_path_enabled() != before
    assert json.loads(guide_path().read_text()) == checkpoint["guides"], "guide state changed during reboot"
    wait_for_node("Overview", role="table cell").click()
    wait_for_node("Active Fedora guide: Make Fedora yours", timeout=30)
    activate_control("Active Fedora guide: Make Fedora yours")
    wait_for_node("Open next step: Review a desktop change", role="menu item", timeout=30).click()
    search = wait_for_node("Search tweaks", role="text", timeout=30)
    search.element.clear()
    search.element.send_keys("Show full path in location bar")
    wait_for_node("Show full path in location bar", role="check box", timeout=60, enabled=True)
    from helpers import confirm_yes
    click("Restore previous value for Show full path in location bar")
    confirm_yes()
    wait_for_setting_feedback("Show full path in location bar", "On" if before else "Off", restored=True)
    assert dolphin_full_path_enabled() == before
    # An independent KDE reader agrees after restoration and actual reboot.
    result = subprocess.run(["kreadconfig6", "--file", "dolphinrc", "--group", "General", "--key", "ShowFullPath", "--default", "false"],
                            check=True, capture_output=True, text=True, timeout=10)
    assert (result.stdout.strip().lower() == "true") == before
