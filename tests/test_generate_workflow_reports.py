"""Tests for scripts/generate_workflow_reports.py compatibility checks."""

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_check_only_accepts_patch_tag_reports(tmp_path):
    module = _load_module(
        "generate_workflow_reports_patch_tag_test",
        Path("scripts/generate_workflow_reports.py"),
    )
    module.ROOT = tmp_path
    module.REPORTS_DIR = tmp_path / ".workflow" / "reports"
    module.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    (module.REPORTS_DIR / "test-results-v26.0.1.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (module.REPORTS_DIR / "run-manifest-v26.0.1.json").write_text(
        "{}",
        encoding="utf-8",
    )

    code = module.check_only("26.0.1")

    assert code == 0


def test_check_only_fails_when_reports_missing(tmp_path):
    module = _load_module(
        "generate_workflow_reports_missing_test",
        Path("scripts/generate_workflow_reports.py"),
    )
    module.ROOT = tmp_path
    module.REPORTS_DIR = tmp_path / ".workflow" / "reports"
    module.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    code = module.check_only("26.0.1")

    assert code == 1


def test_generate_test_results_fails_when_total_tests_is_zero(tmp_path):
    module = _load_module(
        "generate_workflow_reports_zero_total_test",
        Path("scripts/generate_workflow_reports.py"),
    )
    module.ROOT = tmp_path
    module.REPORTS_DIR = tmp_path / ".workflow" / "reports"

    payload = module.generate_test_results(
        "26.0.1",
        {
            "returncode": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "total": 0,
            "duration_seconds": 0.0,
            "summary_line": "no tests collected",
        },
    )

    assert payload["status"] == "fail"
    assert payload["release_gate"]["status"] == "FAIL"


def test_generate_test_results_passes_when_tests_executed_without_failures(tmp_path):
    module = _load_module(
        "generate_workflow_reports_nonzero_total_test",
        Path("scripts/generate_workflow_reports.py"),
    )
    module.ROOT = tmp_path
    module.REPORTS_DIR = tmp_path / ".workflow" / "reports"

    payload = module.generate_test_results(
        "26.0.1",
        {
            "returncode": 0,
            "passed": 10,
            "failed": 0,
            "skipped": 2,
            "errors": 0,
            "total": 12,
            "duration_seconds": 1.2,
            "summary_line": "10 passed, 2 skipped",
        },
    )

    assert payload["status"] == "pass"
    assert payload["release_gate"]["status"] == "PASS"


@pytest.mark.parametrize(
    ("module_name", "script", "reader"),
    (
        (
            "generate_workflow_reports_literal_version_test",
            "generate_workflow_reports.py",
            "extract_version",
        ),
        (
            "project_stats_literal_version_test",
            "project_stats.py",
            "read_version",
        ),
    ),
)
def test_version_readers_reject_expressions_without_executing_them(
    tmp_path,
    module_name,
    script,
    reader,
):
    module = _load_module(module_name, Path("scripts") / script)
    sentinel = tmp_path / "executed"
    version_file = tmp_path / "version.py"
    version_file.write_text(
        "__version__ = "
        f"(__import__('pathlib').Path({str(sentinel)!r}).write_text('unsafe') "
        "or '22.0.0')\n",
        encoding="utf-8",
    )
    module.VERSION_FILE = version_file

    with pytest.raises(ValueError, match="string literal"):
        getattr(module, reader)()

    assert not sentinel.exists()
