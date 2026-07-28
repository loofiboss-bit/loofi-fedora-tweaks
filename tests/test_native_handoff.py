"""Fixed native desktop handoff service and presentation tests."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from core.catalog_models import CapabilityState, NativeHandoffId
from services.desktop.native_handoff import (
    NativeHandoffAvailability,
    NativeHandoffLaunch,
    NativeHandoffService,
)
from ui.native_handoff_card import NativeHandoffCard


class TestNativeHandoffService(unittest.TestCase):
    def test_allowlist_covers_exactly_five_opaque_ids(self):
        targets = NativeHandoffService.targets()

        self.assertEqual(len(targets), 5)
        self.assertEqual(
            {target.handoff_id for target in targets},
            set(NativeHandoffId),
        )
        self.assertNotIn("pkexec", {target.executable for target in targets})

    def test_discover_is_available_without_kcm_probe(self):
        which = MagicMock(return_value="/usr/bin/plasma-discover")
        runner = MagicMock()
        service = NativeHandoffService(which=which, runner=runner)

        availability = service.availability(NativeHandoffId.PLASMA_DISCOVER)

        self.assertTrue(availability.available)
        self.assertEqual(availability.state, CapabilityState.NATIVE_HANDOFF)
        runner.assert_not_called()

    def test_kcm_requires_exact_listed_module(self):
        result = subprocess.CompletedProcess(
            args=["/usr/bin/kcmshell6", "--list"],
            returncode=0,
            stdout=(
                "kcm_kscreen-extra - Similar but not exact\n"
                "kcm_kscreen - Manage displays\n"
            ),
            stderr="",
        )
        runner = MagicMock(return_value=result)
        service = NativeHandoffService(
            which=MagicMock(return_value="/usr/bin/kcmshell6"),
            runner=runner,
        )

        availability = service.availability(NativeHandoffId.PLASMA_DISPLAY)

        self.assertTrue(availability.available)
        runner.assert_called_once_with(
            ["/usr/bin/kcmshell6", "--list"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3.0,
        )

    def test_similarly_named_kcm_is_truthfully_unavailable(self):
        result = subprocess.CompletedProcess(
            args=["/usr/bin/kcmshell6", "--list"],
            returncode=0,
            stdout="kcm_kscreen-extra - Not the requested module\n",
            stderr="",
        )
        service = NativeHandoffService(
            which=MagicMock(return_value="/usr/bin/kcmshell6"),
            runner=MagicMock(return_value=result),
        )

        availability = service.availability(NativeHandoffId.PLASMA_DISPLAY)

        self.assertFalse(availability.available)
        self.assertEqual(availability.state, CapabilityState.UNAVAILABLE)
        self.assertIn("kcm_kscreen", availability.detail)

    def test_missing_executable_is_truthfully_unavailable(self):
        runner = MagicMock()
        service = NativeHandoffService(which=MagicMock(return_value=None), runner=runner)

        availability = service.availability(NativeHandoffId.PLASMA_APPEARANCE)

        self.assertFalse(availability.available)
        self.assertEqual(availability.state, CapabilityState.UNAVAILABLE)
        runner.assert_not_called()

    def test_failed_or_timed_out_kcm_probe_is_unavailable(self):
        for failure in (
            subprocess.CompletedProcess(
                args=["kcmshell6", "--list"],
                returncode=1,
                stdout="",
                stderr="failed",
            ),
            subprocess.TimeoutExpired(["kcmshell6", "--list"], 3),
        ):
            with self.subTest(failure=type(failure).__name__):
                runner = MagicMock()
                if isinstance(failure, BaseException):
                    runner.side_effect = failure
                else:
                    runner.return_value = failure
                service = NativeHandoffService(
                    which=MagicMock(return_value="/usr/bin/kcmshell6"),
                    runner=runner,
                )
                self.assertFalse(
                    service.availability(
                        NativeHandoffId.PLASMA_NETWORK_CONNECTIONS
                    ).available
                )

    def test_prepare_launch_returns_only_fixed_allowlisted_vector(self):
        result = subprocess.CompletedProcess(
            args=["/usr/bin/kcmshell6", "--list"],
            returncode=0,
            stdout="kcm_kwinoptions - Window behavior\n",
            stderr="",
        )
        service = NativeHandoffService(
            which=MagicMock(return_value="/usr/bin/kcmshell6"),
            runner=MagicMock(return_value=result),
        )

        launch = service.prepare_launch(
            NativeHandoffId.PLASMA_WINDOW_MANAGEMENT
        )

        self.assertEqual(
            launch,
            NativeHandoffLaunch(
                "/usr/bin/kcmshell6",
                ("kcm_kwinoptions",),
            ),
        )


class TestNativeHandoffCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_constructor_is_inert_and_accessible(self):
        service = MagicMock(spec=NativeHandoffService)

        card = NativeHandoffCard(
            NativeHandoffId.PLASMA_DISCOVER,
            title="Browse software",
            description="Open the complete catalogue.",
            button_text="Open Discover",
            service=service,
        )

        service.availability.assert_not_called()
        self.assertFalse(card.open_button.isEnabled())
        self.assertEqual(card.accessibleName(), "Browse software")
        self.assertEqual(card.open_button.accessibleName(), "Open Discover")

    def test_refresh_enables_only_available_target(self):
        target = NativeHandoffService.target(NativeHandoffId.PLASMA_DISCOVER)
        service = MagicMock(spec=NativeHandoffService)
        service.availability.return_value = NativeHandoffAvailability(
            target,
            CapabilityState.NATIVE_HANDOFF,
            "Ready",
        )
        card = NativeHandoffCard(
            NativeHandoffId.PLASMA_DISCOVER,
            title="Browse software",
            description="Open the complete catalogue.",
            button_text="Open Discover",
            service=service,
        )

        card.refresh_availability()

        self.assertTrue(card.open_button.isEnabled())
        self.assertEqual(card.status_label.text(), "Ready")
        self.assertEqual(card.property("capabilityState"), "native_handoff")

    @patch("ui.native_handoff_card.QProcess.startDetached", return_value=True)
    def test_click_prepares_then_launches_without_shell_or_pkexec(self, start_detached):
        service = MagicMock(spec=NativeHandoffService)
        service.prepare_launch.return_value = NativeHandoffLaunch(
            "/usr/bin/plasma-discover",
            (),
        )
        card = NativeHandoffCard(
            NativeHandoffId.PLASMA_DISCOVER,
            title="Browse software",
            description="Open the complete catalogue.",
            button_text="Open Discover",
            service=service,
        )
        card.open_button.setEnabled(True)

        card.open_button.click()

        service.prepare_launch.assert_called_once_with(
            NativeHandoffId.PLASMA_DISCOVER
        )
        start_detached.assert_called_once_with("/usr/bin/plasma-discover", [])

    @patch(
        "ui.native_handoff_card.QProcess.startDetached",
        return_value=(False, 0),
    )
    def test_failed_detached_tuple_is_reported(self, _start_detached):
        service = MagicMock(spec=NativeHandoffService)
        service.prepare_launch.return_value = NativeHandoffLaunch(
            "/usr/bin/plasma-discover",
            (),
        )
        card = NativeHandoffCard(
            NativeHandoffId.PLASMA_DISCOVER,
            title="Browse software",
            description="Open the complete catalogue.",
            button_text="Open Discover",
            service=service,
        )
        card.open_button.setEnabled(True)

        card.open_button.click()

        self.assertFalse(card.open_button.isEnabled())
        self.assertIn("could not be started", card.status_label.text())

    @patch("ui.native_handoff_card.QProcess.startDetached")
    def test_unavailable_click_never_launches(self, start_detached):
        target = NativeHandoffService.target(NativeHandoffId.PLASMA_DISPLAY)
        service = MagicMock(spec=NativeHandoffService)
        service.prepare_launch.return_value = None
        service.availability.return_value = NativeHandoffAvailability(
            target,
            CapabilityState.UNAVAILABLE,
            "Display module unavailable.",
        )
        card = NativeHandoffCard(
            NativeHandoffId.PLASMA_DISPLAY,
            title="Displays",
            description="Open display settings.",
            button_text="Open Displays",
            service=service,
        )
        card.open_button.setEnabled(True)

        card.open_button.click()

        start_detached.assert_not_called()
        self.assertFalse(card.open_button.isEnabled())
        self.assertEqual(card.status_label.text(), "Display module unavailable.")
