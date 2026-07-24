#!/usr/bin/env python3
"""Reproducible offscreen startup benchmark for the v15 shell."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PROCESS_ENTRY_NS = time.perf_counter_ns()
SCHEMA_VERSION = 1


def _milliseconds(start_ns: int = PROCESS_ENTRY_NS) -> float:
    return (time.perf_counter_ns() - start_ns) / 1_000_000


def _rss_kib() -> int:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _prepare_profile(profile: Path) -> None:
    config = profile / ".config" / "loofi-fedora-tweaks"
    config.mkdir(parents=True, exist_ok=True)
    (config / "first_run_complete").write_text("1\n")
    (config / "settings.json").write_text(
        json.dumps(
            {
                "navigation_mode": "standard",
                "favorite_routes": [],
                "hidden_routes": [],
                "start_minimized": False,
                "show_notifications": False,
                "check_updates_on_start": False,
                "state_schema_version": 2,
            }
        )
    )


def _child_measurement() -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    profile = Path(os.environ["LOOFI_BENCHMARK_PROFILE"])
    os.environ["HOME"] = str(profile)

    real_run = subprocess.run
    probes: list[list[str]] = []

    def recording_run(*args, **kwargs):
        command = args[0] if args else kwargs.get("args", [])
        if isinstance(command, (list, tuple)):
            probes.append([str(part) for part in command])
        else:
            probes.append([str(command)])
        return real_run(*args, **kwargs)

    subprocess.run = recording_run
    try:
        from PyQt6.QtCore import QThread, QTimer
        from PyQt6.QtWidgets import QApplication

        from core.plugins.registry import PluginRegistry
        from ui.main_window import MainWindow

        gui_import_ms = _milliseconds()
        app = QApplication.instance() or QApplication([])
        qapplication_ms = _milliseconds()
        window = MainWindow()
        main_window_ms = _milliseconds()
        window.show()
        show_returned_ms = _milliseconds()

        home_entry = window._sidebar_index["atlas_dashboard"]
        deadline = time.monotonic() + 15
        while home_entry.page_widget.get_real_widget() is None:
            if time.monotonic() >= deadline:
                raise TimeoutError("Meaningful Home did not render within 15 seconds")
            app.processEvents()

        meaningful_home_ms = _milliseconds()
        registry = PluginRegistry.instance()
        imported = sorted(sys.modules)
        system_check_runtime_imports = [
            name
            for name in imported
            if name in {
                "core.system_check.service",
                "core.workers.system_check_worker",
            }
        ]
        ui_modules = [name for name in imported if name == "ui" or name.startswith("ui.")]
        tab_modules = [name for name in ui_modules if name.endswith("_tab")]
        timers = window.findChildren(QTimer)
        threads = window.findChildren(QThread)
        active_timers = [timer.interval() for timer in timers if timer.isActive()]
        running_threads = sum(1 for thread in threads if thread.isRunning())

        return {
            "schema_version": SCHEMA_VERSION,
            "milestones_ms": {
                "gui_import": round(gui_import_ms, 3),
                "qapplication": round(qapplication_ms, 3),
                "main_window": round(main_window_ms, 3),
                "show_returned": round(show_returned_ms, 3),
                "meaningful_home": round(meaningful_home_ms, 3),
            },
            "rss_kib": _rss_kib(),
            "imports": {
                "all": len(imported),
                "ui": len(ui_modules),
                "ui_tab": len(tab_modules),
                "ui_modules": ui_modules,
                "ui_tab_modules": tab_modules,
            },
            "runtime_plugin_ids": [plugin.metadata().id for plugin in registry.list_all()],
            "plugin_spec_count": len(registry.list_specs()),
            "installed_components": sorted(
                window._navigation_context.installed_components
            ),
            "qt_widget_count": len(app.allWidgets()),
            "active_timer_intervals_ms": sorted(active_timers),
            "running_qthreads": running_threads,
            "subprocess_probes": probes,
            "system_check_runtime_imports": system_check_runtime_imports,
            "post_render_services_scheduled": window._post_render_services_scheduled,
        }
    finally:
        subprocess.run = real_run


def _summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    milestone_names = tuple(runs[0]["milestones_ms"])
    milestones: dict[str, dict[str, float]] = {}
    for name in milestone_names:
        values = [float(run["milestones_ms"][name]) for run in runs]
        milestones[name] = {
            "median": round(statistics.median(values), 3),
            "min": round(min(values), 3),
            "max": round(max(values), 3),
        }
    rss_values = [int(run["rss_kib"]) for run in runs]
    return {
        "milestones_ms": milestones,
        "rss_kib": {
            "median": int(statistics.median(rss_values)),
            "min": min(rss_values),
            "max": max(rss_values),
        },
    }


def _run_parent(warmups: int, run_count: int, output: Path | None) -> dict[str, Any]:
    if warmups < 0 or run_count < 1:
        raise ValueError("warmups must be >= 0 and runs must be >= 1")

    runs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="loofi-v15-startup-") as tmpdir:
        profile = Path(tmpdir)
        _prepare_profile(profile)
        environment = os.environ.copy()
        environment["HOME"] = str(profile)
        environment["LOOFI_BENCHMARK_PROFILE"] = str(profile)
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        source_root = environment.get(
            "LOOFI_SOURCE_ROOT",
            str(Path(__file__).resolve().parents[1] / "loofi-fedora-tweaks"),
        )
        existing_pythonpath = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = source_root + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
        command = [sys.executable, str(Path(__file__).resolve()), "--child"]

        for index in range(warmups + run_count):
            try:
                completed = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                    timeout=30,
                )
            except subprocess.CalledProcessError as exc:
                details = (exc.stderr or exc.stdout or "no child output").strip()
                raise RuntimeError(f"Startup benchmark child failed: {details}") from exc
            measurement = json.loads(completed.stdout)
            if index >= warmups:
                runs.append(measurement)

    result = {
        "schema_version": SCHEMA_VERSION,
        "method": {
            "warmups": warmups,
            "runs": run_count,
            "qt_platform": "offscreen",
            "profile": "temporary-standard-clean",
            "marker": "AtlasDashboardTab realized",
        },
        "summary": _summarize(runs),
        "runs": runs,
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.child:
        print(json.dumps(_child_measurement(), sort_keys=True))
        return 0

    result = _run_parent(args.warmups, args.runs, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
