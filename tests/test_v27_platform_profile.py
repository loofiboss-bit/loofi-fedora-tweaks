"""Tests for v27 PlatformProfile immutability and desktop neutrality."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.platform.profile import (
    DeploymentBackend,
    DesktopEnvironment,
    PlatformProfile,
    RebootStatus,
    SessionType,
    _parse_os_release,
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

        bootc = PlatformProfile(
            os_id="fedora",
            fedora_version=44,
            variant_id="bootc",
            variant_name="Fedora bootc",
            architecture="x86_64",
            desktop=DesktopEnvironment.UNKNOWN,
            session_type=SessionType.UNKNOWN,
            deployment_backend=DeploymentBackend.BOOTC,
            is_atomic=True,
        )
        unknown = dataclasses.replace(bootc, deployment_backend=DeploymentBackend.UNKNOWN)
        assert bootc.package_manager_name == "bootc"
        assert unknown.package_manager_name == "unknown"

    def test_reboot_status_and_serialization_preserve_unknown(self):
        for pending, expected in (
            (True, RebootStatus.REQUIRED),
            (False, RebootStatus.NOT_REQUIRED),
            (None, RebootStatus.UNKNOWN),
        ):
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
                reboot_pending=pending,
            )
            assert profile.reboot_status is expected
            assert profile.reboot_state is expected
            assert profile.to_dict()["reboot_status"] == expected.value

    @patch("core.platform.profile.detect_platform_profile")
    def test_class_detector_uses_canonical_detector(self, mock_detect):
        expected = MagicMock(spec=PlatformProfile)
        mock_detect.return_value = expected

        result = PlatformProfile.detect(os_release_path=Path("/tmp/os-release"))

        assert result is expected
        mock_detect.assert_called_once_with(os_release_path=Path("/tmp/os-release"))


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

    def test_unknown_explicit_session_does_not_guess_from_display(self):
        assert detect_session_type(
            {"XDG_SESSION_TYPE": "mir", "DISPLAY": ":0"}
        ) is SessionType.UNKNOWN


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

    def test_broken_path_probe_fails_closed(self):
        def broken_which(_command: str) -> str | None:
            raise OSError("PATH unavailable")

        assert detect_deployment_backend(
            is_atomic=False,
            which_cmd=broken_which,
        ) == DeploymentBackend.UNKNOWN

    def test_dnf_fallback_is_supported(self):
        def which_dnf(command: str) -> str | None:
            return "/usr/bin/dnf" if command == "dnf" else None

        assert detect_deployment_backend(
            is_atomic=False,
            which_cmd=which_dnf,
        ) == DeploymentBackend.DNF5

    def test_profile_preserves_legacy_dnf_executable(self, tmp_path: Path):
        os_release = tmp_path / "os-release"
        os_release.write_text(
            'ID="fedora"\nVERSION_ID="44"\nVARIANT_ID="workstation"\n',
            encoding="utf-8",
        )
        profile = detect_platform_profile(
            os_release_path=os_release,
            ostree_booted_path=tmp_path / "missing-ostree",
            bootc_booted_path=tmp_path / "missing-bootc",
            env={"XDG_CURRENT_DESKTOP": "GNOME", "XDG_SESSION_TYPE": "wayland"},
            which_cmd=lambda command: "/usr/bin/dnf" if command == "dnf" else None,
        )
        assert profile.deployment_backend is DeploymentBackend.DNF5
        assert profile.package_manager_command == "dnf"
        assert profile.package_manager_name == "dnf"


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

    def test_atomic_build_suffix_keeps_fedora_major(self, tmp_path: Path):
        os_release = tmp_path / "os-release"
        os_release.write_text(
            "ID=fedora\nVERSION_ID=44.20240901\n",
            encoding="utf-8",
        )
        profile = detect_platform_profile(
            os_release_path=os_release,
            ostree_booted_path=tmp_path / "missing-ostree",
            bootc_booted_path=tmp_path / "missing-bootc",
            env={},
            which_cmd=lambda command: "/usr/bin/dnf5" if command == "dnf5" else None,
        )
        assert profile.fedora_version == 44

    def test_probe_errors_and_invalid_reboot_value_remain_unknown(self, tmp_path: Path):
        os_release = tmp_path / "os-release"
        os_release.write_text(
            "ID=fedora\nVERSION_ID=44\n",
            encoding="utf-8",
        )

        class BrokenPath:
            def exists(self) -> bool:
                raise OSError("probe unavailable")

        with patch(
            "core.platform.profile.platform.machine",
            side_effect=OSError("arch unavailable"),
        ):
            profile = detect_platform_profile(
                os_release_path=os_release,
                ostree_booted_path=BrokenPath(),  # type: ignore[arg-type]
                bootc_booted_path=BrokenPath(),  # type: ignore[arg-type]
                env={"XDG_SESSION_TYPE": "wayland"},
                which_cmd=lambda _command: None,
                reboot_pending_checker=lambda: "unexpected",  # type: ignore[return-value]
            )

        assert profile.architecture == "unknown"
        assert profile.deployment_backend == DeploymentBackend.UNKNOWN
        assert profile.reboot_status is RebootStatus.UNKNOWN

    def test_invalid_reboot_probe_value_is_discarded(self, tmp_path: Path):
        os_release = tmp_path / "os-release"
        os_release.write_text("ID=fedora\nVERSION_ID=44\n", encoding="utf-8")

        profile = detect_platform_profile(
            os_release_path=os_release,
            ostree_booted_path=tmp_path / "ostree",
            bootc_booted_path=tmp_path / "bootc",
            which_cmd=lambda command: "/usr/bin/dnf5" if command == "dnf5" else None,
            reboot_pending_checker=lambda: "unexpected",  # type: ignore[return-value]
        )

        assert profile.deployment_backend is DeploymentBackend.DNF5
        assert profile.reboot_pending is None

    def test_reboot_probe_exception_is_discarded(self, tmp_path: Path):
        os_release = tmp_path / "os-release"
        os_release.write_text("ID=fedora\nVERSION_ID=44\n", encoding="utf-8")

        def broken_checker() -> bool:
            raise RuntimeError("probe unavailable")

        profile = detect_platform_profile(
            os_release_path=os_release,
            ostree_booted_path=tmp_path / "ostree",
            bootc_booted_path=tmp_path / "bootc",
            which_cmd=lambda command: "/usr/bin/dnf5" if command == "dnf5" else None,
            reboot_pending_checker=broken_checker,
        )

        assert profile.reboot_pending is None

    def test_reboot_checker_is_not_called_for_foreign_os(self, tmp_path: Path):
        os_release = tmp_path / "os-release"
        os_release.write_text("ID=ubuntu\nVERSION_ID=24.04\n", encoding="utf-8")
        checker = MagicMock(return_value=True)

        detect_platform_profile(
            os_release_path=os_release,
            ostree_booted_path=tmp_path / "ostree",
            bootc_booted_path=tmp_path / "bootc",
            reboot_pending_checker=checker,
        )

        checker.assert_not_called()

    def test_os_release_is_file_probe_error_fails_closed(self):
        class BrokenPath:
            def is_file(self) -> bool:
                raise OSError("stat unavailable")

        assert _parse_os_release(BrokenPath()) == {}  # type: ignore[arg-type]

    def test_os_release_parser_skips_comments_empty_lines_and_invalid_lines(self, tmp_path: Path):
        path = tmp_path / "os-release"
        path.write_text(
            "\n# comment\ninvalid\n ID = 'fedora' \nVERSION_ID=44\n",
            encoding="utf-8",
        )

        assert _parse_os_release(path) == {"ID": "fedora", "VERSION_ID": "44"}

    def test_os_release_parser_read_error_fails_closed(self, tmp_path: Path):
        path = tmp_path / "os-release"
        path.touch()

        with patch.object(Path, "read_text", side_effect=OSError("read unavailable")):
            assert _parse_os_release(path) == {}

    def test_os_release_parser_missing_file_returns_empty(self, tmp_path: Path):
        assert _parse_os_release(tmp_path / "missing-os-release") == {}

    def test_fedora_without_variant_is_marked_unknown(self, tmp_path: Path):
        path = tmp_path / "os-release"
        path.write_text("ID=fedora\nVERSION_ID=44\n", encoding="utf-8")

        profile = detect_platform_profile(
            os_release_path=path,
            ostree_booted_path=tmp_path / "ostree",
            bootc_booted_path=tmp_path / "bootc",
            which_cmd=lambda command: "/usr/bin/dnf5" if command == "dnf5" else None,
        )

        assert profile.variant_id == "unknown"

    def test_atomic_without_variant_is_marked_atomic(self, tmp_path: Path):
        path = tmp_path / "os-release"
        path.write_text("ID=fedora\nVERSION_ID=44\n", encoding="utf-8")
        ostree = tmp_path / "ostree"
        ostree.touch()

        profile = detect_platform_profile(
            os_release_path=path,
            ostree_booted_path=ostree,
            bootc_booted_path=tmp_path / "bootc",
            which_cmd=lambda _command: None,
        )

        assert profile.variant_id == "atomic"
