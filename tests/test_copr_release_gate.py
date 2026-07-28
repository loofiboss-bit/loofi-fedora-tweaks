"""Executable state-machine coverage for fail-closed COPR publication."""

from __future__ import annotations

import unittest

from scripts.copr_release_gate import GateState, evaluate_build, evaluate_install, main


class TestCoprReleaseGate(unittest.TestCase):
    def test_only_authoritative_succeeded_build_is_ready(self) -> None:
        self.assertEqual(evaluate_build("succeeded").state, GateState.READY)
        for status in ("running", "pending", "failed", "canceled", "unknown"):
            with self.subTest(status=status):
                self.assertNotEqual(evaluate_build(status).state, GateState.READY)

    def test_visible_artifacts_cannot_replace_repository_install(self) -> None:
        decision = evaluate_install(
            installed=False,
            expected_version="22.0.0",
        )
        self.assertEqual(decision.state, GateState.PENDING)

    def test_exact_installed_version_is_required(self) -> None:
        mismatch = evaluate_install(
            installed=True,
            expected_version="22.0.0",
            installed_version="21.0.0",
        )
        ready = evaluate_install(
            installed=True,
            expected_version="22.0.0",
            installed_version="22.0.0",
        )
        self.assertEqual(mismatch.state, GateState.FAILED)
        self.assertEqual(ready.state, GateState.READY)

    def test_cli_is_fail_closed(self) -> None:
        self.assertEqual(main(["build", "--status", "succeeded"]), 0)
        self.assertEqual(main(["build", "--status", "running"]), 1)
        self.assertEqual(
            main(
                [
                    "install",
                    "--installed",
                    "1",
                    "--expected-version",
                    "22.0.0",
                    "--installed-version",
                    "22.0.0",
                ]
            ),
            0,
        )
        self.assertEqual(
            main(
                [
                    "install",
                    "--installed",
                    "0",
                    "--expected-version",
                    "22.0.0",
                ]
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()

