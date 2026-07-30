"""Tests for canonical documentation-to-wiki synchronization."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def _load_sync_module():
    path = Path("scripts/sync_wiki_docs.py")
    spec = importlib.util.spec_from_file_location("sync_wiki_docs_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestWikiDocsSync(unittest.TestCase):
    def setUp(self):
        self.module = _load_sync_module()

    def test_render_copies_canonical_bytes_and_check_passes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "guide.md"
            target = root / "wiki" / "Guide.md"
            source.parent.mkdir(parents=True)
            source.write_text("# Current guide\n", encoding="utf-8")

            with patch.object(self.module, "MIRRORS", {source: target}):
                self.module.render()
                self.assertEqual(self.module.drift(), [])
                self.assertEqual(target.read_bytes(), source.read_bytes())

    def test_check_reports_drift_without_modifying_target(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "docs" / "guide.md"
            target = root / "wiki" / "Guide.md"
            source.parent.mkdir(parents=True)
            target.parent.mkdir(parents=True)
            source.write_text("# Current guide\n", encoding="utf-8")
            target.write_text("# Stale guide\n", encoding="utf-8")

            with patch.object(self.module, "ROOT", root), patch.object(
                self.module,
                "MIRRORS",
                {source: target},
            ):
                issues = self.module.drift()

            self.assertEqual(target.read_text(encoding="utf-8"), "# Stale guide\n")
            self.assertEqual(len(issues), 1)
            self.assertIn("differs from", issues[0])
