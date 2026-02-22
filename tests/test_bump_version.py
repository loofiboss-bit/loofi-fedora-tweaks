"""Tests for scripts/bump_version.py cascade helpers."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@patch("subprocess.run")
def test_regenerate_stats_runs_save_prev_then_stats(mock_run, tmp_path):
    module = _load_module("bump_version_test", Path("scripts/bump_version.py"))

    stats_script = tmp_path / "project_stats.py"
    sync_script = tmp_path / "sync_ai_adapters.py"
    stats_script.write_text("# stats\n", encoding="utf-8")
    sync_script.write_text("# sync\n", encoding="utf-8")

    setattr(module, "PROJECT_ROOT", tmp_path)
    setattr(module, "STATS_SCRIPT", stats_script)
    setattr(module, "SYNC_SCRIPT", sync_script)

    mock_run.return_value = MagicMock(returncode=0)

    result = module.regenerate_stats(dry_run=False)

    assert result == ["  stats: regenerated .project-stats.json"]
    assert len(mock_run.call_args_list) == 2

    first_cmd = mock_run.call_args_list[0].args[0]
    second_cmd = mock_run.call_args_list[1].args[0]

    assert first_cmd == [sys.executable, str(sync_script), "--save-prev"]
    assert second_cmd == [sys.executable, str(stats_script)]


@patch("subprocess.run")
def test_regenerate_stats_continues_when_save_prev_fails(mock_run, tmp_path):
    module = _load_module("bump_version_save_prev_fail_test", Path("scripts/bump_version.py"))

    stats_script = tmp_path / "project_stats.py"
    sync_script = tmp_path / "sync_ai_adapters.py"
    stats_script.write_text("# stats\n", encoding="utf-8")
    sync_script.write_text("# sync\n", encoding="utf-8")

    setattr(module, "PROJECT_ROOT", tmp_path)
    setattr(module, "STATS_SCRIPT", stats_script)
    setattr(module, "SYNC_SCRIPT", sync_script)

    mock_run.side_effect = [
        subprocess.CalledProcessError(returncode=1, cmd="save-prev"),
        MagicMock(returncode=0),
    ]

    result = module.regenerate_stats(dry_run=False)

    assert result == ["  stats: regenerated .project-stats.json"]
    assert len(mock_run.call_args_list) == 2


@patch("subprocess.run")
def test_render_templates_runs_render_then_refresh(mock_run, tmp_path):
    module = _load_module("bump_version_render_test", Path("scripts/bump_version.py"))

    sync_script = tmp_path / "sync_ai_adapters.py"
    sync_script.write_text("# sync\n", encoding="utf-8")

    setattr(module, "PROJECT_ROOT", tmp_path)
    setattr(module, "SYNC_SCRIPT", sync_script)

    mock_run.side_effect = [
        MagicMock(stdout="rendered 2 template(s) in A\n"),
        MagicMock(stdout="refreshed stats in A (4 lines changed)\n"),
    ]

    result = module.render_templates(dry_run=False)

    assert result == [
        "  templates: rendered (1 files)",
        "  templates: refreshed stats (1 files)",
    ]
    assert len(mock_run.call_args_list) == 2

    first_cmd = mock_run.call_args_list[0].args[0]
    second_cmd = mock_run.call_args_list[1].args[0]

    assert first_cmd == [sys.executable, str(sync_script), "--render"]
    assert second_cmd == [sys.executable, str(sync_script), "--refresh"]
