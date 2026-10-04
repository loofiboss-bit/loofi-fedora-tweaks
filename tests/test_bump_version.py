"""Regression coverage for the active-only version management script."""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bump_version.py"


def _module(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("bump_version_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    source_dir = tmp_path / "loofi-fedora-tweaks"
    source_dir.mkdir()
    version_file = source_dir / "version.py"
    spec_file = tmp_path / "loofi-fedora-tweaks.spec"
    pyproject_file = tmp_path / "pyproject.toml"
    version_file.write_text('__version__ = "1.2.3"\n__version_codename__ = "Old"\n', encoding="utf-8")
    spec_file.write_text("Name: loofi-fedora-tweaks\nVersion: 1.2.3\n", encoding="utf-8")
    pyproject_file.write_text('[project]\nname = "loofi-fedora-tweaks"\nversion = "1.2.3"\n', encoding="utf-8")
    module.PROJECT_ROOT = tmp_path
    module.VERSION_FILE = version_file
    module.SPEC_FILE = spec_file
    module.PYPROJECT_FILE = pyproject_file
    return module, (version_file, spec_file, pyproject_file)


class TestVersionBump(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module, self.files = _module(self.root)
        self.original_argv = sys.argv
        self.addCleanup(setattr, sys, "argv", self.original_argv)

    def _run(self, args: list[str]) -> tuple[int, str]:
        sys.argv = ["bump_version.py", *args]
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.module.main()
        return result, output.getvalue()

    def test_check_only_requires_and_compares_active_version_sources(self) -> None:
        result, output = self._run(["--check"])

        self.assertEqual(result, 0)
        self.assertIn("[OK] version.py: 1.2.3", output)
        self.assertIn("[OK] spec: 1.2.3", output)
        self.assertIn("[OK] pyproject.toml: 1.2.3", output)
        self.assertFalse((self.root / ".workflow").exists())
        self.assertFalse((self.root / "scripts" / "project_stats.py").exists())
        self.assertFalse((self.root / "scripts" / "sync_ai_adapters.py").exists())

    def test_check_fails_when_active_versions_drift(self) -> None:
        _version_file, spec_file, _pyproject_file = self.files
        spec_file.write_text("Name: loofi-fedora-tweaks\nVersion: 1.2.4\n", encoding="utf-8")
        result, output = self._run(["--check"])

        self.assertEqual(result, 1)
        self.assertIn("[FAIL] spec: 1.2.4", output)

    def test_dry_run_updates_only_active_sources_and_does_not_scaffold_workflows(self) -> None:
        before = [path.read_bytes() for path in self.files]
        result, output = self._run(["1.2.4", "--codename", "New", "--dry-run"])

        self.assertEqual(result, 0)
        self.assertEqual([path.read_bytes() for path in self.files], before)
        self.assertIn("version.py: 1.2.4 (New)", output)
        self.assertIn("spec: 1.2.4", output)
        self.assertIn("pyproject.toml: 1.2.4", output)
        self.assertFalse((self.root / ".workflow").exists())

    def test_bump_updates_only_active_sources(self) -> None:
        result, _output = self._run(["1.2.4", "--codename", "New"])
        self.assertEqual(result, 0)

        version_text, spec_text, pyproject_text = [path.read_text(encoding="utf-8") for path in self.files]
        self.assertIn('__version__ = "1.2.4"', version_text)
        self.assertIn('__version_codename__ = "New"', version_text)
        self.assertIn("Version: 1.2.4", spec_text)
        self.assertIn('version = "1.2.4"', pyproject_text)
        self.assertFalse((self.root / ".workflow").exists())
