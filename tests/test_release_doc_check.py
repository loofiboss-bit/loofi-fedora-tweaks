"""Tests for scripts/check_release_docs.py."""

import importlib.util
import sys
from pathlib import Path


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_release_files(
    root: Path,
    *,
    use_legacy_root_notes: bool = False,
    include_pyproject: bool = True,
) -> None:
    version = "26.0.1"
    codename = "TestRelease"
    (root / "loofi-fedora-tweaks").mkdir(parents=True, exist_ok=True)
    (root / "loofi-fedora-tweaks" / "version.py").write_text(
        f'__version__ = "{version}"\n__version_codename__ = "{codename}"\n',
        encoding="utf-8",
    )
    (root / "loofi-fedora-tweaks.spec").write_text(
        f"Version:        {version}\n", encoding="utf-8"
    )
    if include_pyproject:
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "test"\nversion = "{version}"\n', encoding="utf-8"
        )
    (root / "CHANGELOG.md").write_text(
        f'## [{version}] - 2026-02-11 "{codename}"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        f"# Loofi v{version} \"{codename}\"\n"
        f"https://example.invalid/releases/tag/v{version}\n"
        "![Coverage](https://img.shields.io/badge/Coverage-85%25-brightgreen)\n",
        encoding="utf-8",
    )
    (root / "loofi-fedora-tweaks.metainfo.xml").write_text(
        f'<component><releases><release version="{version}" date="2026-02-11"><description><p>v{version} "{codename}"</p></description></release></releases></component>\n',
        encoding="utf-8",
    )
    (root / "ROADMAP.md").write_text(
        f'| v{version} | {codename} | ACTIVE | Test |\n'
        f'## [ACTIVE] v{version} "{codename}"\n',
        encoding="utf-8",
    )
    notes_root = root if use_legacy_root_notes else root / "docs" / "releases"
    notes_root.mkdir(parents=True, exist_ok=True)
    (notes_root / f"RELEASE-NOTES-v{version}.md").write_text(
        f'# Release Notes -- v{version} "{codename}"\n',
        encoding="utf-8",
    )
    specs = root / ".workflow" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / ".race-lock.json").write_text(
        f'{{"version": "v{version}", "target_version": "v{version}"}}\n',
        encoding="utf-8",
    )
    (specs / f"tasks-v{version}.md").write_text(f'# tasks v{version} "{codename}"\n', encoding="utf-8")
    (specs / f"arch-v{version}.md").write_text(f'# arch v{version} "{codename}"\n', encoding="utf-8")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    workflow_text = (
        'env:\n  COVERAGE_THRESHOLD: "85"\n'
        "jobs:\n  docs_gate:\n    steps:\n"
        "      - run: python3 scripts/check_release_docs.py\n"
    )
    (workflows / "ci.yml").write_text(workflow_text, encoding="utf-8")
    (workflows / "auto-release.yml").write_text(workflow_text, encoding="utf-8")
    (root / "Justfile").write_text('coverage_min := "85"\n', encoding="utf-8")
    # Empty tests dir (no stale tests)
    (root / "tests").mkdir(exist_ok=True)


def _set_module_paths(module, tmp_path: Path) -> None:
    """Point the module's file constants at the tmp_path fixture."""
    module.VERSION_FILE = tmp_path / "loofi-fedora-tweaks" / "version.py"
    module.SPEC_FILE = tmp_path / "loofi-fedora-tweaks.spec"
    module.PYPROJECT_FILE = tmp_path / "pyproject.toml"
    module.CHANGELOG_FILE = tmp_path / "CHANGELOG.md"
    module.README_FILE = tmp_path / "README.md"
    module.METAINFO_FILE = tmp_path / "loofi-fedora-tweaks.metainfo.xml"
    module.TESTS_DIR = tmp_path / "tests"
    module.ROADMAP_FILE = tmp_path / "ROADMAP.md"
    module.WORKFLOW_SPECS_DIR = tmp_path / ".workflow" / "specs"
    module.RACE_LOCK_FILE = tmp_path / ".workflow" / "specs" / ".race-lock.json"
    module.CI_WORKFLOW_FILE = tmp_path / ".github" / "workflows" / "ci.yml"
    module.AUTO_RELEASE_WORKFLOW_FILE = tmp_path / ".github" / "workflows" / "auto-release.yml"
    module.JUSTFILE = tmp_path / "Justfile"
    module.PLUGIN_LOADER_FILE = tmp_path / "loofi-fedora-tweaks" / "core" / "plugins" / "loader.py"


