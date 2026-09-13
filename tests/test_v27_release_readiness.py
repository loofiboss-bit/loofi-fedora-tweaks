"""Tests for v27 ReleaseReadiness diagnostics, targets, and advice."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.diagnostics.release_models import (
    TARGETS,
    ReleaseReadinessReport,
)
from core.diagnostics.release_readiness import ReleaseReadiness
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from core.platform.profile import (
    DeploymentBackend,
    DesktopEnvironment,
    PlatformProfile,
    SessionType,
)


class TestReleaseTargets:
    """Verify supported and preview Fedora release targets."""

    def test_list_targets_contains_stable_and_preview(self):
        targets = ReleaseReadiness.list_targets()
        target_keys = {t.key for t in targets}
        assert "44" in target_keys
        assert "45-preview" in target_keys

    def test_stable_target_metadata(self):
        target = ReleaseReadiness.get_target(
            FEDORA_RELEASE_POLICY.stable_target
        )
        assert target.key == FEDORA_RELEASE_POLICY.stable_target
        assert target.supported is True
        assert target.preview is False
        assert target.fedora_version == "44"

    def test_preview_target_metadata(self):
        target = ReleaseReadiness.get_target("45-preview")
        assert target.key == "45-preview"
        assert target.supported is False
        assert target.preview is True
        assert target.fedora_version == "45"


class TestFedoraVersionCheck:
    """Verify version matching and out-of-target behavior."""

    def test_exact_matching_target_passes(self):
        target = ReleaseReadiness.get_target("44")
        os_release = {
            "ID": "fedora",
            "VERSION_ID": "44",
            "PRETTY_NAME": "Fedora Linux 44",
        }
        check = ReleaseReadiness._fedora_version_check(os_release, target)
        assert check.status == "pass"
        assert check.severity == "info"
        assert "matches the supported" in check.summary

    def test_compatible_version_behavior(self):
        target = ReleaseReadiness.get_target("44")
        os_release = {
            "ID": "fedora",
            "VERSION_ID": "43",
            "PRETTY_NAME": "Fedora Linux 43",
        }
        check = ReleaseReadiness._fedora_version_check(os_release, target)
        assert check.status in ("info", "warning")

    def test_outside_version_warns(self):
        target = ReleaseReadiness.get_target("44")
        os_release = {
            "ID": "fedora",
            "VERSION_ID": "40",
            "PRETTY_NAME": "Fedora Linux 40",
        }
        check = ReleaseReadiness._fedora_version_check(os_release, target)
        assert check.status == "warning"
        assert check.severity == "warning"

    def test_missing_version_fails(self):
        target = ReleaseReadiness.get_target("44")
        os_release = {"ID": "fedora"}
        check = ReleaseReadiness._fedora_version_check(os_release, target)
        assert check.status == "error"


class TestReleaseReadinessReport:
    """Verify full readiness report generation and desktop neutrality."""

    @patch.object(
        ReleaseReadiness,
        "_os_release",
    )
    @patch("services.system.system.SystemManager.get_platform_profile")
    def test_run_produces_valid_neutral_report(
        self,
        mock_profile: MagicMock,
        mock_os_release: MagicMock,
    ):
        mock_profile.return_value = PlatformProfile(
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
        mock_os_release.return_value = {
            "ID": "fedora",
            "VERSION_ID": "44",
            "PRETTY_NAME": "Fedora Linux 44 (Workstation Edition)",
            "VARIANT_ID": "workstation",
        }
        report = ReleaseReadiness.run(target_key="44")
        assert isinstance(report, ReleaseReadinessReport)
        assert report.target == TARGETS["44"].label
        assert 0 <= report.score <= 100
        assert report.status in ("ready", "caution", "not_ready")
        assert len(report.checks) > 0

        # Verify desktop was neutral (desktop info is None for GNOME)
        assert report.desktop is None

        # Check serialization round-trip
        report_dict = report.to_dict()
        assert report_dict["target"] == report.target
        assert report_dict["score"] == report.score
        assert len(report_dict["checks"]) == len(report.checks)
