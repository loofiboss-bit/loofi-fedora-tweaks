#!/usr/bin/env python3
"""Capture reproducible v15 shell evidence for the v16 Phase 0 baseline.

The capture uses the real ``MainWindow`` and its lazy plugin loader.  User
state is isolated in a temporary HOME/XDG tree, background services are
disabled, and potentially mutating child-process commands are rejected.

Raw matrix frames are evidence inputs rather than repository artifacts by
default.  Their paths and SHA-256 digests remain in the JSON manifest while
six compact contact sheets are retained under ``docs/images/v16/phase0``.
Pass ``--retain-raw`` when an audit needs every PNG on disk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence, cast
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "loofi-fedora-tweaks"
OUTPUT_ROOT = ROOT / "docs" / "images" / "v16" / "phase0"
REFERENCE_SOURCE_DIR = OUTPUT_ROOT
REPORT_PATH = ROOT / "docs" / "reports" / "V16_PHASE0_SCREENSHOTS.json"
RAW_DIR = OUTPUT_ROOT / "raw"
CONTACT_SHEET_DIR = OUTPUT_ROOT / "contact-sheets"

BACKEND = "offscreen"
THEME = "system"
FONT_SCALE_METHOD = "QApplication font point-size proxy"
REPRODUCTION_COMMAND = (
    "PYTHONPATH=loofi-fedora-tweaks QT_QPA_PLATFORM=offscreen "
    "python3 scripts/capture_v16_phase0.py"
)


@dataclass(frozen=True)
class DestinationCapture:
    destination_id: str
    route_id: str


@dataclass(frozen=True)
class ViewportScale:
    width: int
    height: int
    scale_percent: int


@dataclass(frozen=True)
class ReferenceScreenshot:
    source_filename: str
    filename: str
    sha256: str
    width: int
    height: int
    finding: str


DESTINATIONS: tuple[DestinationCapture, ...] = (
    DestinationCapture("home", "atlas_dashboard"),
    DestinationCapture("software_updates", "software:apps"),
    DestinationCapture("system", "system_info"),
    DestinationCapture("network_security", "network"),
    DestinationCapture("desktop", "desktop"),
    DestinationCapture("settings", "settings"),
)

VIEWPORT_SCALE_MATRIX: tuple[ViewportScale, ...] = tuple(
    ViewportScale(width, height, scale)
    for scale in (100, 125, 140, 150)
    for width, height in ((860, 720), (1366, 768), (1920, 1080))
) + (ViewportScale(2560, 1440, 200),)

REFERENCE_SCREENSHOTS: tuple[ReferenceScreenshot, ...] = (
    ReferenceScreenshot(
        source_filename="8abef557-d0cf-4cbe-904d-b96b8f2af36c.png",
        filename="home-system-theme.png",
        sha256="9614465e0c9e65259a83f77d9c7d914916a98b95872eb1a64c2fb468a254a53b",
        width=1918,
        height=1018,
        finding="Home hierarchy and full-width nested actions in system-theme mode",
    ),
    ReferenceScreenshot(
        source_filename="ddb44c74-4ae5-4c7a-b857-2cb9de09ef82.png",
        filename="system-section-overflow.png",
        sha256="c59acd6a67232452e0e050a413c529ae54b40b0d54cf76fd8e4fb698c866cd52",
        width=1918,
        height=1018,
        finding="System peer-section labels remain elided at a 1918 px shell width",
    ),
)


def build_capture_matrix() -> tuple[tuple[DestinationCapture, ViewportScale], ...]:
    """Return the complete 6 x 13 Phase 0 capture contract."""
    return tuple(
        (destination, viewport)
        for destination in DESTINATIONS
        for viewport in VIEWPORT_SCALE_MATRIX
    )


def capture_filename(destination: DestinationCapture, viewport: ViewportScale) -> str:
    """Return the stable raw-frame filename for a matrix cell."""
    return (
        f"{destination.destination_id}__{viewport.width}x{viewport.height}"
        f"__font-{viewport.scale_percent:03d}.png"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(path: Path) -> str:
    """Prefer repository-relative paths while supporting isolated unit tests."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _image_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG dimensions without adding a Pillow dependency."""
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"not a supported PNG: {path}")
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def preserve_reference_screenshots() -> list[dict[str, object]]:
    """Copy supplied screenshots byte-for-byte after strict validation."""
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for reference in REFERENCE_SCREENSHOTS:
        source = REFERENCE_SOURCE_DIR / reference.filename
        if not source.is_file():
            raise FileNotFoundError(f"missing preserved screenshot: {source}")
        actual_hash = sha256_file(source)
        actual_size = _image_dimensions(source)
        if actual_hash != reference.sha256:
            raise ValueError(
                f"unexpected source hash for {source}: {actual_hash}"
            )
        if actual_size != (reference.width, reference.height):
            raise ValueError(
                f"unexpected source dimensions for {source}: {actual_size}"
            )

        target = OUTPUT_ROOT / reference.filename
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
        if sha256_file(target) != reference.sha256:
            raise RuntimeError(f"byte-preserving copy failed for {target}")
        records.append(
            {
                "path": _manifest_path(target),
                "sha256": reference.sha256,
                "width": reference.width,
                "height": reference.height,
                "finding": reference.finding,
                "source_filename": reference.source_filename,
            }
        )
    return records