def test_release_doc_check_passes_when_required_files_exist(tmp_path):
    module = _load_module(
        "check_release_docs_test_ok", Path("scripts/check_release_docs.py")
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert issues == []


def test_release_doc_check_requires_release_notes(tmp_path):
    module = _load_module(
        "check_release_docs_test_missing", Path(
            "scripts/check_release_docs.py")
    )
    _write_release_files(tmp_path)
    (tmp_path / "docs" / "releases" / "RELEASE-NOTES-v26.0.1.md").unlink()
    _set_module_paths(module, tmp_path)

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("missing release notes" in item for item in issues)


def test_release_doc_check_supports_legacy_root_release_notes(tmp_path):
    module = _load_module(
        "check_release_docs_test_legacy_notes",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path, use_legacy_root_notes=True)
    _set_module_paths(module, tmp_path)

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert issues == []


def test_release_doc_check_require_logs_flags_missing_artifacts(tmp_path):
    module = _load_module(
        "check_release_docs_test_logs", Path("scripts/check_release_docs.py")
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)

    issues = module.validate_release_docs(tmp_path, require_logs=True)
    assert any("missing workflow run manifest" in item for item in issues)


def test_release_doc_check_require_logs_accepts_patch_tag_artifacts(tmp_path):
    module = _load_module(
        "check_release_docs_test_logs_patch_tag",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)

    reports = tmp_path / ".workflow" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "test-results-v26.0.1.json").write_text(
        (
            '{"status": "pass", "summary": '
            '{"total_tests": 12, "passed": 12, "failed": 0, "errors": 0}}'
        ),
        encoding="utf-8",
    )
    (reports / "run-manifest-v26.0.1.json").write_text(
        '{"phases": [{"phase": "plan", "status": "success"}]}',
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=True)
    assert issues == []


def test_release_doc_check_require_logs_rejects_zero_test_pass_report(tmp_path):
    module = _load_module(
        "check_release_docs_test_logs_zero_total",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)

    reports = tmp_path / ".workflow" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "test-results-v26.0.1.json").write_text(
        (
            '{"status": "pass", "summary": '
            '{"total_tests": 0, "passed": 0, "failed": 0, "errors": 0}}'
        ),
        encoding="utf-8",
    )
    (reports / "run-manifest-v26.0.1.json").write_text(
        '{"phases": [{"phase": "plan", "status": "success"}]}',
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=True)
    assert any("zero executed tests" in item for item in issues)


def test_release_doc_check_require_logs_rejects_short_tag_only_artifacts(tmp_path):
    module = _load_module(
        "check_release_docs_test_logs_short_tag",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)

    reports = tmp_path / ".workflow" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "test-results-v26.0.json").write_text(
        (
            '{"status": "pass", "summary": '
            '{"total_tests": 4, "passed": 4, "failed": 0, "errors": 0}}'
        ),
        encoding="utf-8",
    )
    (reports / "run-manifest-v26.0.json").write_text(
        '{"phases": [{"phase": "plan", "status": "success"}]}',
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=True)
    assert any("missing workflow test report" in item for item in issues)
    assert any("missing workflow run manifest" in item for item in issues)


def test_release_doc_check_catches_pyproject_version_mismatch(tmp_path):
    """pyproject.toml version != version.py should be flagged."""
    module = _load_module(
        "check_release_docs_test_pyproject",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    # Desync pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test"\nversion = "25.0.0"\n', encoding="utf-8"
    )
    _set_module_paths(module, tmp_path)

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("pyproject.toml" in item for item in issues)


def test_release_doc_check_passes_without_pyproject(tmp_path):
    """Missing pyproject.toml should not fail (graceful skip)."""
    module = _load_module(
        "check_release_docs_test_no_pyproject",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path, include_pyproject=False)
    _set_module_paths(module, tmp_path)

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert issues == []


