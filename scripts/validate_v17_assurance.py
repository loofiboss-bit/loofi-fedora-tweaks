#!/usr/bin/env python3
"""Verify that v17 canonical UI entry points only hand off to Action Center."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TARGETS = {
    "loofi-fedora-tweaks/ui/maintenance_tab.py": {
        "_UpdatesSubTab": {"run_dnf_update", "run_flatpak_update", "run_fw_update", "run_update_all"},
        "_CleanupSubTab": {"run_autoremove", "_review_journal"},
    },
    "loofi-fedora-tweaks/ui/software_tab.py": {
        "_ApplicationsSubTab": {"run_app_action"},
    },
    "loofi-fedora-tweaks/ui/backup_tab.py": {
        "BackupTab": {"_create_snapshot"},
    },
    "loofi-fedora-tweaks/ui/snapshot_tab.py": {
        "SnapshotTab": {"_create_snapshot"},
    },
}

FORBIDDEN_CALLS = {"run_command", "execute", "run_operation", "create_snapshot"}


def violations() -> list[str]:
    problems: list[str] = []
    for relative_path, classes in TARGETS.items():
        path = ROOT / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name not in classes:
                continue
            expected = classes[node.name]
            found = {child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for missing in sorted(expected - found):
                problems.append(f"{relative_path}:{node.name}.{missing}: missing canonical entry point")
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) or child.name not in expected:
                    continue
                for call in (item for item in ast.walk(child) if isinstance(item, ast.Call)):
                    name = call.func.attr if isinstance(call.func, ast.Attribute) else call.func.id if isinstance(call.func, ast.Name) else ""
                    if name in FORBIDDEN_CALLS:
                        problems.append(f"{relative_path}:{child.lineno}:{node.name}.{child.name}: forbidden direct call {name}")
    return problems


def main() -> int:
    problems = violations()
    if problems:
        print("v17 Assurance mutation inventory: FAIL")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("v17 Assurance mutation inventory: PASS (0 direct canonical UI execution paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
