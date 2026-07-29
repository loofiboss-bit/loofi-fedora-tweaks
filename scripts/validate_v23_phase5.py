#!/usr/bin/env python3
"""Validate Compass profile budgets and Home startup qualification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "loofi-fedora-tweaks"
DEFAULT_BASELINE = ROOT / "docs" / "reports" / "V23_PHASE0_STARTUP.json"
DEFAULT_CANDIDATE = ROOT / "docs" / "reports" / "V23_PHASE5_STARTUP.json"
DEFAULT_TRADITIONAL = ROOT / "docs" / "reports" / "V23_PHASE5_TRADITIONAL_PROFILES.json"
DEFAULT_ATSPI = ROOT / "docs" / "reports" / "V23_PHASE5_ATSPI.json"
DEFAULT_CODEQL = ROOT / "docs" / "reports" / "V23_PHASE5_CODEQL.json"
STARTUP_MULTIPLIER = 1.10
MINIMUM_RUNS = 10
CODEQL_EXCLUDED_PARTS = frozenset(
    {
        ".flatpak-builder",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
    }
)

if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from core.troubleshooting.profiles import all_profiles  # noqa: E402


EXPECTED_PROFILE_BUDGETS: Mapping[str, Mapping[str, Any]] = {
    "system_slow": {
        "total": 62.0,
        "sources": {
            "system-check": (45.0, True, ("atomic", "traditional")),
            "observability": (2.0, True, ("atomic", "traditional")),
            "change-journal": (15.0, True, ("atomic", "traditional")),
        },
    },
    "updates_failed": {
        "total": 65.0,
        "sources": {
            "package-health": (20.0, True, ("traditional",)),
            "deployment-state": (20.0, True, ("atomic",)),
            "pending-reboot": (20.0, True, ("atomic", "traditional")),
            "change-journal": (15.0, True, ("atomic", "traditional")),
            "action-center": (10.0, True, ("atomic", "traditional")),
        },
    },
    "application_failed": {
        "total": 35.0,
        "sources": {
            "application-inventory": (20.0, True, ("atomic", "traditional")),
            "change-journal": (15.0, True, ("atomic", "traditional")),
        },
    },
    "network_problem": {
        "total": 25.0,
        "sources": {
            "network-state": (5.0, True, ("atomic", "traditional")),
            "dns-state": (5.0, True, ("atomic", "traditional")),
            "change-journal": (15.0, False, ("atomic", "traditional")),
        },
    },
    "storage_pressure": {
        "total": 85.0,
        "sources": {
            "system-check": (45.0, True, ("atomic", "traditional")),
            "storage-reclaim": (25.0, True, ("atomic", "traditional")),
            "change-journal": (15.0, True, ("atomic", "traditional")),
        },
    },
    "boot_or_deployment": {
        "total": 75.0,
        "sources": {
            "boot-analysis": (30.0, True, ("atomic", "traditional")),
            "failed-services": (10.0, True, ("atomic", "traditional")),
            "pending-reboot": (20.0, True, ("atomic", "traditional")),
            "deployment-history": (15.0, True, ("atomic",)),
            "package-history": (15.0, True, ("traditional",)),
        },
    },
}


def _read_json(path: Path, *, label: str) -> tuple[dict[str, Any], list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"{label} evidence is unreadable: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"{label} evidence must be a JSON object"]
    return payload, []


def validate_profile_budgets() -> tuple[dict[str, Any], list[str]]:
    """Validate the complete closed catalog against explicit Phase 5 budgets."""
    errors: list[str] = []
    profiles = {profile.id: profile for profile in all_profiles()}
    if set(profiles) != set(EXPECTED_PROFILE_BUDGETS):
        errors.append("troubleshooting profile catalog differs from the six locked profiles")

    records: dict[str, Any] = {}
    for profile_id, expected in EXPECTED_PROFILE_BUDGETS.items():
        profile = profiles.get(profile_id)
        if profile is None:
            continue
        sources = {
            budget.source_id: (
                budget.timeout_seconds,
                budget.required,
                tuple(sorted(budget.variants)),
            )
            for budget in profile.source_budgets
        }
        if profile.total_budget_seconds != expected["total"]:
            errors.append(f"{profile_id} total budget differs from the locked value")
        if sources != expected["sources"]:
            errors.append(f"{profile_id} source budgets differ from the locked values")

        variant_totals = {
            variant: sum(
                budget.timeout_seconds
                for budget in profile.source_budgets
                if variant in budget.variants
            )
            for variant in ("traditional", "atomic")
        }
        if any(total != profile.total_budget_seconds for total in variant_totals.values()):
            errors.append(f"{profile_id} variant totals differ from its declared total")
        records[profile_id] = {
            "total_budget_seconds": profile.total_budget_seconds,
            "variant_totals_seconds": variant_totals,
            "source_count": len(profile.source_budgets),
        }
    return records, errors


def validate_startup_evidence(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Validate the candidate startup median, RSS, and cold-start invariants."""
    errors: list[str] = []
    for label, payload in (("baseline", baseline), ("candidate", candidate)):
        if payload.get("schema_version") != 1:
            errors.append(f"{label} startup evidence has an unsupported schema")
        marker = payload.get("method", {}).get("marker")
        if marker != "AtlasDashboardTab realized":
            errors.append(f"{label} startup evidence uses an unexpected marker")

    try:
        baseline_home = float(
            baseline["summary"]["milestones_ms"]["meaningful_home"]["median"]
        )
        candidate_home = float(
            candidate["summary"]["milestones_ms"]["meaningful_home"]["median"]
        )
        baseline_rss = float(baseline["summary"]["rss_kib"]["median"])
        candidate_rss = float(candidate["summary"]["rss_kib"]["median"])
    except (KeyError, TypeError, ValueError):
        return {}, errors + ["startup evidence lacks required median or RSS values"]

    home_ceiling = round(baseline_home * STARTUP_MULTIPLIER, 3)
    rss_ceiling = round(baseline_rss * STARTUP_MULTIPLIER, 3)
    if candidate_home > home_ceiling:
        errors.append(
            f"meaningful Home median {candidate_home:.3f} ms exceeds "
            f"{home_ceiling:.3f} ms"
        )
    if candidate_rss > rss_ceiling:
        errors.append(
            f"Home RSS median {candidate_rss:.0f} KiB exceeds "
            f"{rss_ceiling:.0f} KiB"
        )

    runs = candidate.get("runs")
    if not isinstance(runs, list) or len(runs) < MINIMUM_RUNS:
        errors.append(f"candidate startup evidence requires at least {MINIMUM_RUNS} runs")
        runs = []
    for index, run in enumerate(runs, start=1):
        if not isinstance(run, Mapping):
            errors.append(f"startup run {index} is not an object")
            continue
        if run.get("runtime_plugin_ids") != ["atlas_dashboard"]:
            errors.append(f"startup run {index} does not realize exactly one Home provider")
        if run.get("active_timer_intervals_ms") != []:
            errors.append(f"startup run {index} owns an active timer")
        if run.get("running_qthreads") != 0:
            errors.append(f"startup run {index} owns a running QThread")
        if run.get("subprocess_probes") != []:
            errors.append(f"startup run {index} performs a subprocess probe")
        if run.get("system_check_runtime_imports") != []:
            errors.append(f"startup run {index} eagerly imports System Check runtime code")

    return {
        "meaningful_home_median_ms": candidate_home,
        "meaningful_home_ceiling_ms": home_ceiling,
        "rss_median_kib": int(candidate_rss),
        "rss_ceiling_kib": int(rss_ceiling),
        "measured_runs": len(runs),
        "startup_multiplier": STARTUP_MULTIPLIER,
    }, errors


