"""Tests for core.platform.profile: immutable, fail-closed platform profiling."""

from pathlib import Path
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


def test_detect_desktop_variations():
    assert detect_desktop({"XDG_CURRENT_DESKTOP": "KDE"}) == DesktopEnvironment.KDE
    assert detect_desktop({"XDG_CURRENT_DESKTOP": "GNOME"}) == DesktopEnvironment.GNOME
    assert detect_desktop({"XDG_CURRENT_DESKTOP": "XFCE"}) == DesktopEnvironment.XFCE
    assert detect_desktop({"XDG_CURRENT_DESKTOP": "sway"}) == DesktopEnvironment.SWAY
    assert detect_desktop({"XDG_CURRENT_DESKTOP": "COSMIC"}) == DesktopEnvironment.COSMIC
    assert detect_desktop({"XDG_CURRENT_DESKTOP": "X-Cinnamon"}) == DesktopEnvironment.CINNAMON
    assert detect_desktop({"XDG_CURRENT_DESKTOP": "MATE"}) == DesktopEnvironment.MATE
    assert detect_desktop({"XDG_CURRENT_DESKTOP": "LXQt"}) == DesktopEnvironment.LXQT
    assert detect_desktop({"XDG_CURRENT_DESKTOP": "CustomWM"}) == DesktopEnvironment.UNKNOWN
    assert detect_desktop({}) == DesktopEnvironment.UNKNOWN


def test_detect_session_type():
    assert detect_session_type({"XDG_SESSION_TYPE": "wayland"}) == SessionType.WAYLAND
    assert detect_session_type({"XDG_SESSION_TYPE": "x11"}) == SessionType.X11
    assert detect_session_type({"WAYLAND_DISPLAY": "wayland-0"}) == SessionType.WAYLAND
    assert detect_session_type({"DISPLAY": ":0"}) == SessionType.X11
    assert detect_session_type({}) == SessionType.UNKNOWN


def test_detect_deployment_backend():
    assert detect_deployment_backend(is_atomic=True, is_bootc=False) == DeploymentBackend.RPM_OSTREE
    assert detect_deployment_backend(is_atomic=True, is_bootc=True) == DeploymentBackend.BOOTC

    # Non-atomic with dnf5
    which_dnf5 = lambda cmd: "/usr/bin/dnf5" if cmd == "dnf5" else None
    assert detect_deployment_backend(is_atomic=False, is_bootc=False, which_cmd=which_dnf5) == DeploymentBackend.DNF5

    # Non-atomic with neither
    which_none = lambda cmd: None
    assert detect_deployment_backend(is_atomic=False, is_bootc=False, which_cmd=which_none) == DeploymentBackend.UNKNOWN


def test_platform_profile_fedora_kde(tmp_path: Path):
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="Fedora Linux"\n'
        'ID=fedora\n'
        'VERSION_ID=44\n'
        'VARIANT="KDE Plasma"\n'
        'VARIANT_ID=kde\n'
    )
    ostree = tmp_path / "ostree-booted"  # doesn't exist
    bootc = tmp_path / "bootc-booted"

    env = {"XDG_CURRENT_DESKTOP": "KDE", "XDG_SESSION_TYPE": "wayland"}
    which = lambda cmd: "/usr/bin/dnf5" if cmd in ("dnf5", "dnf") else None

    profile = detect_platform_profile(
        os_release_path=os_release,
        ostree_booted_path=ostree,
        bootc_booted_path=bootc,
        env=env,
        which_cmd=which,
        reboot_pending_checker=lambda: False,
    )

    assert profile.is_fedora is True
    assert profile.fedora_version == 44
    assert profile.variant_id == "kde"
    assert profile.variant_name == "KDE Plasma"
    assert profile.desktop == DesktopEnvironment.KDE
    assert profile.session_type == SessionType.WAYLAND
    assert profile.deployment_backend == DeploymentBackend.DNF5
    assert profile.is_atomic is False
    assert profile.reboot_pending is False
    assert profile.is_supported_release is True
    assert profile.is_preview_release is False
    assert profile.package_manager_name == "dnf5"


def test_platform_profile_silverblue(tmp_path: Path):
    os_release = tmp_path / "os-release"
    os_release.write_text(
        '# test comment line\n'
        'NAME="Fedora Linux"\n'
        'ID=fedora\n'
        'VERSION_ID=43\n'
        'VARIANT="Silverblue"\n'
        'VARIANT_ID=silverblue\n'
    )
    ostree = tmp_path / "ostree-booted"
    ostree.touch()
    bootc = tmp_path / "bootc-booted"

    env = {"XDG_CURRENT_DESKTOP": "GNOME", "XDG_SESSION_TYPE": "wayland"}

    profile = detect_platform_profile(
        os_release_path=os_release,
        ostree_booted_path=ostree,
        bootc_booted_path=bootc,
        env=env,
        reboot_pending_checker=lambda: True,
    )

    assert profile.is_fedora is True
    assert profile.fedora_version == 43
    assert profile.variant_id == "silverblue"
    assert profile.desktop == DesktopEnvironment.GNOME
    assert profile.session_type == SessionType.WAYLAND
    assert profile.deployment_backend == DeploymentBackend.RPM_OSTREE
    assert profile.is_atomic is True
    assert profile.reboot_pending is True
    assert profile.is_supported_release is True
    assert profile.package_manager_name == "rpm-ostree"


