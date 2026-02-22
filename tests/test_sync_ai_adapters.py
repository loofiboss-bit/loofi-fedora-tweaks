"""Tests for scripts/sync_ai_adapters.py helper functions."""

import importlib.util
import json
import sys
from pathlib import Path


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_sync_file_detects_drift_and_writes(tmp_path):
    module = _load_module("sync_ai_adapters_test", Path("scripts/sync_ai_adapters.py"))

    source = tmp_path / "source.md"
    target = tmp_path / "target.md"
    source.write_text("canonical\n", encoding="utf-8")
    target.write_text("stale\n", encoding="utf-8")

    mapping = module.FileMapping(source=source, target=target)
    diffs: list[str] = []

    module.sync_file(mapping, check=False, diffs=diffs)

    assert diffs
    assert target.read_text(encoding="utf-8") == "canonical\n"


def test_sync_directory_detects_stale_files_in_check_mode(tmp_path):
    module = _load_module("sync_ai_adapters_dir_test", Path("scripts/sync_ai_adapters.py"))

    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()

    (source_dir / "a.md").write_text("a\n", encoding="utf-8")
    (target_dir / "a.md").write_text("a\n", encoding="utf-8")
    (target_dir / "obsolete.md").write_text("old\n", encoding="utf-8")

    mapping = module.DirMapping(source=source_dir, target=target_dir)
    diffs: list[str] = []

    module.sync_directory(mapping, check=True, diffs=diffs)

    assert any("stale adapter file" in item for item in diffs)
    assert (target_dir / "obsolete.md").exists()


def test_refresh_rendered_stats_replaces_old_values(tmp_path):
    module = _load_module("sync_ai_adapters_refresh_test", Path("scripts/sync_ai_adapters.py"))

    stats_file = tmp_path / ".project-stats.json"
    prev_file = tmp_path / ".project-stats.prev.json"
    renderable = tmp_path / "agent.md"

    stats_file.write_text(
        json.dumps({"version": "2.1.0", "coverage": "81", "tab_count": 30}),
        encoding="utf-8",
    )
    prev_file.write_text(
        json.dumps({"version": "2.0.0", "coverage": "80", "tab_count": 28}),
        encoding="utf-8",
    )
    renderable.write_text(
        'Current release is v2.0.0 and has 28 tabs with 80% coverage.\n',
        encoding="utf-8",
    )

    module.STATS_FILE = stats_file
    module.PREV_STATS_FILE = prev_file
    module.ROOT = tmp_path
    module.RENDERABLE_FILES = ["agent.md"]

    diffs = module.refresh_rendered_stats(check=False)

    assert diffs
    updated = renderable.read_text(encoding="utf-8")
    assert "v2.1.0" in updated
    assert "30 tabs" in updated
    assert "81% coverage" in updated
    assert "v2.0.0" not in updated


def test_refresh_rendered_stats_check_mode_does_not_write(tmp_path):
    module = _load_module(
        "sync_ai_adapters_refresh_check_test", Path("scripts/sync_ai_adapters.py")
    )

    stats_file = tmp_path / ".project-stats.json"
    prev_file = tmp_path / ".project-stats.prev.json"
    renderable = tmp_path / "agent.md"

    stats_file.write_text(json.dumps({"version": "2.1.0"}), encoding="utf-8")
    prev_file.write_text(json.dumps({"version": "2.0.0"}), encoding="utf-8")
    original = "Current release is v2.0.0.\n"
    renderable.write_text(original, encoding="utf-8")

    module.STATS_FILE = stats_file
    module.PREV_STATS_FILE = prev_file
    module.ROOT = tmp_path
    module.RENDERABLE_FILES = ["agent.md"]

    diffs = module.refresh_rendered_stats(check=True)

    assert diffs
    assert renderable.read_text(encoding="utf-8") == original


def test_refresh_rendered_stats_missing_prev_file_reports_skip(tmp_path):
    module = _load_module(
        "sync_ai_adapters_refresh_missing_prev_test",
        Path("scripts/sync_ai_adapters.py"),
    )

    module.PREV_STATS_FILE = tmp_path / ".project-stats.prev.json"

    diffs = module.refresh_rendered_stats(check=True)

    assert diffs == ["refresh: no .project-stats.prev.json — skipping (first run?)"]
