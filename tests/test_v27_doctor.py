"""Fail-closed v27 doctor and reboot-state contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from cli.commands.diagnostic_commands import handle_doctor
from core.platform.profile import (
    DeploymentBackend,
    DesktopEnvironment,
    PlatformProfile,
    RebootStatus,
    SessionType,
    detect_platform_profile,
)
from services.system.system import SystemManager


def _profile(
    backend: DeploymentBackend,
    reboot_pending: bool | None = None,
) -> PlatformProfile:
    return PlatformProfile(
        os_id="fedora",
        fedora_version=44,
        variant_id="workstation",
        variant_name="Fedora Workstation",
        architecture="x86_64",
        desktop=DesktopEnvironment.GNOME,
        session_type=SessionType.WAYLAND,
        deployment_backend=backend,
        is_atomic=backend.is_atomic,
        reboot_pending=reboot_pending,
    )


def test_profile_serializes_enum_values_and_tri_state() -> None:
    profile = _profile(DeploymentBackend.RPM_OSTREE)

    payload = profile.to_dict()

    assert payload["desktop"] == "gnome"
    assert payload["session_type"] == "wayland"
    assert payload["deployment_backend"] == "rpm_ostree"
    assert payload["reboot_pending"] is None
    assert payload["reboot_status"] == "unknown"
    json.dumps(payload)

    assert profile.reboot_status is RebootStatus.UNKNOWN
    assert _profile(DeploymentBackend.RPM_OSTREE, True).reboot_state is RebootStatus.REQUIRED
    assert _profile(DeploymentBackend.RPM_OSTREE, False).reboot_status is RebootStatus.NOT_REQUIRED


def test_bootc_reboot_probe_is_unknown(tmp_path: Path) -> None:
    os_release = tmp_path / "os-release"
    os_release.write_text("ID=fedora\nVERSION_ID=44\n", encoding="utf-8")
    bootc = tmp_path / "bootc-booted"
    bootc.touch()
    checker = MagicMock(return_value=False)

    profile = detect_platform_profile(
        os_release_path=os_release,
        ostree_booted_path=tmp_path / "ostree-booted",
        bootc_booted_path=bootc,
        env={},
        which_cmd=lambda _: "/usr/bin/bootc",
        reboot_pending_checker=checker,
    )

    assert profile.deployment_backend is DeploymentBackend.BOOTC
    assert profile.reboot_pending is None
    assert profile.reboot_status is RebootStatus.UNKNOWN
    checker.assert_not_called()


def test_unknown_backend_does_not_invoke_reboot_checker(tmp_path: Path) -> None:
    os_release = tmp_path / "os-release"
    os_release.write_text("ID=fedora\nVERSION_ID=44\n", encoding="utf-8")
    checker = MagicMock(return_value=True)

    profile = detect_platform_profile(
        os_release_path=os_release,
        ostree_booted_path=tmp_path / "ostree-booted",
        bootc_booted_path=tmp_path / "bootc-booted",
        env={},
        which_cmd=lambda _: None,
        reboot_pending_checker=checker,
    )

    assert profile.deployment_backend is DeploymentBackend.UNKNOWN
    assert profile.reboot_pending is None
    checker.assert_not_called()


@patch("services.system.system.subprocess.run")
@patch("services.system.system.os.path.exists")
def test_rpm_ostree_reboot_probe_reports_pending(
    mock_exists: MagicMock,
    mock_run: MagicMock,
) -> None:
    mock_exists.side_effect = lambda path: path == "/run/ostree-booted"
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='{"deployments": [{"booted": false}, {"booted": true}]}'
    )

    assert SystemManager._check_reboot_pending() is True


@patch("services.system.system.subprocess.run")
@patch("services.system.system.os.path.exists")
def test_rpm_ostree_probe_failure_is_unknown(
    mock_exists: MagicMock,
    mock_run: MagicMock,
) -> None:
    mock_exists.side_effect = lambda path: path == "/run/ostree-booted"
    mock_run.return_value = MagicMock(returncode=1, stdout="")

    assert SystemManager._check_reboot_pending() is None


@patch("services.system.system.os.path.exists")
@patch("services.system.system.subprocess.run")
def test_bootc_probe_never_uses_rpm_ostree(
    mock_run: MagicMock,
    mock_exists: MagicMock,
) -> None:
    mock_exists.return_value = True

    assert SystemManager._check_reboot_pending() is None
    mock_run.assert_not_called()


def test_doctor_does_not_fabricate_platform_on_detection_error() -> None:
    output = MagicMock()
    with patch("core.platform.profile.detect_platform_profile", side_effect=RuntimeError("probe")):
        result = handle_doctor(
            True,
            output,
            MagicMock(),
            which_fn=lambda _: "/usr/bin/tool",
        )

    assert result == 1
    payload = output.call_args.args[0]
    assert payload["deployment_backend"] == "unknown"
    assert payload["desktop"] == "unknown"
    assert payload["session_type"] == "unknown"
    assert payload["reboot_pending"] is None
    assert payload["all_critical_ok"] is False


def test_doctor_requires_backend_and_critical_tools() -> None:
    output = MagicMock()
    profile = _profile(DeploymentBackend.DNF5, False)
    with patch("core.platform.profile.detect_platform_profile", return_value=profile):
        result = handle_doctor(
            True,
            output,
            MagicMock(),
            which_fn=lambda tool: "/usr/bin/" + tool if tool in {"pkexec", "systemctl", "dnf5"} else None,
        )

    assert result == 0
    payload = output.call_args.args[0]
    assert payload["deployment_backend"] == "dnf5"
    assert payload["critical"] == {
        "pkexec": True,
        "systemctl": True,
        "dnf5": True,
    }
    assert payload["all_critical_ok"] is True
