"""Tests for local, read-only software-source status checks."""

from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import patch

from services.software.source_status import (
    SOURCE_STATUS_KEYS,
    SoftwareSourceStatusService,
    SourceScope,
    SourceState,
    SourceStatus,
    SourceStatusReason,
)
from services.system.system import SystemManager


class TestSoftwareSourceStatusService(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SoftwareSourceStatusService()

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/dnf5")
    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.source_status.subprocess.run")
    def test_dnf_sources_are_aggregated_by_known_repository_ids(self, run, _manager, _which) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=["dnf5"],
            returncode=0,
            stdout=json.dumps(
                [
                    {"id": "rpmfusion-free", "is_enabled": True, "name": "Free"},
                    {"id": "rpmfusion-free-updates", "is_enabled": False, "name": "Free updates"},
                    {"id": "rpmfusion-nonfree", "is_enabled": False, "name": "Non-Free"},
                    {"id": "copr:copr.fedorainfracloud.org:loofitheboss:loofi-fedora-tweaks", "is_enabled": True, "name": "Loofi"},
                    {"id": "fedora", "is_enabled": True, "name": "Fedora"},
                ]
            ),
            stderr="",
        )

        statuses = self.service._dnf_statuses()

        self.assertEqual(
            [(status.source_id, status.state) for status in statuses],
            [
                ("rpmfusion-free", SourceState.ENABLED),
                ("rpmfusion-nonfree", SourceState.DISABLED),
                ("loofi-copr", SourceState.ENABLED),
            ],
        )
        run.assert_called_once_with(
            ["dnf5", "--cacheonly", "repolist", "--all", "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/dnf5")
    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.source_status.subprocess.run")
    def test_successful_empty_repository_list_means_sources_are_not_enabled(self, run, _manager, _which) -> None:
        run.return_value = subprocess.CompletedProcess(args=["dnf5"], returncode=0, stdout="[]", stderr="")

        statuses = self.service._dnf_statuses()

        self.assertTrue(all(status.state is SourceState.DISABLED for status in statuses))

    @patch("services.software.source_status.shutil.which", return_value=None)
    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.source_status.subprocess.run")
    def test_missing_dnf_tool_is_unknown_and_does_not_run_a_command(self, run, _manager, _which) -> None:
        statuses = self.service._dnf_statuses()

        self.assertTrue(all(status.state is SourceState.UNKNOWN for status in statuses))
        self.assertTrue(all(status.reason is SourceStatusReason.TOOL_UNAVAILABLE for status in statuses))
        run.assert_not_called()

    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="rpm-ostree")
    @patch("services.software.source_status.subprocess.run")
    def test_unsupported_deployment_backend_is_unknown(self, run, _manager) -> None:
        statuses = self.service._dnf_statuses()

        self.assertTrue(all(status.state is SourceState.UNKNOWN for status in statuses))
        self.assertTrue(all(status.reason is SourceStatusReason.UNSUPPORTED_BACKEND for status in statuses))
        run.assert_not_called()

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/dnf5")
    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.source_status.subprocess.run")
    def test_dnf_timeout_is_unknown(self, run, _manager, _which) -> None:
        run.side_effect = subprocess.TimeoutExpired("dnf5", 20)

        statuses = self.service._dnf_statuses()

        self.assertTrue(all(status.state is SourceState.UNKNOWN for status in statuses))
        self.assertTrue(all(status.reason is SourceStatusReason.TIMEOUT for status in statuses))

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/dnf5")
    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.source_status.subprocess.run")
    def test_dnf_nonzero_exit_is_unknown_with_exit_code(self, run, _manager, _which) -> None:
        run.return_value = subprocess.CompletedProcess(args=["dnf5"], returncode=7, stdout="", stderr="private detail")

        statuses = self.service._dnf_statuses()

        self.assertTrue(all(status.state is SourceState.UNKNOWN for status in statuses))
        self.assertTrue(all(status.reason is SourceStatusReason.COMMAND_FAILED for status in statuses))
        self.assertTrue(all(status.exit_code == 7 for status in statuses))

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/dnf5")
    @patch("services.software.source_status.SystemManager.get_package_manager", return_value="dnf5")
    @patch("services.software.source_status.subprocess.run")
    def test_malformed_dnf_json_is_unknown(self, run, _manager, _which) -> None:
        run.return_value = subprocess.CompletedProcess(args=["dnf5"], returncode=0, stdout="{broken", stderr="")

        statuses = self.service._dnf_statuses()

        self.assertTrue(all(status.state is SourceState.UNKNOWN for status in statuses))
        self.assertTrue(all(status.reason is SourceStatusReason.INVALID_RESPONSE for status in statuses))

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/flatpak")
    @patch("services.software.source_status.SystemManager.is_flathub_enabled", return_value=True)
    def test_flathub_scope_is_reported_separately(self, enabled, _which) -> None:
        system_status = self.service._flatpak_status(SourceScope.SYSTEM)
        user_status = self.service._flatpak_status(SourceScope.USER)

        self.assertEqual(system_status.state, SourceState.ENABLED)
        self.assertEqual(system_status.scope, SourceScope.SYSTEM)
        self.assertEqual(user_status.state, SourceState.ENABLED)
        self.assertEqual(user_status.scope, SourceScope.USER)
        self.assertEqual(
            [call.kwargs["scope"] for call in enabled.call_args_list],
            ["system", "user"],
        )

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/flatpak")
    @patch("services.software.source_status.SystemManager.is_flathub_enabled", return_value=False)
    def test_successful_flathub_absence_means_not_enabled(self, _enabled, _which) -> None:
        status = self.service._flatpak_status(SourceScope.USER)

        self.assertEqual(status.state, SourceState.DISABLED)
        self.assertIsNone(status.reason)

    @patch("services.software.source_status.shutil.which", return_value=None)
    @patch("services.software.source_status.SystemManager.is_flathub_enabled")
    def test_missing_flatpak_is_unknown(self, enabled, _which) -> None:
        status = self.service._flatpak_status(SourceScope.SYSTEM)

        self.assertEqual(status.state, SourceState.UNKNOWN)
        self.assertEqual(status.reason, SourceStatusReason.TOOL_UNAVAILABLE)
        enabled.assert_not_called()

    @patch("services.software.source_status.shutil.which", return_value="/usr/bin/flatpak")
    @patch("services.software.source_status.SystemManager.is_flathub_enabled", return_value=None)
    def test_flathub_probe_failure_is_not_reported_as_disabled(self, _enabled, _which) -> None:
        status = self.service._flatpak_status(SourceScope.SYSTEM)

        self.assertEqual(status.state, SourceState.UNKNOWN)
        self.assertEqual(status.reason, SourceStatusReason.PROBE_FAILED)

    @patch.object(SoftwareSourceStatusService, "_dnf_statuses")
    @patch.object(SoftwareSourceStatusService, "_flatpak_status")
    def test_snapshot_has_all_known_sources_in_stable_scope_order(self, flatpak_status, dnf_statuses) -> None:
        dnf_statuses.return_value = tuple(
            SourceStatus(source_id, scope, SourceState.DISABLED)
            for source_id, scope in SOURCE_STATUS_KEYS[:3]
        )
        flatpak_status.side_effect = lambda scope: self._make_test_status(scope)

        statuses = self.service.snapshot()

        self.assertEqual([(status.source_id, status.scope) for status in statuses], list(SOURCE_STATUS_KEYS))
        self.assertEqual(flatpak_status.call_args_list[0].args, (SourceScope.SYSTEM,))
        self.assertEqual(flatpak_status.call_args_list[1].args, (SourceScope.USER,))

    @staticmethod
    def _make_test_status(scope: SourceScope):
        from services.software.source_status import SourceStatus

        return SourceStatus("flathub", scope, SourceState.DISABLED)