def _command_tokens(command: object) -> list[str]:
    if isinstance(command, (list, tuple)):
        return [str(token) for token in command]
    if isinstance(command, os.PathLike):
        return [os.fspath(command)]
    if isinstance(command, str):
        return shlex.split(command)
    return [str(command)]


def assert_read_only_command(command: object, *, shell: bool = False) -> None:
    """Reject commands with plausible host-mutation semantics."""
    if shell:
        raise RuntimeError("Phase 0 capture guard rejects shell=True")
    tokens = _command_tokens(command)
    if not tokens:
        return
    program = Path(tokens[0]).name
    lowered = [token.lower() for token in tokens[1:]]
    always_mutating = {
        "pkexec",
        "sudo",
        "su",
        "rm",
        "mv",
        "cp",
        "install",
        "tee",
        "touch",
        "mkdir",
        "rmdir",
        "chmod",
        "chown",
        "chgrp",
        "dd",
        "mount",
        "umount",
        "reboot",
        "shutdown",
    }
    mutating_verbs = {
        "install",
        "remove",
        "erase",
        "upgrade",
        "update",
        "downgrade",
        "rebase",
        "deploy",
        "rollback",
        "apply-live",
        "set",
        "enable",
        "disable",
        "start",
        "stop",
        "restart",
        "reload",
        "mask",
        "unmask",
        "add",
        "delete",
        "modify",
        "connect",
        "disconnect",
        "commit",
        "push",
    }
    mutation_capable = {
        "dnf",
        "dnf5",
        "rpm-ostree",
        "flatpak",
        "systemctl",
        "firewall-cmd",
        "nmcli",
        "gsettings",
        "kwriteconfig5",
        "kwriteconfig6",
        "git",
    }
    if program in always_mutating or (
        program in mutation_capable and any(token in mutating_verbs for token in lowered)
    ):
        raise RuntimeError(
            "Phase 0 capture guard rejected mutating command: "
            + shlex.join(tokens)
        )