def test_release_doc_check_catches_hardcoded_version_in_tests(tmp_path):
    """Test files with hardcoded assertEqual(__version__, 'X.Y.Z') should be flagged."""
    module = _load_module(
        "check_release_docs_test_stale",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)

    # Create a test file with a hardcoded version assertion
    (tmp_path / "tests" / "test_bad_version.py").write_text(
        'self.assertEqual(__version__, "26.0.1")  # stale!\n',
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("stale version assertion" in item for item in issues)
    assert any("test_bad_version.py" in item for item in issues)


def test_release_doc_check_catches_hardcoded_codename_in_tests(tmp_path):
    """Test files with hardcoded codename assertions should be flagged."""
    module = _load_module(
        "check_release_docs_test_stale_codename",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)

    # Create a test file with a hardcoded codename assertion
    (tmp_path / "tests" / "test_bad_codename.py").write_text(
        'self.assertEqual(__version_codename__, "TestRelease")  # stale!\n',
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("stale codename assertion" in item for item in issues)
    assert any("test_bad_codename.py" in item for item in issues)


def test_release_doc_check_allows_dynamic_version_tests(tmp_path):
    """Test files that use dynamic version checks should NOT be flagged."""
    module = _load_module(
        "check_release_docs_test_dynamic",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)

    # Create test files with dynamic (version-agnostic) assertions
    (tmp_path / "tests" / "test_good_version.py").write_text(
        "self.assertTrue(len(__version__) > 0)\n"
        'parts = __version__.split(".")\n'
        "self.assertEqual(len(parts), 3)\n",
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert issues == []


def test_release_doc_check_catches_readme_release_badge_drift(tmp_path):
    module = _load_module(
        "check_release_docs_test_readme_badge",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)
    (tmp_path / "README.md").write_text("missing current badge\n", encoding="utf-8")

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("README" in item for item in issues)


def test_release_doc_check_catches_coverage_threshold_mismatch(tmp_path):
    module = _load_module(
        "check_release_docs_test_threshold",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        'env:\n  COVERAGE_THRESHOLD: "77"\n'
        "jobs:\n  docs_gate:\n    steps:\n"
        "      - run: python3 scripts/check_release_docs.py\n",
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("coverage threshold" in item for item in issues)


def test_release_doc_check_catches_docs_only_ci_bypass(tmp_path):
    module = _load_module(
        "check_release_docs_test_docs_bypass",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        'on:\n  push:\n    paths-ignore:\n      - "docs/**"\n'
        'env:\n  COVERAGE_THRESHOLD: "85"\n'
        "jobs:\n  docs_gate:\n    steps:\n"
        "      - run: python3 scripts/check_release_docs.py\n",
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("docs-only" in item for item in issues)


def test_release_doc_check_requires_exactly_one_active_release(tmp_path):
    module = _load_module(
        "check_release_docs_test_one_active",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text(
        roadmap.read_text(encoding="utf-8")
        + '\n## [ACTIVE] v99.0.0 "Other"\n',
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("exactly one ACTIVE" in item for item in issues)


def test_release_doc_check_catches_current_tab_count_drift(tmp_path):
    module = _load_module(
        "check_release_docs_test_tab_count",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)
    module.PLUGIN_LOADER_FILE.parent.mkdir(parents=True, exist_ok=True)
    module.PLUGIN_LOADER_FILE.write_text(
        "_BUILTIN_PLUGINS = [\n    'a',\n    'b',\n    'c',\n]\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "Current app has 2 tabs.\n"
        "https://example.invalid/releases/tag/v26.0.1\n"
        "TestRelease\n",
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("current docs claim 2 tabs" in item for item in issues)


def test_release_doc_check_catches_non_blocking_rpm_import_check(tmp_path):
    module = _load_module(
        "check_release_docs_test_spec_import",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)
    (tmp_path / "loofi-fedora-tweaks.spec").write_text(
        'Version:        26.0.1\n%check\npython3 -c "import main" || :\n',
        encoding="utf-8",
    )

    issues = module.validate_release_docs(tmp_path, require_logs=False)
    assert any("RPM import check must be blocking" in item for item in issues)


def test_release_doc_check_requires_at_least_one_task_checkbox(tmp_path):
    module = _load_module(
        "check_release_docs_test_task_presence",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)

    issues = module.validate_release_docs(
        tmp_path,
        require_logs=False,
        require_completed_tasks=True,
    )

    assert any("has no task checkboxes" in item for item in issues)


def test_release_doc_check_rejects_unchecked_release_tasks(tmp_path):
    module = _load_module(
        "check_release_docs_test_incomplete_tasks",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)
    tasks_file = tmp_path / ".workflow" / "specs" / "tasks-v26.0.1.md"
    tasks_file.write_text(
        '# tasks v26.0.1 "TestRelease"\n\n- [x] Complete\n- [ ] Pending\n',
        encoding="utf-8",
    )

    issues = module.validate_release_docs(
        tmp_path,
        require_logs=False,
        require_completed_tasks=True,
    )

    assert any("incomplete workflow task" in item for item in issues)
    assert any("tasks-v26.0.1.md:4" in item for item in issues)


def test_release_doc_check_accepts_completed_release_tasks(tmp_path):
    module = _load_module(
        "check_release_docs_test_completed_tasks",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)
    tasks_file = tmp_path / ".workflow" / "specs" / "tasks-v26.0.1.md"
    tasks_file.write_text(
        '# tasks v26.0.1 "TestRelease"\n\n- [x] Complete\n* [X] Also complete\n',
        encoding="utf-8",
    )

    issues = module.validate_release_docs(
        tmp_path,
        require_logs=False,
        require_completed_tasks=True,
    )

    assert issues == []


def test_release_doc_check_allows_only_tagged_post_publish_task_before_release(tmp_path):
    module = _load_module(
        "check_release_docs_test_publish_ready_tasks",
        Path("scripts/check_release_docs.py"),
    )
    _write_release_files(tmp_path)
    _set_module_paths(module, tmp_path)
    tasks_file = tmp_path / ".workflow" / "specs" / "tasks-v26.0.1.md"
    tasks_file.write_text(
        '# tasks v26.0.1 "TestRelease"\n\n'
        '- [x] Pre-publication complete\n'
        '- [ ] [post-publish] Verify public readback\n',
        encoding="utf-8",
    )

    publish_issues = module.validate_release_docs(
        tmp_path,
        require_logs=False,
        require_publish_ready_tasks=True,
    )
    closure_issues = module.validate_release_docs(
        tmp_path,
        require_logs=False,
        require_completed_tasks=True,
    )

    assert publish_issues == []
    assert any("incomplete workflow task" in item for item in closure_issues)
