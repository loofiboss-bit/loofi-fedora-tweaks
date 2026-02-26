"""Tests for scripts/generate_workflow_reports.py compatibility checks."""

import importlib.util
import sys
from pathlib import Path


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