@contextmanager
def guarded_subprocesses() -> Iterator[None]:
    """Delegate read-only probes while failing closed on mutating commands."""
    real_run = subprocess.run
    real_popen = subprocess.Popen
    real_check_output = subprocess.check_output
    real_check_call = subprocess.check_call

    def guarded_run(*args, **kwargs):
        command = args[0] if args else kwargs.get("args", [])
        assert_read_only_command(command, shell=bool(kwargs.get("shell", False)))
        tokens = _command_tokens(command)
        if tokens and Path(tokens[0]).name == "kscreen-doctor" and "--outputs" in tokens:
            empty = "" if kwargs.get("text") or kwargs.get("universal_newlines") else b""
            return subprocess.CompletedProcess(command, 0, empty, empty)
        return real_run(*args, **kwargs)

    def guarded_popen(*args, **kwargs):
        command = args[0] if args else kwargs.get("args", [])
        assert_read_only_command(command, shell=bool(kwargs.get("shell", False)))
        return real_popen(*args, **kwargs)

    def guarded_check_output(*args, **kwargs):
        command = args[0] if args else kwargs.get("args", [])
        assert_read_only_command(command, shell=bool(kwargs.get("shell", False)))
        return real_check_output(*args, **kwargs)

    def guarded_check_call(*args, **kwargs):
        command = args[0] if args else kwargs.get("args", [])
        assert_read_only_command(command, shell=bool(kwargs.get("shell", False)))
        return real_check_call(*args, **kwargs)

    with (
        patch("subprocess.run", guarded_run),
        patch("subprocess.Popen", guarded_popen),
        patch("subprocess.check_output", guarded_check_output),
        patch("subprocess.check_call", guarded_check_call),
    ):
        yield


