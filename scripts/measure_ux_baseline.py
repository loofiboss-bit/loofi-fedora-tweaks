#!/usr/bin/env python3
"""Measure curated Apps page construction and last-key search latency offscreen."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from pathlib import Path
from statistics import median
from time import perf_counter

from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.catalog_models import FedoraVariant
from core.tasks.applications import ApplicationCatalog, ApplicationContext, ApplicationRecord
from ui.install_workflow import InstallWorkflowPage


ROOT = Path(__file__).resolve().parents[1]


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((percentile * len(ordered) + 0.999999) - 1)))
    return ordered[index]


def _git_value(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip()


def _fixture(rows: int) -> tuple[ApplicationRecord, ...]:
    return tuple(
        ApplicationRecord(
            id=f"fixture-{index:03d}",
            name=f"Fixture application {index:03d}",
            description="A bounded performance fixture for catalog filtering.",
            category="Utilities",
            source="flatpak",
            package_id=f"org.example.Fixture{index:03d}",
            keywords=("fixture", "search"),
        )
        for index in range(rows)
    )


def measure(rows: int, samples: int) -> dict[str, object]:
    app = QApplication.instance() or QApplication([])
    catalog = ApplicationCatalog(_fixture(rows))
    context = ApplicationContext(FedoraVariant.TRADITIONAL, frozenset({"dnf5"}), online=True)

    started = perf_counter()
    page = InstallWorkflowPage(catalog=catalog, context=context)
    app.processEvents()
    construction_ms = (perf_counter() - started) * 1000

    search_samples_ms: list[float] = []
    for index in range(samples):
        query = f"fixture application {index % 10}"
        search = page.search_input
        search.setText(query[:-1])
        app.processEvents()
        started = perf_counter()
        QTest.keyClick(search, query[-1])
        app.processEvents()
        search_samples_ms.append((perf_counter() - started) * 1000)

    page.close()
    page.deleteLater()
    app.processEvents()
    return {
        "revision": _git_value("rev-parse", "HEAD"),
        "working_tree_dirty": bool(_git_value("status", "--porcelain")),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pyqt": PYQT_VERSION_STR,
            "qt": QT_VERSION_STR,
            "qt_platform": "offscreen",
        },
        "fixture": {"catalog_rows": rows, "search_samples": samples},
        "measured_ms": {
            "apps_catalog_construction": round(construction_ms, 2),
            "last_key_to_filtered_list_p50": round(median(search_samples_ms), 2),
            "last_key_to_filtered_list_p95": round(_percentile(search_samples_ms, 0.95), 2),
            "last_key_to_filtered_list_max": round(max(search_samples_ms), 2),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=500, help="Number of synthetic curated app identities.")
    parser.add_argument("--samples", type=int, default=30, help="Number of last-key latency samples.")
    args = parser.parse_args()
    if args.rows < 1 or args.samples < 1:
        parser.error("--rows and --samples must be positive integers")
    print(json.dumps(measure(args.rows, args.samples), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
