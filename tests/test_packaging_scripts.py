"""Tests for packaging scripts used in v30.0."""

import importlib.util
import os
import re
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from shutil import copy2

ROOT = Path(__file__).resolve().parents[1]
BASH = "/bin/bash"


def _load_packaging_manifest_module():
    spec = importlib.util.spec_from_file_location(
        "check_packaging_manifest_test",
        ROOT / "scripts" / "check_packaging_manifest.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _base_env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path / 'bin'}:{env.get('PATH', '')}"
    return env


def _extract_version(version_file: Path) -> str:
    content = version_file.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', content, re.MULTILINE)
    assert match, "Version parse failed in test fixture"
    return match.group(1)


def test_packaging_manifest_static_metadata_passes():
    module = _load_packaging_manifest_module()
    assert module.validate_packaging(build=False) == []


def test_packaging_manifest_tracks_navigation_and_assets():
    module = _load_packaging_manifest_module()
    expected = set(module.EXPECTED_SOURCE_SUFFIXES)
    assert "core/navigation/areas.py" in expected
    assert "core/navigation/destinations.py" in expected
    assert "core/navigation/manifest.py" in expected
    assert "core/navigation/migrations.py" in expected
    assert "core/navigation/models.py" in expected
    assert "core/navigation/policy.py" in expected
    assert "core/platform/profile.py" in expected
    assert "core/executor/command_facade.py" in expected
    assert "core/executor/command_policy.py" in expected
    assert "ui/layout_primitives.py" in expected
    assert "assets/base.qss" in expected
    assert "ui/design/theme_manager.py" in expected
    assert "resources/translations/en.ts" in expected
    assert "config/apps.json" in expected


def test_artifact_check_rejects_retired_runtime_surfaces():
    module = _load_packaging_manifest_module()
    names = {
        "loofi_fedora_tweaks/main.py",
        "loofi_fedora_tweaks/config/apps.json",
        "loofi_fedora_tweaks/config/org.loofi.fedora-tweaks.policy",
    }
    errors = module._artifact_errors(names, artifact="fixture.tar.gz", wheel=True)
    assert any("retired artifact" in error for error in errors)


@unittest.skipIf(sys.platform == "win32", "Bash scripts require bash shell not available on Windows")
def test_build_appimage_missing_dependency(tmp_path):
    env = _base_env(tmp_path)
    (tmp_path / "bin").mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [BASH, "scripts/build_appimage.sh"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Missing required tool" in (result.stderr + result.stdout)


@unittest.skipIf(sys.platform == "win32", "Bash scripts require bash shell not available on Windows")
def test_build_appimage_success_with_stub_tools(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        bin_dir / "linuxdeploy",
        "#!/bin/bash\n"
        "if [[ \"$1\" == \"--version\" ]]; then\n"
        "  echo linuxdeploy\n"
        "fi\n"
        "exit 0\n",
    )
    _write_executable(
        bin_dir / "appimagetool",
        "#!/bin/bash\n"
        "touch \"$2\"\n"
        "exit 0\n",
    )

    env = _base_env(tmp_path)
    result = subprocess.run(
        [BASH, "scripts/build_appimage.sh"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    version = _extract_version(ROOT / "loofi-fedora-tweaks" / "version.py")
    expected_appimage = ROOT / "dist" / "appimage" / \
        f"loofi-fedora-tweaks-v{version}-x86_64.AppImage"
    assert expected_appimage.exists()


@unittest.skipIf(sys.platform == "win32", "Bash scripts require bash shell not available on Windows")
def test_build_appimage_linuxdeploy_from_env_var(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    custom_linuxdeploy = tmp_path / "linuxdeploy-custom"
    _write_executable(custom_linuxdeploy, "#!/bin/bash\nexit 0\n")
    _write_executable(bin_dir / "appimagetool",
                      "#!/bin/bash\ntouch \"$2\"\nexit 0\n")

    env = _base_env(tmp_path)
    env["LINUXDEPLOY_BIN"] = str(custom_linuxdeploy)
    result = subprocess.run(
        [BASH, "scripts/build_appimage.sh"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0


@unittest.skipIf(sys.platform == "win32", "Bash scripts require bash shell not available on Windows")
def test_build_appimage_missing_desktop_file(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "scripts").mkdir(parents=True, exist_ok=True)
    (project_root / "loofi-fedora-tweaks" /
     "assets").mkdir(parents=True, exist_ok=True)

    copy2(ROOT / "scripts" / "build_appimage.sh",
          project_root / "scripts" / "build_appimage.sh")
    (project_root / "loofi-fedora-tweaks" /
     "version.py").write_text('__version__ = "30.0.0"\n', encoding="utf-8")
    (project_root / "loofi-fedora-tweaks" /
     "main.py").write_text("print('ok')\n", encoding="utf-8")
    (project_root / "loofi-fedora-tweaks" /
     "assets" / "icon.png").write_bytes(b"png")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _write_executable(bin_dir / "linuxdeploy", "#!/bin/bash\nexit 0\n")
    _write_executable(bin_dir / "appimagetool", "#!/bin/bash\nexit 0\n")

    env = _base_env(tmp_path)
    result = subprocess.run(
        [BASH, "scripts/build_appimage.sh"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Missing desktop file" in (result.stderr + result.stdout)


@unittest.skipIf(sys.platform == "win32", "Bash scripts require bash shell not available on Windows")
def test_build_sdist_missing_build_module(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        bin_dir / "python3",
        "#!/bin/bash\n"
        "if [[ \"$1\" == \"-c\" ]]; then\n"
        "  exit 1\n"
        "fi\n"
        "exit 0\n",
    )

    env = _base_env(tmp_path)
    result = subprocess.run(
        [BASH, "scripts/build_sdist.sh"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Python module 'build' is required" in (
        result.stderr + result.stdout)


@unittest.skipIf(sys.platform == "win32", "Bash scripts require bash shell not available on Windows")
def test_build_sdist_success_with_stub_python(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "scripts").mkdir(parents=True)
    egg_info = project_root / "loofi-fedora-tweaks" / "loofi_fedora_tweaks.egg-info"
    egg_info.mkdir(parents=True)
    (egg_info / "SOURCES.txt").write_text("ui/removed.py\n", encoding="utf-8")
    copy2(ROOT / "scripts" / "build_sdist.sh", project_root / "scripts" / "build_sdist.sh")
    (project_root / "loofi-fedora-tweaks" / "version.py").write_text(
        '__version__ = "30.0.0"\n', encoding="utf-8"
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        bin_dir / "python3",
        "#!/bin/bash\n"
        "if [[ \"$1\" == \"-c\" ]]; then\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"$1\" == \"-m\" && \"$2\" == \"build\" ]]; then\n"
        "  mkdir -p dist\n"
        "  touch dist/loofi_fedora_tweaks-30.0.0.tar.gz\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )

    env = _base_env(tmp_path)
    result = subprocess.run(
        [BASH, "scripts/build_sdist.sh"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert (project_root / "dist" / "loofi_fedora_tweaks-30.0.0.tar.gz").exists()
    assert not egg_info.exists()