@contextmanager
def isolated_capture_home() -> Iterator[Path]:
    """Use disposable HOME/XDG paths and deterministic Standard/system settings."""
    keys = ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")
    previous = {key: os.environ.get(key) for key in keys}
    with tempfile.TemporaryDirectory(prefix="loofi-v16-phase0-") as temporary:
        home = Path(temporary)
        values = {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
        }
        os.environ.update(values)
        config_dir = home / ".config" / "loofi-fedora-tweaks"
        config_dir.mkdir(parents=True, exist_ok=True)
        catalog_cache = home / ".cache" / "loofi-fedora-tweaks" / "apps.json"
        catalog_cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC / "config" / "apps.json", catalog_cache)
        (config_dir / "first_run_complete").touch()
        (config_dir / "tour_complete").touch()
        (config_dir / "favorites.json").write_text(
            '{"version": 2, "favorites": []}\n', encoding="utf-8"
        )
        (config_dir / "settings.json").write_text(
            json.dumps(
                {
                    "theme": "dark",
                    "follow_system_theme": True,
                    "navigation_mode": "standard",
                    "restore_last_tab": False,
                    "last_tab_index": 0,
                    "start_minimized": False,
                    "check_updates_on_start": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            yield home
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _settle(app, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
    )
    return completed.stdout.strip()


def _save_contact_sheet(destination_id: str, frames: Sequence[dict[str, object]]) -> Path:
    from PyQt6.QtCore import QRect, QSize, Qt
    from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen

    columns = 4
    cell_width, cell_height = 380, 245
    header_height = 54
    rows = (len(frames) + columns - 1) // columns
    sheet = QImage(
        QSize(columns * cell_width, header_height + rows * cell_height),
        QImage.Format.Format_RGB32,
    )
    sheet.fill(QColor("#202328"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.setPen(QPen(QColor("#f3f4f6")))
    title_font = QFont()
    title_font.setBold(True)
    title_font.setPointSize(14)
    painter.setFont(title_font)
    painter.drawText(QRect(16, 0, sheet.width() - 32, header_height), Qt.AlignmentFlag.AlignVCenter, destination_id)

    label_font = QFont()
    label_font.setPointSize(9)
    painter.setFont(label_font)
    for index, record in enumerate(frames):
        source = QImage(str(record["temporary_path"]))
        if source.isNull():
            raise RuntimeError(f"failed to load capture for contact sheet: {record['temporary_path']}")
        row, column = divmod(index, columns)
        x = column * cell_width
        y = header_height + row * cell_height
        viewport = cast(list[int], record["viewport"])
        label = (
            f"{viewport[0]}x{viewport[1]}  "
            f"{record['font_scale_percent']}%"
        )
        painter.drawText(QRect(x + 10, y, cell_width - 20, 25), Qt.AlignmentFlag.AlignCenter, label)
        target = QRect(x + 10, y + 28, cell_width - 20, cell_height - 38)
        scaled = source.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image_x = target.x() + (target.width() - scaled.width()) // 2
        image_y = target.y() + (target.height() - scaled.height()) // 2
        painter.drawImage(image_x, image_y, scaled)
        painter.setPen(QPen(QColor("#60656f")))
        painter.drawRect(target)
        painter.setPen(QPen(QColor("#f3f4f6")))
    painter.end()

    CONTACT_SHEET_DIR.mkdir(parents=True, exist_ok=True)
    output = CONTACT_SHEET_DIR / f"{destination_id}.png"
    if not sheet.save(str(output), "PNG"):
        raise RuntimeError(f"failed to save contact sheet: {output}")
    return output


def capture_matrix(*, retain_raw: bool, settle_seconds: float) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Capture all Standard destination defaults through the real MainWindow."""
    os.environ.setdefault("QT_QPA_PLATFORM", BACKEND)
    sys.path.insert(0, str(SRC))

    from PyQt6.QtWidgets import QApplication
    from core.navigation import NavigationMode
    from core.plugins.registry import PluginRegistry
    from ui.main_window import MainWindow
    from utils.command_runner import CommandRunner
    from utils.settings import SettingsManager

    app = cast(QApplication | None, QApplication.instance()) or QApplication(
        ["capture-v16-phase0"]
    )
    app.setStyleSheet("")
    base_font = app.font()
    base_point_size = base_font.pointSizeF()
    if base_point_size <= 0:
        base_point_size = 10.0

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    contact_sheets: list[dict[str, object]] = []
    frames_by_destination: dict[str, list[dict[str, object]]] = {
        destination.destination_id: [] for destination in DESTINATIONS
    }

    def reject_qprocess(*_args, **_kwargs):
        raise RuntimeError("Phase 0 capture guard rejected an asynchronous command")

    with ExitStack() as stack:
        stack.enter_context(guarded_subprocesses())
        stack.enter_context(patch.object(MainWindow, "_check_first_run", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_initialize_background_services", lambda self: None))
        stack.enter_context(patch.object(MainWindow, "_schedule_post_render_services", lambda self: None))
        stack.enter_context(patch.object(CommandRunner, "run_command", reject_qprocess))

        for viewport in VIEWPORT_SCALE_MATRIX:
            scaled_font = app.font()
            scaled_font.setPointSizeF(base_point_size * viewport.scale_percent / 100.0)
            app.setFont(scaled_font)
            app.setStyleSheet("")
            SettingsManager._reset_instance()
            PluginRegistry.reset()

            window = MainWindow()
            window.apply_navigation_mode(NavigationMode.STANDARD)
            window.resize(viewport.width, viewport.height)
            window.show()
            _settle(app, settle_seconds)
            try:
                for destination in DESTINATIONS:
                    if not window.switch_to_route(destination.route_id):
                        raise RuntimeError(
                            f"default route did not resolve: {destination.route_id}"
                        )
                    _settle(app, settle_seconds)
                    filename = capture_filename(destination, viewport)
                    output = RAW_DIR / filename
                    pixmap = window.grab()
                    if pixmap.isNull() or not pixmap.save(str(output), "PNG"):
                        raise RuntimeError(f"failed to save capture: {output}")
                    width, height = _image_dimensions(output)
                    record: dict[str, object] = {
                        "path": _manifest_path(output),
                        "sha256": sha256_file(output),
                        "destination_id": destination.destination_id,
                        "route_id": destination.route_id,
                        "viewport": [viewport.width, viewport.height],
                        "captured_dimensions": [width, height],
                        "font_scale_percent": viewport.scale_percent,
                        "font_scale_method": FONT_SCALE_METHOD,
                        "backend": BACKEND,
                        "theme": THEME,
                        "retained": retain_raw,
                        "temporary_path": str(output),
                    }
                    records.append(record)
                    frames_by_destination[destination.destination_id].append(record)
            finally:
                window.close()
                window.deleteLater()
                _settle(app, 0.05)

    app.setFont(base_font)
    for destination in DESTINATIONS:
        sheet = _save_contact_sheet(
            destination.destination_id,
            frames_by_destination[destination.destination_id],
        )
        contact_sheets.append(
            {
                "destination_id": destination.destination_id,
                "path": _manifest_path(sheet),
                "sha256": sha256_file(sheet),
                "frame_count": len(frames_by_destination[destination.destination_id]),
            }
        )

    for record in records:
        record.pop("temporary_path", None)
    if not retain_raw:
        shutil.rmtree(RAW_DIR)
    return records, contact_sheets


def write_manifest(
    references: Sequence[dict[str, object]],
    captures: Sequence[dict[str, object]],
    contact_sheets: Sequence[dict[str, object]],
) -> dict[str, object]:
    """Write the machine-readable screenshot evidence manifest."""
    manifest: dict[str, object] = {
        "schema_version": 1,
        "release": "v16.0.0 Clarity",
        "phase": 0,
        "captured_product_version": "15.0.0 Essentials",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_value("rev-parse", "HEAD"),
        "capture_policy": {
            "real_main_window": True,
            "navigation_mode": "standard",
            "theme": THEME,
            "backend": BACKEND,
            "temporary_home_and_xdg": True,
            "background_services_disabled": True,
            "mutating_subprocesses_rejected": True,
            "host_display_probe_stubbed": True,
            "catalog_seeded_from_packaged_config": True,
            "raw_frames_retained": bool(captures and captures[0]["retained"]),
            "raw_storage": (
                "retained under docs/images/v16/phase0/raw"
                if captures and captures[0]["retained"]
                else "not committed; hashes and compact contact sheets are retained"
            ),
        },
        "font_scaling": {
            "method": FONT_SCALE_METHOD,
            "limitation": (
                "Offscreen QApplication font scaling is a deterministic proxy only; "
                "real Wayland and X11 compositor scaling is deferred to Phase 7."
            ),
        },
        "reproduction_command": REPRODUCTION_COMMAND,
        "destinations": [asdict(destination) for destination in DESTINATIONS],
        "viewport_scale_matrix": [asdict(viewport) for viewport in VIEWPORT_SCALE_MATRIX],
        "reference_screenshots": list(references),
        "captures": list(captures),
        "contact_sheets": list(contact_sheets),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retain-raw",
        action="store_true",
        help="retain all 78 raw PNG captures in addition to contact sheets",
    )
    parser.add_argument(
        "--references-only",
        action="store_true",
        help="validate/copy supplied screenshots without launching MainWindow",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=0.25,
        help="event-loop settling time before each grab (default: 0.25)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.settle_seconds < 0:
        raise ValueError("--settle-seconds must be non-negative")
    references = preserve_reference_screenshots()
    if args.references_only:
        print(f"validated {len(references)} supplied Phase 0 screenshots")
        return 0

    with isolated_capture_home():
        captures, contact_sheets = capture_matrix(
            retain_raw=args.retain_raw,
            settle_seconds=args.settle_seconds,
        )
        manifest = write_manifest(references, captures, contact_sheets)
    manifest_captures = cast(Sequence[object], manifest["captures"])
    manifest_contact_sheets = cast(Sequence[object], manifest["contact_sheets"])
    print(
        f"captured {len(manifest_captures)} matrix frames and "
        f"{len(manifest_contact_sheets)} contact sheets"
    )
    print(REPORT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
