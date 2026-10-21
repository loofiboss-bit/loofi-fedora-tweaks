#!/usr/bin/env python3
"""Compile and run the Qt stale-child-index regression in isolated XDG state.

A zero exit code proves only this native regression, not full AT-SPI candidate
qualification. No packages are installed and no desktop settings are changed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main() -> int:
    source = Path(__file__).with_name("qt_scroll_accessibility_probe.cpp")
    flags = subprocess.run(["pkg-config", "--cflags", "--libs", "Qt6Widgets"],
                           check=True, capture_output=True, text=True, timeout=15)
    with tempfile.TemporaryDirectory(prefix="loofi-qt-regression-") as directory:
        root = Path(directory)
        binary = root / "probe"
        subprocess.run(["c++", "-std=c++17", str(source), "-o", str(binary), *shlex.split(flags.stdout)],
                       check=True, capture_output=True, text=True, timeout=90)
        environment = dict(os.environ)
        for name in ("CONFIG", "DATA", "CACHE", "RUNTIME"):
            path = root / name.lower()
            path.mkdir(mode=0o700)
            environment[f"XDG_{name}_HOME" if name != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
        environment["QT_QPA_PLATFORM"] = "offscreen"
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30, env=environment)
        print(json.dumps({"passed": result.returncode == 0, "exit_code": result.returncode,
                          "stdout": result.stdout, "stderr": result.stderr}))
        return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