def test_platform_profile_bootc(tmp_path: Path):
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="Fedora Linux"\n'
        'ID=fedora\n'
        'VERSION_ID=44\n'
    )
    ostree = tmp_path / "ostree-booted"
    bootc = tmp_path / "bootc-booted"
    bootc.touch()

    profile = detect_platform_profile(
        os_release_path=os_release,
        ostree_booted_path=ostree,
        bootc_booted_path=bootc,
        env={},
        which_cmd=lambda cmd: None,
    )

    assert profile.is_atomic is True
    assert profile.deployment_backend == DeploymentBackend.BOOTC
    assert profile.package_manager_name == "bootc"


def test_platform_profile_preview_release(tmp_path: Path):
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'ID=fedora\n'
        'VERSION_ID=45\n'
    )
    profile = detect_platform_profile(
        os_release_path=os_release,
        ostree_booted_path=tmp_path / "nonexistent",
        bootc_booted_path=tmp_path / "nonexistent",
        env={},
    )
    assert profile.fedora_version == 45
    assert profile.is_supported_release is False
    assert profile.is_preview_release is True


def test_platform_profile_fail_closed_non_fedora(tmp_path: Path):
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'NAME="Ubuntu"\n'
        'ID=ubuntu\n'
        'VERSION_ID="24.04"\n'
    )
    profile = detect_platform_profile(
        os_release_path=os_release,
        ostree_booted_path=tmp_path / "nonexistent",
        bootc_booted_path=tmp_path / "nonexistent",
        env={},
        which_cmd=lambda cmd: None,
    )

    assert profile.is_fedora is False
    assert profile.fedora_version is None
    assert profile.desktop == DesktopEnvironment.UNKNOWN
    assert profile.deployment_backend == DeploymentBackend.UNKNOWN
    assert profile.variant_id == "non-fedora"
    assert profile.reboot_pending is None


def test_platform_profile_fail_closed_missing_file(tmp_path: Path):
    profile = detect_platform_profile(
        os_release_path=tmp_path / "nonexistent-os-release",
        ostree_booted_path=tmp_path / "nonexistent-ostree",
        bootc_booted_path=tmp_path / "nonexistent-bootc",
        env={},
        which_cmd=lambda cmd: None,
    )

    assert profile.is_fedora is False
    assert profile.fedora_version is None
    assert profile.desktop == DesktopEnvironment.UNKNOWN
    assert profile.session_type == SessionType.UNKNOWN
    assert profile.deployment_backend == DeploymentBackend.UNKNOWN
    assert profile.is_atomic is False
    assert profile.reboot_pending is None


def test_platform_profile_reboot_checker_exception(tmp_path: Path):
    def bad_checker():
        raise RuntimeError("boom")

    profile = detect_platform_profile(
        os_release_path=tmp_path / "nonexistent",
        ostree_booted_path=tmp_path / "nonexistent",
        bootc_booted_path=tmp_path / "nonexistent",
        env={},
        reboot_pending_checker=bad_checker,
    )
    assert profile.reboot_pending is None


def test_platform_profile_edge_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert DeploymentBackend.RPM_OSTREE.is_atomic is True
    assert DeploymentBackend.BOOTC.is_atomic is True
    assert DeploymentBackend.DNF5.is_atomic is False
    assert DeploymentBackend.UNKNOWN.is_atomic is False

    # Package manager name unknown
    unknown_profile = detect_platform_profile(
        os_release_path=tmp_path / "nonexistent",
        ostree_booted_path=tmp_path / "nonexistent",
        bootc_booted_path=tmp_path / "nonexistent",
        env={},
        which_cmd=lambda cmd: None,
    )
    assert unknown_profile.package_manager_name == "unknown"

    # dnf fallback when dnf5 not found
    which_dnf_fallback = lambda cmd: "/usr/bin/dnf" if cmd == "dnf" else None
    assert detect_deployment_backend(is_atomic=False, is_bootc=False, which_cmd=which_dnf_fallback) == DeploymentBackend.DNF5

    # Default env detection
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.setenv("DESKTOP_SESSION", "gnome")
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert detect_desktop() == DesktopEnvironment.GNOME
    assert detect_session_type() == SessionType.WAYLAND

    # os-release unreadable (permission/OSError)
    unreadable = tmp_path / "unreadable-os-release"
    unreadable.touch()
    monkeypatch.setattr(Path, "read_text", lambda self, *args, **kwargs: (_ for _ in ()).throw(OSError("mock read error")))
    profile_err = detect_platform_profile(
        os_release_path=unreadable,
        ostree_booted_path=tmp_path / "nonexistent",
        bootc_booted_path=tmp_path / "nonexistent",
    )
    assert profile_err.is_fedora is False

