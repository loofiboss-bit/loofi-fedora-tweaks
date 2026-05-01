"""Support Bundle v4 with generic release readiness diagnostics."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

from core.diagnostics.release_readiness import ReleaseReadiness
from core.export.report_exporter import ReportExporter
from services.package.dnf5_health import DNF5HealthService
from utils.log import get_logger
from version import __version__, __version_codename__

logger = get_logger(__name__)


class SupportBundleV4:
    """Privacy-masked diagnostic bundle for release readiness support."""

    BUNDLE_SCHEMA = "6.0.0-compass-support-v4"

    @staticmethod
    def _mask_text(text: str) -> str:
        masked = re.sub(r"/home/[^/\\s]+", "/home/<user>", text or "")
        masked = re.sub(r"(?i)(token|password|secret|key)=([^\s&]+)", r"\1=<masked>", masked)
        masked = re.sub(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+)", r"\1***\2", masked)
        return masked[:6000]

    @classmethod
    def _run(cls, cmd: list[str], timeout: int = 12) -> str:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            return cls._mask_text((result.stdout or result.stderr).strip())
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
            logger.debug("Support bundle probe failed for %s: %s", cmd, exc)
            return ""

    @classmethod
    def _flatpak_runtimes(cls) -> str:
        return cls._run(["flatpak", "list", "--runtime", "--columns=application,branch,origin"], timeout=20)

    @classmethod
    def _recent_journal_warnings(cls) -> str:
        return cls._run(["journalctl", "-p", "4", "-n", "80", "--no-pager", "--output=short"], timeout=15)

    @classmethod
    def _failed_services(cls) -> list[dict[str, str]]:
        return ReportExporter.gather_services_info()

    @classmethod
    def generate_bundle(cls, target: str = "44") -> Dict[str, Any]:
        readiness = ReleaseReadiness.run(target)
        package_report = readiness.package or DNF5HealthService.collect()
        system_info = ReportExporter.gather_system_info()
        readiness_payload = readiness.to_dict(advanced=True)
        bundle = {
            "v": cls.BUNDLE_SCHEMA,
            "app": {
                "version": __version__,
                "codename": __version_codename__,
            },
            "timestamp": time.time(),
            "system": system_info,
            "release_readiness": readiness_payload,
            "fedora_kde_44_readiness": readiness_payload,
            "support_summary": readiness.support_summary(),
            "desktop": readiness.desktop.to_dict() if readiness.desktop else {},
            "package_health": package_report.to_dict(),
            "rpm_ostree": [
                check.to_dict(advanced=True)
                for check in readiness.checks
                if check.id == "atomic-status"
            ],
            "nvidia_akmods_secureboot": [
                check.to_dict(advanced=True)
                for check in readiness.checks
                if check.id == "nvidia-akmods-secureboot"
            ],
            "failed_services": cls._failed_services(),
            "recent_journal_warnings_errors": cls._recent_journal_warnings(),
            "flatpak_runtimes": cls._flatpak_runtimes(),
            "masked_repo_list": [risk.to_dict() for risk in package_report.repo_risks],
            "privacy": {
                "home_paths_masked": True,
                "tokens_masked": True,
                "private_files_included": False,
            },
        }
        return bundle

    @classmethod
    def save_json(cls, path: str, target: str = "44") -> str:
        bundle = cls.generate_bundle(target=target)
        Path(path).write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
        return path
