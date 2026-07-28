#!/usr/bin/env python3
"""Fail-closed COPR release-state decisions shared by publication workflows."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum


class GateState(Enum):
    """One terminal interpretation of the observed COPR release facts."""

    READY = "ready"
    PENDING = "pending"
    FAILED = "failed"


@dataclass(frozen=True)
class GateDecision:
    """Machine-readable decision and reader-facing reason."""

    state: GateState
    reason: str

    @property
    def passed(self) -> bool:
        return self.state is GateState.READY


def evaluate_build(status: str) -> GateDecision:
    """Require authoritative terminal COPR success."""
    normalized = str(status).strip().lower()
    if normalized == "succeeded":
        return GateDecision(GateState.READY, "COPR API reported succeeded")
    if normalized in {"failed", "canceled", "cancelled", "skipped"}:
        return GateDecision(GateState.FAILED, f"COPR API reported {normalized}")
    return GateDecision(
        GateState.PENDING,
        f"COPR API has not reached succeeded (status={normalized or 'unknown'})",
    )


def evaluate_install(
    *,
    installed: bool,
    expected_version: str,
    installed_version: str = "",
) -> GateDecision:
    """Require repository installation and exact installed-version readback."""
    if not installed:
        return GateDecision(
            GateState.PENDING,
            "COPR repository does not expose an installable package",
        )
    if installed_version != expected_version:
        return GateDecision(
            GateState.FAILED,
            f"installed version {installed_version or 'unknown'} does not match {expected_version}",
        )
    return GateDecision(
        GateState.READY,
        f"installed COPR package version matches {expected_version}",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--status", required=True)

    install = subparsers.add_parser("install")
    install.add_argument("--installed", choices=("0", "1"), required=True)
    install.add_argument("--expected-version", required=True)
    install.add_argument("--installed-version", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        decision = evaluate_build(args.status)
    else:
        decision = evaluate_install(
            installed=args.installed == "1",
            expected_version=args.expected_version,
            installed_version=args.installed_version,
        )
    print(f"{decision.state.value}: {decision.reason}")
    return 0 if decision.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

