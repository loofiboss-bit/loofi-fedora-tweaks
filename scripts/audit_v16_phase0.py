#!/usr/bin/env python3
"""Produce the reproducible, read-only v16 Phase 0 compatibility inventory."""

from __future__ import annotations

import argparse
import ast
from dataclasses import fields
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tomllib
from typing import Any, Iterable

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "loofi-fedora-tweaks"
UI_ROOT = APP_ROOT / "ui"
QSS_ROOT = APP_ROOT / "assets"
BASELINE_TAG = "v15.0.0"
BASELINE_AUTHORITY_COMMIT = "b96eafec85a3d7e55535201dd7459ef5c9de46b1"
HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
CLASSIFICATIONS = frozenset({"KEEP", "ADAPT", "REPLACE", "DELETE", "DEFER"})

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def _decision(classification: str, phase: str, risk: str) -> dict[str, str]:
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"Unknown Phase 0 classification: {classification}")
    return {
        "classification": classification,
        "target_phase": phase,
        "compatibility_risk": risk,
    }


def _source_site(path: Path, node: ast.AST, **extra: Any) -> dict[str, Any]:
    result = {
        "file": path.relative_to(REPO_ROOT).as_posix(),
        "line": int(getattr(node, "lineno", 0)),
    }
    result.update(extra)
    return result


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _target_name(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except (AttributeError, ValueError):
        return ""


class _UiVisitor(ast.NodeVisitor):
    """Collect syntax-level UI ownership signals without importing PyQt."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tabs: list[dict[str, Any]] = []
        self.scroll_owners: list[dict[str, Any]] = []
        self.margin_calls: list[dict[str, Any]] = []
        self.inline_styles: list[dict[str, Any]] = []
        self.page_titles: list[dict[str, Any]] = []
        self.hardcoded_colors: list[dict[str, Any]] = []
        self.full_width_actions: list[dict[str, Any]] = []
        self._seen_colors: set[tuple[int, str]] = set()
        self._button_targets: set[str] = set()
        self._vbox_targets: set[str] = set()

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call):
            constructor = _call_name(node.value.func)
            for target in node.targets:
                name = _target_name(target)
                if constructor == "QPushButton":
                    self._button_targets.add(name)
                elif constructor == "QVBoxLayout":
                    self._vbox_targets.add(name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in {"QTabWidget", "QTabBar"}:
            if name == "QTabBar":
                decision = _decision("REPLACE", "3", "critical")
            elif self.path.name in {"monitor_tab.py", "diagnostics_tab.py"}:
                decision = _decision("REPLACE", "4", "high")
            elif self.path.name in {
                "desktop_tab.py",
                "maintenance_tab.py",
                "network_tab.py",
                "settings_tab.py",
                "software_tab.py",
            }:
                decision = _decision("REPLACE", "5", "high")
            else:
                decision = _decision("DEFER", "6", "medium")
            self.tabs.append(
                _source_site(
                    self.path,
                    node,
                    widget=name,
                    **decision,
                )
            )
        elif name == "QScrollArea":
            self.scroll_owners.append(
                _source_site(self.path, node, widget="QScrollArea", **_decision("ADAPT", "4-7", "medium"))
            )
        elif name == "setContentsMargins":
            values = [ast.unparse(arg) for arg in node.args]
            self.margin_calls.append(
                _source_site(self.path, node, values=values, **_decision("ADAPT", "4-6", "low"))
            )
        elif name == "setStyleSheet":
            self.inline_styles.append(
                _source_site(self.path, node, **_decision("REPLACE", "1-2", "medium"))
            )
        elif name in {"PageHeader", "make_page_title"}:
            self.page_titles.append(
                _source_site(
                    self.path,
                    node,
                    owner=name,
                    object_name="",
                    **_decision("ADAPT", "4-6", "medium"),
                )
            )
        elif name == "setObjectName" and node.args:
            value = node.args[0]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                object_name = value.value
                lowered = object_name.lower()
                is_page_title = lowered == "header" or lowered.endswith("header") or lowered in {
                    "sectiontitle",
                    "pageheadertitle",
                }
                if is_page_title and "subheader" not in lowered:
                    owner = _target_name(node.func.value) if isinstance(node.func, ast.Attribute) else ""
                    self.page_titles.append(
                        _source_site(
                            self.path,
                            node,
                            owner=owner,
                            object_name=object_name,
                            **_decision("ADAPT", "4-6", "medium"),
                        )
                    )
        elif name == "addWidget" and node.args:
            receiver = _target_name(node.func.value) if isinstance(node.func, ast.Attribute) else ""
            widget = _target_name(node.args[0])
            is_button = widget in self._button_targets or "button" in widget.lower() or "btn" in widget.lower()
            is_vertical = receiver in self._vbox_targets or receiver.endswith(".body")
            if is_button and is_vertical:
                self.full_width_actions.append(
                    _source_site(
                        self.path,
                        node,
                        widget=widget,
                        heuristic="button added directly to a vertical layout without an action row",
                        **_decision("ADAPT", "2-6", "medium"),
                    )
                )

        numeric_args = [
            arg.value
            for arg in node.args
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int)
        ]
        if name == "QColor" and len(numeric_args) == len(node.args) and len(numeric_args) >= 3:
            literal = "QColor(" + ", ".join(str(value) for value in numeric_args) + ")"
            self._add_color(node, literal)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            for match in HEX_COLOR_RE.finditer(node.value):
                self._add_color(node, match.group(0).lower())

    def _add_color(self, node: ast.AST, value: str) -> None:
        key = (int(getattr(node, "lineno", 0)), value)
        if key in self._seen_colors:
            return
        self._seen_colors.add(key)
        self.hardcoded_colors.append(
            _source_site(self.path, node, value=value, **_decision("REPLACE", "1", "high"))
        )


def _scan_ui() -> dict[str, Any]:
    visitors: list[_UiVisitor] = []
    for path in sorted(UI_ROOT.rglob("*.py")):
        visitor = _UiVisitor(path)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        visitors.append(visitor)

    def collect(attribute: str) -> list[dict[str, Any]]:
        values = [value for visitor in visitors for value in getattr(visitor, attribute)]
        return sorted(values, key=lambda item: (item["file"], item["line"], json.dumps(item, sort_keys=True)))

    tabs = collect("tabs")
    tab_widgets = [site for site in tabs if site["widget"] == "QTabWidget"]
    tab_bars = [site for site in tabs if site["widget"] == "QTabBar"]
    margins = collect("margin_calls")
    inline_styles = collect("inline_styles")
    colors = collect("hardcoded_colors")
    scroll_owners = collect("scroll_owners")
    page_titles = collect("page_titles")
    full_width = collect("full_width_actions")
    return {
        "tabs": {
            "qtabwidget_count": len(tab_widgets),
            "qtabwidget_file_count": len({site["file"] for site in tab_widgets}),
            "qtabbar_count": len(tab_bars),
            "sites": tabs,
        },
        "page_title_owners": {"count": len(page_titles), "sites": page_titles},
        "scroll_owners": {"count": len(scroll_owners), "sites": scroll_owners},
        "root_margin_heuristic": {
            "count": len(margins),
            "method": "all explicit setContentsMargins calls in ui/**/*.py; Phase 0 treats each as a root-margin review candidate",
            "sites": margins,
        },
        "inline_styles": {"count": len(inline_styles), "sites": inline_styles},
        "hardcoded_colors": {
            "count": len(colors),
            "method": "hex literals and direct numeric QColor construction in ui/**/*.py",
            "sites": colors,
        },
        "full_width_action_heuristic": {
            "count": len(full_width),
            "method": "button-like widgets added directly to a known vertical/body layout",
            "sites": full_width,
        },
    }


def _qss_selectors(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    without_comments = re.sub(
        r"/\*.*?\*/",
        lambda match: "\n" * match.group(0).count("\n"),
        text,
        flags=re.DOTALL,
    )
    selectors: list[dict[str, Any]] = []
    for match in re.finditer(r"([^{}]+)\{", without_comments):
        raw_prelude = match.group(1)
        if not raw_prelude.strip():
            continue
        for part in re.finditer(r"[^,]+", raw_prelude):
            raw_selector = part.group(0)
            selector = raw_selector.strip()
            if not selector or not re.match(r"^Q[A-Za-z]", selector):
                continue
            selector_offset = len(raw_selector) - len(raw_selector.lstrip())
            selector_start = match.start(1) + part.start() + selector_offset
            line = without_comments.count("\n", 0, selector_start) + 1
            broad = "#" not in selector and "[" not in selector
            if broad:
                selectors.append(
                    {
                        "file": path.relative_to(REPO_ROOT).as_posix(),
                        "line": line,
                        "selector": " ".join(selector.split()),
                        **_decision("REPLACE", "1", "high"),
                    }
                )
    return sorted(selectors, key=lambda item: (item["file"], item["line"], item["selector"]))


def _scan_qss() -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    broad: list[dict[str, Any]] = []
    for path in sorted(QSS_ROOT.glob("*.qss")):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        files.append(
            {
                "file": path.relative_to(REPO_ROOT).as_posix(),
                "line_count": line_count,
                **_decision("REPLACE", "1", "high"),
            }
        )
        broad.extend(_qss_selectors(path))
    return {
        "line_count": sum(item["line_count"] for item in files),
        "files": files,
        "broad_selectors": {"count": len(broad), "sites": broad},
    }


def _release_identity() -> dict[str, Any]:
    tag_object = _git("rev-parse", BASELINE_TAG)
    baseline_commit = _git("rev-parse", f"{BASELINE_TAG}^{{}}")
    product_diff = _git("diff", "--name-only", baseline_commit, "--", APP_ROOT.name).splitlines()
    untracked_product_paths = _git(
        "ls-files", "--others", "--exclude-standard", "--", APP_ROOT.name
    ).splitlines()
    if product_diff or untracked_product_paths:
        changed = product_diff + untracked_product_paths
        raise RuntimeError(
            f"Phase 0 requires {APP_ROOT.name}/ to match {BASELINE_TAG}; changed paths: {', '.join(changed)}"
        )
    return {
        "branch": _git("branch", "--show-current"),
        "phase0_branch_point": BASELINE_AUTHORITY_COMMIT,
        "baseline_tag": BASELINE_TAG,
        "tag_object": tag_object,
        "tag_object_type": _git("cat-file", "-t", BASELINE_TAG),
        "baseline_commit": baseline_commit,
        "product_tree": _git("rev-parse", "HEAD:loofi-fedora-tweaks"),
        "baseline_product_tree": _git("rev-parse", f"{baseline_commit}:loofi-fedora-tweaks"),
        "product_diff": product_diff,
        "untracked_product_paths": untracked_product_paths,
        "product_matches_baseline": True,
        **_decision("KEEP", "0", "critical"),
    }


def _version_and_schemas() -> dict[str, Any]:
    from core.actions.history import MAX_HISTORY
    from core.actions.model import ActionCenterItem
    from core.actions.stores import (
        ACTION_PLAN_SCHEMA_VERSION,
        ACTION_RUN_SCHEMA_VERSION,
        MAX_ACTION_PLANS,
        MAX_ACTION_RUNS,
    )
    from core.actions.contracts import ActionPlan, ActionRun
    from core.state.inventory import StateInventory
    from utils.settings import STATE_SCHEMA_VERSION
    from version import __version__, __version_codename__

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    spec_match = re.search(
        r"^Version:\s*(\S+)",
        (REPO_ROOT / "loofi-fedora-tweaks.spec").read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    state_domains = [
        {
            "id": domain.id,
            "owner": domain.owner,
            "schema_id": domain.schema_id,
            "schema_version": domain.schema_version,
            "category": domain.category,
            **_decision("KEEP", "0", "critical"),
        }
        for domain in StateInventory().all()
    ]
    return {
        "application": {
            "version": __version__,
            "codename": __version_codename__,
            "pyproject_version": str(pyproject["project"]["version"]),
            "rpm_spec_version": spec_match.group(1) if spec_match else "",
            **_decision("KEEP", "0", "critical"),
        },
        "settings_schema_version": STATE_SCHEMA_VERSION,
        "state_domains": state_domains,
        "action_center": {
            "plan_schema_version": ACTION_PLAN_SCHEMA_VERSION,
            "run_schema_version": ACTION_RUN_SCHEMA_VERSION,
            "history_schema_version": 3,
            "plan_limit": MAX_ACTION_PLANS,
            "run_limit": MAX_ACTION_RUNS,
            "history_limit": MAX_HISTORY,
            "plan_fields": [field.name for field in fields(ActionPlan)],
            "run_fields": [field.name for field in fields(ActionRun)],
            "history_item_fields": [field.name for field in fields(ActionCenterItem)],
            **_decision("KEEP", "0", "critical"),
        },
    }


def _navigation_and_plugins() -> dict[str, Any]:
    from core.navigation import all_destinations, all_routes, placement_for_route
    from core.navigation import manifest
    from core.plugins.spec import BUILTIN_PLUGIN_SPECS

    routes = []
    for route in all_routes():
        placement = placement_for_route(route.id)
        routes.append(
            {
                "id": route.id,
                "label": route.label,
                "plugin_id": route.plugin_id,
                "aliases": list(route.aliases),
                "destination_id": placement.destination_id if placement else "",
                "section_id": placement.section_id if placement else "",
                "redirect_route_id": placement.redirect_route_id if placement else None,
                "discoverable": placement.discoverable if placement else False,
                "advanced_only": placement.advanced_only if placement else False,
                "component_id": placement.component_id if placement else "",
                "allowed_variants": sorted(variant.value for variant in placement.allowed_variants) if placement else [],
                **_decision("KEEP", "0", "critical"),
            }
        )
    destinations = [
        {
            "id": destination.id,
            "label": destination.label,
            "default_route_id": destination.default_route_id,
            "route_ids": list(destination.route_ids),
            "section_ids": sorted(
                {
                    placement_for_route(route_id).section_id
                    for route_id in destination.route_ids
                    if placement_for_route(route_id) is not None
                }
            ),
            "advanced_only": destination.advanced_only,
            **_decision("KEEP", "0", "critical"),
        }
        for destination in all_destinations()
    ]
    plugins = [
        {
            "id": spec.id,
            "module": spec.module,
            "class_name": spec.class_name,
            "destination_id": spec.destination_id,
            "component": spec.component,
            "visibility": spec.visibility,
            "order": spec.order,
            "owner_route_ids": sorted(route.id for route in all_routes() if route.plugin_id == spec.id),
            **_decision("KEEP", "0", "critical"),
        }
        for spec in BUILTIN_PLUGIN_SPECS
    ]
    redirects = [
        {
            "route_id": route["id"],
            "target_route_id": route["redirect_route_id"],
            **_decision("KEEP", "0", "critical"),
        }
        for route in routes
        if route["redirect_route_id"]
    ]
    alias_keys = [
        {
            "key": key,
            "route_id": manifest._ROUTE_BY_ALIAS[key].id,
            **_decision("KEEP", "0", "critical"),
        }
        for key in sorted(manifest._ROUTE_BY_ALIAS)
    ]
    return {
        "route_count": len(routes),
        "route_ids": sorted(route["id"] for route in routes),
        "routes": sorted(routes, key=lambda item: item["id"]),
        "alias_key_count": len(manifest._ROUTE_BY_ALIAS),
        "alias_keys": alias_keys,
        "destinations": sorted(destinations, key=lambda item: item["id"]),
        "redirects": sorted(redirects, key=lambda item: item["route_id"]),
        "lazy_plugin_specs": sorted(plugins, key=lambda item: item["id"]),
        "section_metadata_decision": {
            "current_source": "core.navigation.destinations.RoutePlacement.section_id",
            "v16_requirement": "add explicit data-only section label and description metadata; do not derive either from the first route",
            **_decision("ADAPT", "3", "high"),
        },
    }


def _action_catalog() -> dict[str, Any]:
    from core.actions.catalog import ActionCatalog
    from core.actions.contracts import PLAN_TRANSITIONS, RUN_TRANSITIONS

    definitions = [
        {**definition.to_dict(), **_decision("KEEP", "0", "critical")}
        for definition in ActionCatalog().list()
    ]
    return {
        "deny_by_default": True,
        "count": len(definitions),
        "definitions": definitions,
        "plan_transitions": {key: sorted(value) for key, value in sorted(PLAN_TRANSITIONS.items())},
        "run_transitions": {key: sorted(value) for key, value in sorted(RUN_TRANSITIONS.items())},
        **_decision("KEEP", "0", "critical"),
    }


def _environment() -> dict[str, Any]:
    try:
        os_release = platform.freedesktop_os_release()
    except OSError:
        os_release = {}
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
    except ImportError:
        PYQT_VERSION_STR = "unavailable"
        QT_VERSION_STR = "unavailable"
    return {
        "python": platform.python_version(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "os_release": {
            key: str(os_release.get(key, ""))
            for key in ("ID", "VERSION_ID", "PRETTY_NAME", "VARIANT_ID")
        },
        "desktop": {
            "current_desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
            "session_desktop": os.environ.get("XDG_SESSION_DESKTOP", ""),
            "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
            "qt_platform": os.environ.get("QT_QPA_PLATFORM", ""),
        },
        "qt": {
            "qt_version": QT_VERSION_STR,
            "pyqt_version": PYQT_VERSION_STR,
        },
    }


def build_inventory() -> dict[str, Any]:
    """Build a stable inventory after proving the product tree matches v15."""
    release = _release_identity()
    return {
        "schema_version": 1,
        "audit": "loofi-fedora-tweaks-v16-phase0",
        "release_identity": release,
        "environment": _environment(),
        "versions_and_state_schemas": _version_and_schemas(),
        "navigation": _navigation_and_plugins(),
        "action_center": _action_catalog(),
        "ui_debt": _scan_ui(),
        "qss_debt": _scan_qss(),
        "classification_legend": {
            "values": sorted(CLASSIFICATIONS),
            "compatibility_risks": ["low", "medium", "high", "critical"],
        },
    }


def render_inventory(inventory: dict[str, Any]) -> str:
    return json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_output(output: str, payload: str) -> None:
    if output == "-":
        sys.stdout.write(payload)
        return
    Path(output).write_text(payload, encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="-",
        metavar="PATH",
        help="Write deterministic JSON to PATH, or '-' for stdout (default).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    _write_output(args.output, render_inventory(build_inventory()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
