"""Fedora KDE 44 desktop environment detection.

Read-only helpers for Plasma, Qt, session, and display-manager state. These
functions intentionally avoid UI imports and do not mutate system state.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List

from utils.log import get_logger

logger = get_logger(__name__)


@dataclass
class KDE44DesktopInfo:
    """Snapshot of Fedora KDE desktop compatibility signals."""

    plasma_version: str = "Unknown"
    qt_version: str = "Unknown"
    session_type: str = "Unknown"
    desktop: str = "Unknown"
    display_manager: str = "Unknown"
    display_manager_active: bool = False
    display_manager_detail: str = ""
    warnings: List[str] = field(default_factory=list)
    raw: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "plasma_version": self.plasma_version,
            "qt_version": self.qt_version,
            "session_type": self.session_type,
            "desktop": self.desktop,
            "display_manager": self.display_manager,
            "display_manager_active": self.display_manager_active,
            "display_manager_detail": self.display_manager_detail,
            "warnings": list(self.warnings),
            "raw": dict(self.raw),
        }


class KDE44DesktopService:
    """Read-only Fedora KDE 44 desktop detector."""

    @staticmethod
    def _run(cmd: List[str], timeout: int = 8) -> str:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return result.stderr.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
            logger.debug("Desktop probe failed for %s: %s", cmd, exc)
            return ""

    @staticmethod
    def _extract_version(text: str) -> str:
        match = re.search(r"(\d+(?:\.\d+){1,3})", text or "")
        return match.group(1) if match else "Unknown"

    @staticmethod
    def _extract_qt_version(text: str) -> str:
        match = re.search(r"Qt\s+version\s+(\d+(?:\.\d+){1,3})", text or "", re.IGNORECASE)
        if match:
            return match.group(1)
        return KDE44DesktopService._extract_version(text)

    @classmethod
    def get_plasma_version(cls) -> str:
        out = cls._run(["plasmashell", "--version"])
        return cls._extract_version(out)

    @classmethod
    def get_qt_version(cls) -> str:
        for cmd in (["qmake6", "--version"], ["qmake", "--version"]):
            out = cls._run(cmd)
            if out:
                version = cls._extract_qt_version(out)
                if version != "Unknown":
                    return version

        try:
            from PyQt6.QtCore import QT_VERSION_STR

            return str(QT_VERSION_STR)
        except ImportError as exc:
            logger.debug("PyQt6 Qt version fallback failed: %s", exc)
            return "Unknown"

    @staticmethod
    def get_session_type() -> str:
        return os.environ.get("XDG_SESSION_TYPE", "Unknown") or "Unknown"

    @staticmethod
    def get_desktop() -> str:
        return os.environ.get("XDG_CURRENT_DESKTOP", "Unknown") or "Unknown"

    @classmethod
    def get_display_manager(cls) -> tuple[str, bool, str]:
        service_path = "/etc/systemd/system/display-manager.service"
        resolved = os.path.realpath(service_path) if os.path.exists(service_path) else ""
        guessed = "Unknown"

        lowered = resolved.lower()
        if "sddm" in lowered:
            guessed = "SDDM"
        elif "gdm" in lowered:
            guessed = "GDM"
        elif "lightdm" in lowered:
            guessed = "LightDM"

        active_out = cls._run(["systemctl", "is-active", "display-manager.service"], timeout=5)
        active = active_out.strip() == "active"

        detail = resolved or "display-manager.service symlink not found"
        if active_out:
            detail = f"{detail}; state={active_out.strip()}"

        if guessed == "Unknown":
            status_out = cls._run(["systemctl", "status", "display-manager.service", "--no-pager"], timeout=5)
            lowered_status = status_out.lower()
            if "sddm" in lowered_status:
                guessed = "SDDM"
            elif "gdm" in lowered_status:
                guessed = "GDM"
            if status_out:
                detail = status_out[:1000]

        return guessed, active, detail

    @classmethod
    def collect(cls) -> KDE44DesktopInfo:
        dm_name, dm_active, dm_detail = cls.get_display_manager()
        info = KDE44DesktopInfo(
            plasma_version=cls.get_plasma_version(),
            qt_version=cls.get_qt_version(),
            session_type=cls.get_session_type(),
            desktop=cls.get_desktop(),
            display_manager=dm_name,
            display_manager_active=dm_active,
            display_manager_detail=dm_detail,
            raw={
                "XDG_SESSION_TYPE": os.environ.get("XDG_SESSION_TYPE", ""),
                "XDG_CURRENT_DESKTOP": os.environ.get("XDG_CURRENT_DESKTOP", ""),
            },
        )

        if info.session_type.lower() == "x11":
            info.warnings.append("X11 session detected. Fedora KDE 44 is optimized for Plasma Wayland.")
        elif info.session_type == "Unknown":
            info.warnings.append("Unable to determine session type.")

        if info.display_manager == "GDM":
            info.warnings.append("GDM detected on a KDE system. SDDM is the expected Plasma login manager.")
        elif info.display_manager == "Unknown":
            info.warnings.append("Unable to identify the display manager.")
        elif not info.display_manager_active:
            info.warnings.append("Display manager service is not active.")

        return info
