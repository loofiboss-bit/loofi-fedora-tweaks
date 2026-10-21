#!/usr/bin/env python3
"""Build patched QtWidgets in an isolated directory; never install host files.

Requires matching Fedora Qt 6.11.2 Core/Gui development and private headers,
WidgetsTools, BuildInternals, CMake, Ninja, C++, patch, and pkg-config.
The resulting library is an experimental qualification artifact, not an RPM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import urllib.request


VERSION = "6.11.2"
ARCHIVE = f"qtbase-everywhere-src-{VERSION}.tar.xz"
URL = f"https://download.qt.io/official_releases/qt/6.11/{VERSION}/submodules/{ARCHIVE}"
SHA256 = "5b2e00eccaf5a4d8c14134ffa0ea8dfd0a35ae1ffc7f8d87fa4305a1ed23cf22"


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run(arguments: list[str], *, timeout: int = 120, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(arguments, check=True, text=True, timeout=timeout, **kwargs)


def main() -> int:
    repository = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=repository / "test-results/v35/qt-runtime")
    options = parser.parse_args()
    root = options.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    version = run(["pkg-config", "--modversion", "Qt6Widgets"], capture_output=True).stdout.strip()
    if version != VERSION:
        parser.error(f"Requires exact installed Qt {VERSION}, found {version}")
    archive = root / ARCHIVE
    if not archive.exists():
        with urllib.request.urlopen(URL, timeout=180) as response, archive.open("wb") as target:
            while block := response.read(1024 * 1024):
                target.write(block)
    if digest(archive) != SHA256:
        raise ValueError("Official Qt archive SHA256 mismatch; remove the invalid download")
    source = root / f"qtbase-everywhere-src-{VERSION}"
    patch = repository / "packaging/qt/qtbase-scroll-area-accessibility.patch"
    if not source.exists():
        with tarfile.open(archive) as bundle:
            bundle.extractall(root, filter="data")
    # Reverse dry-run accepts a resumable build only with this exact patch applied.
    applied = subprocess.run(["patch", "--reverse", "--dry-run", "-p1", "-i", str(patch)],
                             cwd=source, capture_output=True, text=True, timeout=30)
    if applied.returncode != 0:
        run(["patch", "--forward", "-p1", "-i", str(patch)], cwd=source)
    wrapper = root / "widgets-project"
    wrapper.mkdir(exist_ok=True)
    (wrapper / "CMakeLists.txt").write_text(
        'cmake_minimum_required(VERSION 3.24)\n'
        f'project(LoofiPatchedQtWidgets VERSION {VERSION} LANGUAGES CXX C)\n'
        f'set(QT_REPO_MODULE_VERSION {VERSION})\n'
        f'find_package(Qt6 {VERSION} EXACT REQUIRED COMPONENTS BuildInternals Core Gui WidgetsTools)\n'
        'qt_internal_project_setup()\nqt_build_repo_begin()\n'
        f'add_subdirectory("{source.as_posix()}/src/widgets" widgets)\n'
        'qt_build_repo_end()\n', encoding="utf-8")
    build = root / "widgets-build"
    with (root / "configure.log").open("a") as log:
        run(["cmake", "-S", str(wrapper), "-B", str(build), "-G", "Ninja",
             "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_AUTOGEN_PARALLEL=2",
             f"-DCMAKE_INSTALL_PREFIX={root / 'stage'}", "-DQT_BUILD_TESTS=OFF",
             "-DQT_BUILD_EXAMPLES=OFF"], stdout=log, stderr=subprocess.STDOUT)
    with (root / "build.log").open("a") as log:
        run(["cmake", "--build", str(build), "--target", "Widgets", "--parallel", "2"],
            timeout=7200, stdout=log, stderr=subprocess.STDOUT)
    library = next(build.rglob(f"libQt6Widgets.so.{VERSION}"))
    include = run(["pkg-config", "--variable=includedir", "Qt6Widgets"], capture_output=True).stdout.strip()
    feature_pattern = r"^#define (QT_FEATURE_\w+) ([-\d]+)$"
    installed_config = (Path(include) / "QtWidgets/qtwidgets-config.h").read_text()
    built_config = (build / "widgets/qtwidgets-config.h").read_text()
    installed_features = dict(re.findall(feature_pattern, installed_config, re.M))
    built_features = dict(re.findall(feature_pattern, built_config, re.M))
    if installed_features != built_features:
        raise RuntimeError("Built QtWidgets feature configuration differs from installed Qt")
    flags = run(["pkg-config", "--cflags", "--libs", "Qt6Widgets"], capture_output=True).stdout
    probe = root / "qt-scroll-probe"
    run(["c++", "-std=c++17", str(repository / "scripts/qt_scroll_accessibility_probe.cpp"),
         "-o", str(probe), *shlex.split(flags)])
    environment = dict(os.environ)
    # Only this process and its child probe use the complete corrected library.
    environment.pop("LD_PRELOAD", None)
    environment["LD_LIBRARY_PATH"] = str(library.parent)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    for name in ("CONFIG", "DATA", "CACHE", "RUNTIME"):
        path = root / "probe-state" / name.lower()
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        environment[f"XDG_{name}_HOME" if name != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
    dependencies = run(["ldd", str(probe)], env=environment, capture_output=True).stdout
    if str(library.parent) not in dependencies:
        raise RuntimeError("Probe did not load the built QtWidgets library")
    dependency_libraries = {}
    for name in ("Core", "Gui"):
        match = re.search(rf"libQt6{name}\.so\.6 => (\S+)", dependencies)
        if match is None:
            raise RuntimeError(f"Missing resolved Qt{name} dependency")
        dependency = Path(match.group(1)).resolve(strict=True)
        dependency_libraries[name] = {"path": str(dependency), "sha256": digest(dependency)}
    result = subprocess.run([str(probe)], env=environment, capture_output=True, text=True, timeout=30)
    packages = run(["rpm", "-q", "qt6-qtbase", "qt6-qtbase-gui", "qt6-qtbase-devel",
                    "qt6-qtbase-private-devel"], capture_output=True).stdout
    evidence = {"source_url": URL, "source_sha256": digest(archive),
                "patch_sha256": digest(patch), "runtime_path": str(library),
                "runtime_library_dir": str(library.parent),
                "runtime_sha256": digest(library), "build_parallelism": 2,
                "matched_widgets_features": len(built_features),
                "dependency_libraries": dependency_libraries,
                "installed_dependencies": packages, "probe_dependencies": dependencies,
                "passed": result.returncode == 0, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr,
                "qualification": "native regression only; full candidate AT-SPI VM runs still required"}
    (root / "qualification.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