def _codeql_input_files() -> tuple[Path, ...]:
    """Return the exact local Python and Actions inputs covered by CodeQL."""
    inputs = {
        path
        for path in ROOT.rglob("*.py")
        if not CODEQL_EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
    }
    workflow_root = ROOT / ".github" / "workflows"
    for pattern in ("*.yml", "*.yaml"):
        inputs.update(workflow_root.glob(pattern))
    return tuple(sorted(inputs, key=lambda path: path.relative_to(ROOT).as_posix()))


def codeql_input_snapshot() -> dict[str, Any]:
    """Hash paths and bytes so retained CodeQL evidence cannot drift silently."""
    digest = hashlib.sha256()
    python_files = 0
    actions_files = 0
    for path in _codeql_input_files():
        relative = path.relative_to(ROOT).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        if path.suffix == ".py":
            python_files += 1
        else:
            actions_files += 1
    return {
        "sha256": digest.hexdigest(),
        "python_files": python_files,
        "actions_files": actions_files,
    }


def validate_traditional_evidence(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Validate fresh physical Traditional CLI coverage for all six profiles."""
    errors: list[str] = []
    if payload.get("schema_version") != 1 or payload.get("phase") != 5:
        errors.append("Traditional profile evidence has an unsupported schema")
    if payload.get("status") != "passed" or payload.get("errors") != []:
        errors.append("Traditional profile evidence is not a passed result")

    host = payload.get("host")
    if not isinstance(host, Mapping):
        errors.append("Traditional profile evidence lacks host identity")
        host = {}
    expected_host = {
        "os_id": "fedora",
        "version_id": "44",
        "variant_id": "kde",
        "session_type": "wayland",
        "package_model": "traditional",
        "virtualization": "none",
    }
    if any(host.get(key) != value for key, value in expected_host.items()):
        errors.append("Traditional host identity differs from physical Fedora 44 KDE")

    policy = payload.get("capture_policy")
    if not isinstance(policy, Mapping):
        errors.append("Traditional profile evidence lacks its capture policy")
        policy = {}
    for field in (
        "explicit_cli_collection",
        "isolated_xdg_state",
    ):
        if policy.get(field) is not True:
            errors.append(f"Traditional capture policy does not prove {field}")
    if policy.get("mutating_actions") is not False:
        errors.append("Traditional capture policy permits mutation")
    if policy.get("raw_cli_payloads_retained") is not False:
        errors.append("Traditional capture retained raw CLI payloads")

    records = payload.get("profiles")
    if not isinstance(records, list):
        errors.append("Traditional profile evidence lacks profile records")
        records = []
    actual_ids = tuple(
        record.get("profile_id")
        for record in records
        if isinstance(record, Mapping)
    )
    if actual_ids != tuple(EXPECTED_PROFILE_BUDGETS):
        errors.append("Traditional evidence does not cover the closed catalog in order")

    for record in records:
        if not isinstance(record, Mapping):
            errors.append("Traditional evidence contains a malformed record")
            continue
        profile_id = str(record.get("profile_id", ""))
        expected = EXPECTED_PROFILE_BUDGETS.get(profile_id)
        if expected is None:
            continue
        expected_sources = tuple(
            sorted(
                source_id
                for source_id, (_timeout, _required, variants) in expected[
                    "sources"
                ].items()
                if "traditional" in variants
            )
        )
        if record.get("variant") != "traditional":
            errors.append(f"{profile_id} lost Traditional identity")
        if record.get("state") not in {"completed", "partial"}:
            errors.append(f"{profile_id} is not in a truthful terminal state")
        if tuple(record.get("source_ids", [])) != expected_sources:
            errors.append(f"{profile_id} source projection drifted")
        if record.get("budget_seconds") != expected["total"]:
            errors.append(f"{profile_id} evidence uses the wrong total budget")
        try:
            elapsed = float(record["elapsed_seconds"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{profile_id} evidence lacks elapsed time")
        else:
            if elapsed < 0 or elapsed > float(expected["total"]) + 1.0:
                errors.append(f"{profile_id} exceeded its bounded run budget")

    return {
        "host": dict(host),
        "profile_count": len(records),
        "source_identity": payload.get("source_identity", ""),
    }, errors


def validate_atspi_evidence(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Validate summary-only live Wayland AT-SPI exposure evidence."""
    errors: list[str] = []
    if payload.get("schema_version") != 1 or payload.get("phase") != 5:
        errors.append("AT-SPI evidence has an unsupported schema")
    if payload.get("status") != "passed" or payload.get("errors") != []:
        errors.append("AT-SPI evidence is not a passed result")
    for field, expected in (
        ("backend", "wayland"),
        ("protocol", "AT-SPI2"),
        ("real_main_window", True),
        ("bus_address_resolved", True),
        ("orca_available", True),
        ("nodes_retained", False),
    ):
        if payload.get(field) != expected:
            errors.append(f"AT-SPI evidence does not prove {field}={expected!r}")
    if payload.get("nodes") != []:
        errors.append("AT-SPI evidence retained raw accessibility nodes")

    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, Mapping):
        errors.append("AT-SPI evidence lacks surface results")
        surfaces = {}
    expected_surfaces = {
        "application",
        "confirmation",
        "navigation",
        "page_title",
        "result_state",
        "troubleshoot_profile",
        "troubleshoot_start",
        "troubleshoot_view",
    }
    if set(surfaces) != expected_surfaces:
        errors.append("AT-SPI evidence surface catalog drifted")
    for surface_id, record in surfaces.items():
        if not isinstance(record, Mapping) or record.get("status") != "passed":
            errors.append(f"AT-SPI surface {surface_id} did not pass")

    return {
        "backend": payload.get("backend", ""),
        "protocol": payload.get("protocol", ""),
        "surface_count": len(surfaces),
        "node_count": payload.get("node_count", 0),
    }, errors


