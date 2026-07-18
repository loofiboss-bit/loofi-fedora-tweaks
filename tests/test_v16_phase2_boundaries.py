"""Presentation, packaging, and structural style boundaries for Phase 2."""

from __future__ import annotations

import ast
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))


ROOT = Path(__file__).parents[1]
COMPONENT_ROOT = ROOT / "loofi-fedora-tweaks" / "ui" / "components"


class TestComponentBoundaries(unittest.TestCase):
    def test_component_layer_has_no_domain_or_execution_imports(self) -> None:
        forbidden_roots = {
            "core",
            "services",
            "subprocess",
            "utils",
        }
        violations = []
        for path in COMPONENT_ROOT.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = ""
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".", 1)[0] in forbidden_roots:
                            violations.append(f"{path.name}:{node.lineno}:{alias.name}")
                    continue
                if module.split(".", 1)[0] in forbidden_roots:
                    violations.append(f"{path.name}:{node.lineno}:{module}")

            source = path.read_text(encoding="utf-8")
            for forbidden_text in ("QProcess", "CommandRunner", "shell=True"):
                if forbidden_text in source:
                    violations.append(f"{path.name}:{forbidden_text}")

        self.assertEqual(violations, [])

    def test_gallery_is_test_only_and_absent_from_runtime_registration(self) -> None:
        runtime_paths = (
            ROOT / "loofi-fedora-tweaks" / "core" / "plugins" / "spec.py",
            ROOT / "loofi-fedora-tweaks" / "core" / "navigation" / "manifest.py",
            ROOT / "loofi-fedora-tweaks" / "ui" / "main_window.py",
            ROOT / "pyproject.toml",
            ROOT / "MANIFEST.in",
        )
        runtime_text = "\n".join(path.read_text(encoding="utf-8") for path in runtime_paths)
        self.assertNotIn("ComponentGallery", runtime_text)
        self.assertNotIn("v16ComponentGallery", runtime_text)
        self.assertTrue((ROOT / "tests" / "support" / "v16_component_gallery.py").is_file())

    def test_structural_qss_covers_components_and_interaction_states(self) -> None:
        qss = (ROOT / "loofi-fedora-tweaks" / "assets" / "base.qss").read_text(encoding="utf-8")
        for selector in (
            'QFrame[componentCard="true"]',
            'QFrame[clickableCard="true"]:focus',
            'QFrame[clickableCard="true"][interactionState="active"]',
            'QPushButton#componentButton[buttonRole="primary"]',
            'QPushButton#componentButton[buttonRole="secondary"]',
            'QPushButton#componentButton[buttonRole="ghost"]',
            'QPushButton#componentButton[buttonRole="danger"]',
            'QPushButton#componentButton[interactionState="loading"]',
            'QPushButton#componentButton[interactionState="error"]',
            'QPushButton#componentButton[interactionState="success"]',
            "QPushButton:pressed",
            "QPushButton:disabled",
            "QPushButton:focus",
            "QFrame#sectionNavigator",
            "QListWidget#sectionRail::item:selected",
            "QComboBox#sectionSelector",
            'QFrame#statusBadge[statusKind="warning"]',
            'QFrame#inlineNotice[noticeKind="error"]',
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, qss)

    def test_components_have_no_direct_product_colours(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in COMPONENT_ROOT.glob("*.py")
        )
        self.assertNotRegex(source, r"#[0-9a-fA-F]{3,8}")


if __name__ == "__main__":
    unittest.main()
