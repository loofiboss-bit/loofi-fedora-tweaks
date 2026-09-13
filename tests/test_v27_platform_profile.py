"""Tests for v27 PlatformProfile immutability and desktop neutrality."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.platform.profile import (
    DeploymentBackend,
    DesktopEnvironment,
    PlatformProfile,
    SessionType,
    detect_deployment_backend,
    detect_desktop,
    detect_platform_profile,
    detect_session_type,
)


class TestPlatformProfileImmutability:
    """Verify that PlatformProfile instances cannot be modified at runtime."""

    def test_profile_is_frozen(self):
        profile = PlatformProfile(
            os_id="fedora",
            fedora_version=44,
            variant_id="workstation",
            variant_name="Fedora Workstation",
            architecture="x86_64",
            desktop=DesktopEnvironment.GNOME,
            session_type=SessionType.WAYLAND,
            deployment_backend=DeploymentBackend.DNF5,
            is_atomic=False,
            reboot_pending=False,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            profile.is_atomic = True  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            profile.fedora_version = 45  # type: ignore[misc]

    def test_profile_properties(self):
        f44_traditional = PlatformProfile(
            os_id="fedora",
            fedora_version=44,
            variant_id="workstation",
            variant_name="Fedora Workstation",
            architecture="x86_64",
            desktop=DesktopEnvironment.GNOME,
            session_type=SessionType.WAYLAND,
            deployment_backend=DeploymentBackend.DNF5,
            is_atomic=False,
            reboot_pending=False,
        )
        assert f44_traditional.is_fedora is True
        assert f44_traditional.is_supported_release is True
        assert f44_traditional.is_preview_release is False
        assert f44_traditional.package_manager_name == "dnf5"

        f45_preview = PlatformProfile(
            os_id="fedora",
            fedora_version=45,
            variant_id="silverblue",
            variant_name="Fedora Silverblue",
            architecture="aarch64",
            desktop=DesktopEnvironment.GNOME,
            session_type=SessionType.WAYLAND,
            deployment_backend=DeploymentBackend.RPM_OSTREE,
            is_atomic=True,
            reboot_pending=True,
        )
        assert f45_preview.is_fedora is True
        assert f45_preview.is_supported_release is False
        assert f45_preview.is_preview_release is True
        assert f45_preview.package_manager_name == "rpm-ostree"


class TestDesktopDetection:
    """Verify desktop environment neutrality across environments."""

    @pytest.mark.parametrize(
        ("env", "expected"),
        [
            ({"XDG_CURRENT_DESKTOP": "GNOME"}, DesktopEnvironment.GNOME),
            (
                {"XDG_CURRENT_DESKTOP": "KDE", "DESKTOP_SESSION": "plasma"},
                DesktopEnvironment.KDE,
            ),
            (
                {
                    "XDG_CURRENT_DESKTOP": "X-Cinnamon",
                    "DESKTOP_SESSION": "cinnamon",
                },
                DesktopEnvironment.CINNAMON,
            ),
            ({"XDG_CURRENT_DESKTOP": "XFCE"}, DesktopEnvironment.XFCE),
            ({"XDG_CURRENT_DESKTOP": "sway"}, DesktopEnvironment.SWAY),
            ({"XDG_CURRENT_DESKTOP": "COSMIC"}, DesktopEnvironment.COSMIC),
            ({"XDG_CURRENT_DESKTOP": "MATE"}, DesktopEnvironment.MATE),
            ({"XDG_CURRENT_DESKTOP": "LXQt"}, DesktopEnvironment.LXQT),
            (
                {"XDG_CURRENT_DESKTOP": "unknown_wm"},
                DesktopEnvironment.UNKNOWN,
            ),
            ({}, DesktopEnvironment.UNKNOWN),
        ],
    )
    def test_detect_desktop(
        self, env: dict[str, str], expected: DesktopEnvironment
    ):
        assert detect_desktop(env) == expected


class TestSessionTypeDetection:
    """Verify display server protocol detection."""

    @pytest.mark.parametrize(
        ("env", "expected"),
        [
            ({"XDG_SESSION_TYPE": "wayland"}, SessionType.WAYLAND),
            ({"XDG_SESSION_TYPE": "x11"}, SessionType.X11),
            ({"WAYLAND_DISPLAY": "wayland-0"}, SessionType.WAYLAND),
            ({"DISPLAY": ":0"}, SessionType.X11),
            ({}, SessionType.UNKNOWN),
        ],
    )
    def test_detect_session_type(
        self, env: dict[str, str], expected: SessionType
    ):
        assert detect_session_type(env) == expected


class TestDeploymentBackendDetection:
    """Verify deployment backend detection for Atomic, bootc, traditional."""

    def test_bootc_detection(self):
        backend = detect_deployment_backend(is_atomic=True, is_bootc=True)
        assert backend == DeploymentBackend.BOOTC
        assert backend.is_atomic is True

    def test_rpm_ostree_detection(self):
        backend = detect_deployment_backend(is_atomic=True, is_bootc=False)
        assert backend == DeploymentBackend.RPM_OSTREE
        assert backend.is_atomic is True

    def test_dnf5_traditional_detection(self):
        which_mock = MagicMock(
            side_effect=lambda c: "/usr/bin/dnf5" if c == "dnf5" else None
        )
        backend = detect_deployment_backend(
            is_atomic=False, which_cmd=which_mock
        )
        assert backend == DeploymentBackend.DNF5
        assert backend.is_atomic is False

    def test_unknown_backend_fails_closed(self):
        which_mock = MagicMock(return_value=None)
        backend = detect_deployment_backend(
            is_atomic=False, which_cmd=which_mock
        )
        assert backend == DeploymentBackend.UNKNOWN
        assert backend.is_atomic is False


class TestPlatformProfileDetection:
    """Verify end-to-end platform profile construction with mock files."""

    def test_fedora_kinoite_atomic_detection(self, tmp_path: Path):
        os_release = tmp_path / "os-release"
        os_release.write_text(
            'NAME="Fedora Linux"\n'
            'VERSION="44 (Kinoite)"\n'
            'ID=fedora\n'
            'VERSION_ID=44\n'
            'VARIANT="Kinoite"\n'
            'VARIANT_ID=kinoite\n',
            encoding="utf-8",
        )
        ostree_booted = tmp_path / "ostree-booted"
        ostree_booted.touch()

        profile = detect_platform_profile(
            os_release_path=os_release,
            ostree_booted_path=ostree_booted,
            bootc_booted_path=tmp_path / "bootc-booted",
            env={"XDG_CURRENT_DESKTOP": "KDE", "XDG_SESSION_TYPE": "wayland"},
            reboot_pending_checker=lambda: True,
        )

        assert profile.is_fedora is True
        assert profile.fedora_version == 44
        assert profile.variant_id == "kinoite"
        assert profile.variant_name == "Kinoite"
        assert profile.desktop == DesktopEnvironment.KDE
        assert profile.session_type == SessionType.WAYLAND
        assert profile.deployment_backend == DeploymentBackend.RPM_OSTREE
        assert profile.is_atomic is True
        assert profile.reboot_pending is True
        assert profile.package_manager_name == "rpm-ostree"

    def test_non_fedora_fails_closed(self, tmp_path: Path):
        os_release = tmp_path / "os-release"
        os_release.write_text(
            'NAME="Ubuntu"\n'
            'ID=ubuntu\n'
            'VERSION_ID="24.04"\n',
            encoding="utf-8",
        )
        profile = detect_platform_profile(
            os_release_path=os_release,
            ostree_booted_path=tmp_path / "ostree-booted",
            bootc_booted_path=tmp_path / "bootc-booted",
            env={},
            which_cmd=lambda _: None,
        )

        assert profile.is_fedora is False
        assert profile.fedora_version is None
        assert profile.is_supported_release is False
        assert profile.deployment_backend == DeploymentBackend.UNKNOWN
        assert profile.is_atomic is False