def validate_codeql_evidence(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Validate exact-input local CodeQL security-extended evidence."""
    errors: list[str] = []
    if payload.get("schema_version") != 1 or payload.get("phase") != 5:
        errors.append("CodeQL evidence has an unsupported schema")
    if payload.get("status") != "passed":
        errors.append("CodeQL evidence is not a passed result")

    tool = payload.get("tool")
    if not isinstance(tool, Mapping):
        errors.append("CodeQL evidence lacks tool identity")
        tool = {}
    if tool.get("name") != "CodeQL CLI" or tool.get("version") != "2.25.5":
        errors.append("CodeQL evidence uses an unexpected tool version")
    if tool.get("bundle_sha256") != (
        "76cd9d785940da0a5876676136be0c2803baa116304af5265052b74f1ec46258"
    ):
        errors.append("CodeQL bundle checksum differs from the verified bundle")

    suite = payload.get("query_suite")
    if not isinstance(suite, Mapping):
        errors.append("CodeQL evidence lacks query-suite identity")
        suite = {}
    if suite.get("name") != "python-security-extended.qls":
        errors.append("CodeQL evidence did not run security-extended")
    if suite.get("resolved_queries") != 52:
        errors.append("CodeQL evidence resolved an unexpected query count")

    current_snapshot = codeql_input_snapshot()
    snapshot = payload.get("input_snapshot")
    if not isinstance(snapshot, Mapping):
        errors.append("CodeQL evidence lacks its input snapshot")
        snapshot = {}
    if dict(snapshot) != current_snapshot:
        errors.append("CodeQL input snapshot differs from the current worktree")

    coverage = payload.get("scan_coverage")
    if not isinstance(coverage, Mapping):
        errors.append("CodeQL evidence lacks scan coverage")
        coverage = {}
    expected_coverage = {
        "python_files_scanned": current_snapshot["python_files"],
        "python_files_total": current_snapshot["python_files"],
        "actions_files_scanned": current_snapshot["actions_files"],
        "actions_files_total": current_snapshot["actions_files"],
    }
    if dict(coverage) != expected_coverage:
        errors.append("CodeQL scan coverage differs from the exact input snapshot")

    findings = payload.get("findings")
    if not isinstance(findings, Mapping):
        errors.append("CodeQL evidence lacks finding disposition")
        findings = {}
    expected_counts = {
        "raw": 4,
        "source_suppressed": 4,
        "effective": 0,
        "effective_high_or_critical": 0,
    }
    if any(findings.get(key) != value for key, value in expected_counts.items()):
        errors.append("CodeQL finding counts do not prove a clean effective gate")
    suppressions = findings.get("source_suppressions")
    if not isinstance(suppressions, list):
        errors.append("CodeQL evidence lacks source-suppression records")
        suppressions = []
    suppression_counts = {
        str(record.get("rule_id")): record.get("count")
        for record in suppressions
        if isinstance(record, Mapping)
    }
    if suppression_counts != {
        "py/clear-text-logging-sensitive-data": 2,
        "py/path-injection": 2,
    }:
        errors.append("CodeQL source suppressions differ from reviewed dispositions")
    if payload.get("alert_suppression_query_matches_all_raw_alerts") is not True:
        errors.append("CodeQL suppression query did not match every raw alert")

    return {
        "input_snapshot": current_snapshot,
        "raw_findings": findings.get("raw", 0),
        "effective_findings": findings.get("effective", 0),
        "resolved_queries": suite.get("resolved_queries", 0),
    }, errors


def run_validation(
    baseline_path: Path = DEFAULT_BASELINE,
    candidate_path: Path = DEFAULT_CANDIDATE,
    traditional_path: Path = DEFAULT_TRADITIONAL,
    atspi_path: Path = DEFAULT_ATSPI,
    codeql_path: Path = DEFAULT_CODEQL,
) -> dict[str, Any]:
    """Return one machine-readable Phase 5 local qualification result."""
    baseline, baseline_errors = _read_json(baseline_path, label="baseline")
    candidate, candidate_errors = _read_json(candidate_path, label="candidate")
    traditional_payload, traditional_read_errors = _read_json(
        traditional_path,
        label="Traditional profile",
    )
    atspi_payload, atspi_read_errors = _read_json(atspi_path, label="AT-SPI")
    codeql_payload, codeql_read_errors = _read_json(codeql_path, label="CodeQL")
    profiles, profile_errors = validate_profile_budgets()
    startup: dict[str, Any] = {}
    startup_errors: list[str] = []
    if baseline and candidate:
        startup, startup_errors = validate_startup_evidence(baseline, candidate)
    traditional: dict[str, Any] = {}
    traditional_errors: list[str] = []
    if traditional_payload:
        traditional, traditional_errors = validate_traditional_evidence(
            traditional_payload
        )
    atspi: dict[str, Any] = {}
    atspi_errors: list[str] = []
    if atspi_payload:
        atspi, atspi_errors = validate_atspi_evidence(atspi_payload)
    codeql: dict[str, Any] = {}
    codeql_errors: list[str] = []
    if codeql_payload:
        codeql, codeql_errors = validate_codeql_evidence(codeql_payload)
    errors = (
        baseline_errors
        + candidate_errors
        + traditional_read_errors
        + atspi_read_errors
        + codeql_read_errors
        + profile_errors
        + startup_errors
        + traditional_errors
        + atspi_errors
        + codeql_errors
    )
    return {
        "schema_version": 1,
        "release": "v23.0.0 Compass",
        "product_metadata": "v22.0.0 Alignment",
        "profiles": profiles,
        "startup": startup,
        "traditional": traditional,
        "atspi": atspi,
        "codeql": codeql,
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--traditional", type=Path, default=DEFAULT_TRADITIONAL)
    parser.add_argument("--atspi", type=Path, default=DEFAULT_ATSPI)
    parser.add_argument("--codeql", type=Path, default=DEFAULT_CODEQL)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_validation(
        args.baseline,
        args.candidate,
        args.traditional,
        args.atspi,
        args.codeql,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"[v23-phase5] {payload['status'].upper()}")
        startup = payload["startup"]
        if startup:
            print(
                "- meaningful Home: "
                f"{startup['meaningful_home_median_ms']:.3f} ms / "
                f"{startup['meaningful_home_ceiling_ms']:.3f} ms"
            )
            print(
                "- RSS: "
                f"{startup['rss_median_kib']} KiB / "
                f"{startup['rss_ceiling_kib']} KiB"
            )
        print(f"- Traditional profiles: {payload['traditional'].get('profile_count', 0)}")
        print(f"- live AT-SPI surfaces: {payload['atspi'].get('surface_count', 0)}")
        print(
            "- effective CodeQL findings: "
            f"{payload['codeql'].get('effective_findings', 0)}"
        )
        for error in payload["errors"]:
            print(f"[v23-phase5] ERROR: {error}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
