"""Tests for release-scoped project statistics generation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _module():
    return _load_module(
        "project_stats_quality_gate",
        Path("scripts/project_stats.py"),
    )


def test_report_readers_use_only_the_current_release(tmp_path: Path):
    module = _module()
    current_version = module.read_version()["version"]
    reports = tmp_path / ".workflow" / "reports"
    reports.mkdir(parents=True)
    module.ROOT = tmp_path

    (reports / "test-results-v18.0.0.json").write_text(
        json.dumps({"test_count": 6864, "coverage_percent": 86.24}),
        encoding="utf-8",
    )
    (reports / f"test-results-v{current_version}.json").write_text(
        json.dumps(
            {
                "version": "v27.0.0",
                "summary": {"total_tests": 5019},
                "coverage_percent": 90.12,
            }
        ),
        encoding="utf-8",
    )

    assert module.read_test_count_from_reports(current_version) == "5019"
    assert module.read_coverage_from_reports(current_version) == "90.12"
    assert module.read_test_count_from_reports("28.0.0") == "unverified"
    assert module.read_coverage_from_reports("28.0.0") == "unverified"


def test_malformed_current_report_is_unverified(tmp_path: Path):
    module = _module()
    current_version = module.read_version()["version"]
    reports = tmp_path / ".workflow" / "reports"
    reports.mkdir(parents=True)
    module.ROOT = tmp_path
    (reports / f"test-results-v{current_version}.json").write_text("{not json", encoding="utf-8")

    assert module.read_test_count_from_reports(current_version) == "unverified"
    assert module.read_coverage_from_reports(current_version) == "unverified"


def test_markdown_does_not_turn_unverified_coverage_into_a_claim(tmp_path: Path):
    module = _module()
    current_version = module.read_version()["version"]
    output = tmp_path / ".project-stats.md"
    module.STATS_MD = output

    module.write_stats_markdown(
        {
            "version": current_version,
            "codename": "Core",
            "framework": "PyQt6",
            "python_version": "3.12",
            "tab_count": 0,
            "test_file_count": 0,
            "test_count": "unverified",
            "coverage": "unverified",
            "utils_module_count": 0,
            "active_version": "27.0.0",
            "pipeline_version": "v27.0.0",
            "pipeline_status": "active",
            "tab_names": [],
        }
    )

    text = output.read_text(encoding="utf-8")
    assert "| Coverage | unverified |" in text
    assert "unverified%" not in text
    assert "| Test Count | unverified |" in text
    assert "unverified+" not in text
