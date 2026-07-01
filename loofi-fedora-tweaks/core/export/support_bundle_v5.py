"""Support Bundle v5 for Aegis release diagnostics."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, cast

from core.diagnostics.readiness_actions import ReadinessActionService
from core.diagnostics.release_readiness import ReleaseReadiness
from core.executor.action_executor import ActionExecutor
from core.export.report_exporter import ReportExporter
from services.package.dnf5_health import DNF5HealthService
from utils.log import get_logger
from version import __version__, __version_codename__

logger = get_logger(__name__)


class SupportBundleV5:
    """Privacy-masked diagnostic bundle for guided readiness support.

    The class name stays stable for compatibility; the v10 payload schema is
    support-v6 and preserves all v5 fields.
    """

    BUNDLE_SCHEMA = "10.0.0-waypoint-support-v6"
    _SECRET_KEY_RE = re.compile(r"(?i)(token|password|passwd|secret|api[_-]?key|private[_-]?key|access[_-]?key|credential)")
    _SECRET_VALUE_RE = re.compile(r"(?i)(token|password|passwd|secret|api[_-]?key|private[_-]?key|access[_-]?key)=([^\s&]+)")
    _HOME_RE = re.compile(r"/home/[^/\\s]+")
    _EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+)")

    @classmethod
    def _mask_text(cls, text: str) -> str:
        masked = cls._HOME_RE.sub("/home/<user>", text or "")
        masked = cls._SECRET_VALUE_RE.sub(r"\1=<masked>", masked)
        masked = cls._EMAIL_RE.sub(r"\1***\2", masked)
        return masked[:6000]

    @classmethod
    def _redact(cls, value: Any, key_name: str = "") -> Any:
        if cls._SECRET_KEY_RE.search(key_name):
            return "<masked>"
        if isinstance(value, dict):
            return {key: cls._redact(item, str(key)) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._redact(item, key_name) for item in value]
        if isinstance(value, tuple):
            return [cls._redact(item, key_name) for item in value]
        if isinstance(value, str):
            return cls._mask_text(value)
        return value

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
    def _readiness_delta(cls) -> None:
        return None

    @classmethod
    def generate_bundle(cls, target: str = "44") -> Dict[str, Any]:
        mode = "upgrade-plan" if target == "45-preview" else "check"
        readiness = ReleaseReadiness.run(target, mode=mode)
        package_report = readiness.package or DNF5HealthService.collect()
        readiness_payload = readiness.to_dict(advanced=True)
        action_plan = ReadinessActionService.build_plan(target, report=readiness)
        action_history = ActionExecutor.get_action_log(limit=25)
        system_info = ReportExporter.gather_system_info()
        release_plan = ReleaseReadiness.build_release_plan(readiness)
        update_preview = {
            "package_manager": package_report.package_manager,
            "dnf_locked": package_report.dnf_locked,
            "repo_probe_ok": package_report.repo_probe_ok,
            "repo_risks": [risk.to_dict() for risk in package_report.repo_risks],
        }

        bundle: Dict[str, Any] = {
            "v": cls.BUNDLE_SCHEMA,
            "schema": cls.BUNDLE_SCHEMA,
            "app": {
                "version": __version__,
                "codename": __version_codename__,
            },
            "timestamp": time.time(),
            "system": system_info,
            "release_readiness": readiness_payload,
            "fedora_kde_44_readiness": readiness_payload,
            "release_plan": release_plan,
            "target_changes": readiness_payload.get("target_changes", {}),
            "action_candidates": [candidate.to_dict() for candidate in action_plan.candidates],
            "action_plan": action_plan.to_dict(),
            "action_history": action_history,
            "update_preview": update_preview,
            "readiness_delta": cls._readiness_delta(),
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
                "emails_masked": True,
                "private_files_included": False,
                "redaction": "recursive",
            },
        }
        return cast(Dict[str, Any], cls._redact(bundle))

    @classmethod
    def save_json(cls, path: str, target: str = "44") -> str:
        bundle = cls.generate_bundle(target=target)
        Path(path).write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
        return path