class TestSystemManagerFlathubProbe(unittest.TestCase):
    @patch("services.system.system.cached_which", return_value="/usr/bin/flatpak")
    @patch("services.system.system.subprocess.run")
    def test_reads_flathub_for_requested_scope(self, run, _which) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=["flatpak"],
            returncode=0,
            stdout=json.dumps([{"name": "flathub", "options": "filtered"}]),
            stderr="",
        )

        self.assertTrue(SystemManager.is_flathub_enabled(scope="user"))

        run.assert_called_once_with(
            ["flatpak", "remotes", "--json", "--user"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    @patch("services.system.system.cached_which", return_value="/usr/bin/flatpak")
    @patch("services.system.system.subprocess.run")
    def test_valid_empty_remote_list_means_disabled(self, run, _which) -> None:
        run.return_value = subprocess.CompletedProcess(args=["flatpak"], returncode=0, stdout="[]", stderr="")

        self.assertFalse(SystemManager.is_flathub_enabled())

    @patch("services.system.system.cached_which", return_value="/usr/bin/flatpak")
    @patch("services.system.system.subprocess.run")
    def test_timeout_nonzero_and_malformed_response_are_unknown(self, run, _which) -> None:
        run.side_effect = subprocess.TimeoutExpired("flatpak", 10)
        self.assertIsNone(SystemManager.is_flathub_enabled())

        run.side_effect = None
        run.return_value = subprocess.CompletedProcess(args=["flatpak"], returncode=1, stdout="[]", stderr="")
        self.assertIsNone(SystemManager.is_flathub_enabled())

        run.return_value = subprocess.CompletedProcess(args=["flatpak"], returncode=0, stdout="oops", stderr="")
        self.assertIsNone(SystemManager.is_flathub_enabled())

    @patch("services.system.system.cached_which", return_value=None)
    @patch("services.system.system.subprocess.run")
    def test_missing_flatpak_or_invalid_scope_is_unknown_without_probe(self, run, _which) -> None:
        self.assertIsNone(SystemManager.is_flathub_enabled())
        self.assertIsNone(SystemManager.is_flathub_enabled(scope="invalid"))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
