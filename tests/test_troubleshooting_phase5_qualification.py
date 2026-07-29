"""Compass Phase 5 budget, adversarial-input, and startup gates."""

from __future__ import annotations

import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

from core.troubleshooting.profiles import require_profile
from core.troubleshooting.validation import (
    MAX_MAPPING_ITEMS,
    MAX_SEQUENCE_ITEMS,
    freeze_mapping,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_v23_phase5.py"
SPEC = importlib.util.spec_from_file_location("validate_v23_phase5", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _startup_payload(*, home_ms=100.0, rss_kib=1000, runs=10):
    return {
        "schema_version": 1,
        "method": {"marker": "AtlasDashboardTab realized"},
        "summary": {
            "milestones_ms": {"meaningful_home": {"median": home_ms}},
            "rss_kib": {"median": rss_kib},
        },
        "runs": [
            {
                "runtime_plugin_ids": ["atlas_dashboard"],
                "active_timer_intervals_ms": [],
                "running_qthreads": 0,
                "subprocess_probes": [],
                "system_check_runtime_imports": [],
            }
            for _index in range(runs)
        ],
    }


def _traditional_payload():
    records = []
    for profile_id, expected in VALIDATOR.EXPECTED_PROFILE_BUDGETS.items():
        records.append(
            {
                "profile_id": profile_id,
                "variant": "traditional",
                "state": "completed",
                "elapsed_seconds": 0.5,
                "budget_seconds": expected["total"],
                "source_ids": sorted(
                    source_id
                    for source_id, (_timeout, _required, variants) in expected[
                        "sources"
                    ].items()
                    if "traditional" in variants
                ),
            }
        )
    return {
        "schema_version": 1,
        "phase": 5,
        "status": "passed",
        "errors": [],
        "source_identity": "WORKTREE@example",
        "host": {
            "os_id": "fedora",
            "version_id": "44",
            "variant_id": "kde",
            "session_type": "wayland",
            "package_model": "traditional",
            "virtualization": "none",
        },
        "capture_policy": {
            "explicit_cli_collection": True,
            "isolated_xdg_state": True,
            "mutating_actions": False,
            "raw_cli_payloads_retained": False,
        },
        "profiles": records,
    }


def _atspi_payload():
    surfaces = {
        surface_id: {"status": "passed"}
        for surface_id in (
            "application",
            "confirmation",
            "navigation",
            "page_title",
            "result_state",
            "troubleshoot_profile",
            "troubleshoot_start",
            "troubleshoot_view",
        )
    }
    return {
        "schema_version": 1,
        "phase": 5,
        "status": "passed",
        "errors": [],
        "backend": "wayland",
        "protocol": "AT-SPI2",
        "real_main_window": True,
        "bus_address_resolved": True,
        "orca_available": True,
        "nodes_retained": False,
        "nodes": [],
        "node_count": 100,
        "surfaces": surfaces,
    }


def _codeql_payload():
    snapshot = VALIDATOR.codeql_input_snapshot()
    return {
        "schema_version": 1,
        "phase": 5,
        "status": "passed",
        "tool": {
            "name": "CodeQL CLI",
            "version": "2.25.5",
            "bundle_sha256": (
                "76cd9d785940da0a5876676136be0c2803baa116304af5265052b74f1ec"
                "46258"
            ),
        },
        "query_suite": {
            "name": "python-security-extended.qls",
            "resolved_queries": 52,
        },
        "input_snapshot": snapshot,
        "scan_coverage": {
            "python_files_scanned": snapshot["python_files"],
            "python_files_total": snapshot["python_files"],
            "actions_files_scanned": snapshot["actions_files"],
            "actions_files_total": snapshot["actions_files"],
        },
        "findings": {
            "raw": 4,
            "source_suppressed": 4,
            "effective": 0,
            "effective_high_or_critical": 0,
            "source_suppressions": [
                {
                    "rule_id": "py/clear-text-logging-sensitive-data",
                    "count": 2,
                },
                {"rule_id": "py/path-injection", "count": 2},
            ],
        },
        "alert_suppression_query_matches_all_raw_alerts": True,
    }


class TestV23Phase5Qualification(unittest.TestCase):
    def test_all_six_profile_budgets_match_explicit_phase5_contract(self):
        records, errors = VALIDATOR.validate_profile_budgets()

        self.assertEqual(errors, [])
        self.assertEqual(set(records), set(VALIDATOR.EXPECTED_PROFILE_BUDGETS))
        for record in records.values():
            self.assertEqual(
                set(record["variant_totals_seconds"]),
                {"traditional", "atomic"},
            )
            self.assertTrue(
                all(
                    total == record["total_budget_seconds"]
                    for total in record["variant_totals_seconds"].values()
                )
            )

    def test_startup_gate_rejects_slow_rss_or_resource_ownership_regression(self):
        baseline = _startup_payload(home_ms=100.0, rss_kib=1000)
        candidate = _startup_payload(home_ms=110.001, rss_kib=1101)
        candidate["runs"][0]["runtime_plugin_ids"].append("diagnostics")
        candidate["runs"][1]["active_timer_intervals_ms"] = [1000]
        candidate["runs"][2]["running_qthreads"] = 1
        candidate["runs"][3]["subprocess_probes"] = [["uname"]]
        candidate["runs"][4]["system_check_runtime_imports"] = [
            "core.system_check.service"
        ]

        _summary, errors = VALIDATOR.validate_startup_evidence(
            baseline,
            candidate,
        )

        self.assertEqual(len(errors), 7)

    def test_startup_gate_accepts_exact_ceiling_and_ten_clean_runs(self):
        baseline = _startup_payload(home_ms=100.0, rss_kib=1000)
        candidate = _startup_payload(home_ms=110.0, rss_kib=1100)

        summary, errors = VALIDATOR.validate_startup_evidence(
            baseline,
            candidate,
        )

        self.assertEqual(errors, [])
        self.assertEqual(summary["measured_runs"], 10)

    def test_malicious_application_identifiers_fail_closed(self):
        profile = require_profile("application_failed")
        malicious = (
            "../firefox",
            "/usr/bin/firefox",
            "firefox;id",
            "firefox\nid",
            "firefox --safe-mode",
            "org.kde.kate/../../secret",
            "a" * 129,
        )

        for application_id in malicious:
            with self.subTest(application_id=application_id):
                with self.assertRaises(ValueError):
                    profile.validate_parameters(
                        {"application_id": application_id}
                    )

    def test_nested_authority_secret_and_raw_output_keys_fail_closed(self):
        malicious_keys = (
            "command",
            "command-vector",
            "auth.token",
            "raw_output",
            "callback",
            "renderer",
            "credential",
            "stderr",
        )

        for key in malicious_keys:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    freeze_mapping(
                        {"evidence": {"nested": {key: "unsafe"}}},
                        field="phase5 adversarial evidence",
                    )

    def test_oversized_and_overdeep_evidence_fails_closed(self):
        with self.assertRaises(ValueError):
            freeze_mapping(
                {
                    f"key-{index}": index
                    for index in range(MAX_MAPPING_ITEMS + 1)
                },
                field="phase5 adversarial evidence",
            )
        with self.assertRaises(ValueError):
            freeze_mapping(
                {"values": list(range(MAX_SEQUENCE_ITEMS + 1))},
                field="phase5 adversarial evidence",
            )
        with self.assertRaises(ValueError):
            freeze_mapping(
                {"a": {"b": {"c": {"d": {"e": "too deep"}}}}},
                field="phase5 adversarial evidence",
            )

    def test_candidate_evidence_is_not_allowed_to_drop_runs(self):
        baseline = _startup_payload()
        candidate = deepcopy(baseline)
        candidate["runs"] = candidate["runs"][:-1]

        _summary, errors = VALIDATOR.validate_startup_evidence(
            baseline,
            candidate,
        )

        self.assertIn(
            "candidate startup evidence requires at least 10 runs",
            errors,
        )

    def test_traditional_gate_requires_physical_host_and_exact_six_profiles(self):
        payload = _traditional_payload()

        summary, errors = VALIDATOR.validate_traditional_evidence(payload)

        self.assertEqual(errors, [])
        self.assertEqual(summary["profile_count"], 6)
        payload["host"]["virtualization"] = "kvm"
        payload["profiles"][0]["source_ids"] = []
        _summary, errors = VALIDATOR.validate_traditional_evidence(payload)
        self.assertEqual(len(errors), 2)

    def test_atspi_gate_requires_summary_only_live_wayland_surfaces(self):
        payload = _atspi_payload()

        summary, errors = VALIDATOR.validate_atspi_evidence(payload)

        self.assertEqual(errors, [])
        self.assertEqual(summary["surface_count"], 8)
        payload["nodes_retained"] = True
        payload["surfaces"]["troubleshoot_start"]["status"] = "failed"
        _summary, errors = VALIDATOR.validate_atspi_evidence(payload)
        self.assertEqual(len(errors), 2)

    def test_codeql_gate_binds_exact_inputs_and_effective_findings(self):
        payload = _codeql_payload()

        summary, errors = VALIDATOR.validate_codeql_evidence(payload)

        self.assertEqual(errors, [])
        self.assertEqual(summary["effective_findings"], 0)
        payload["input_snapshot"]["sha256"] = "0" * 64
        payload["findings"]["effective"] = 1
        _summary, errors = VALIDATOR.validate_codeql_evidence(payload)
        self.assertEqual(len(errors), 2)


if __name__ == "__main__":
    unittest.main()
