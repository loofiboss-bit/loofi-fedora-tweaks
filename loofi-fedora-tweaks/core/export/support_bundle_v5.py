"""Support Bundle v5 for Aegis release diagnostics."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, cast

from core.actions import ActionCenterService
from core.diagnostics.daily_maintenance import DailyMaintenanceService
from core.diagnostics.readiness_actions import ReadinessActionService
from core.diagnostics.release_readiness import ReleaseReadiness
from core.executor.action_executor import ActionExecutor
from core.export.report_exporter import ReportExporter
from core.observability import HealthSnapshot, HealthTimelineStore, MaintenanceTrendAnalyzer
from core.privacy import redact_text
from services.package.dnf5_health import DNF5HealthService
from utils.log import get_logger
from version import __version__, __version_codename__

logger = get_logger(__name__)


class SupportBundleV5:
    """Privacy-masked diagnostic bundle for guided readiness support.

    The class name stays stable for compatibility; the v12 payload schema is
    support-v8 and preserves older v5/v6/v7 fields.
    """

    BUNDLE_SCHEMA = "12.0.0-lighthouse-support-v8"
    _SECRET_KEY_RE = re.compile(r"(?i)(token|password|passwd|secret|api[_-]?key|private[_-]?key|access[_-]?key|credential)")
    _SECRET_VALUE_RE = re.compile(r"(?i)(token|password|passwd|secret|api[_-]?key|private[_-]?key|access[_-]?key)=([^\s&]+)")
    _HOME_RE = re.compile(r"/home/[^/\\s]+")
    _EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+)")
    _HOSTNAME_RE = re.compile(r"(?i)\b(hostname|host)\s*[:=]\s*([A-Za-z0-9_.-]+)")

    @classmethod
    def _mask_text(cls, text: str) -> str:
        masked = redact_text(text or "")
        masked = cls._HOME_RE.sub("/home/<user>", masked)
        masked = cls._SECRET_VALUE_RE.sub(r"\1=<masked>", masked)
        masked = cls._EMAIL_RE.sub(r"\1***\2", masked)
        masked = cls._HOSTNAME_RE.sub(r"\1=<masked-host>", masked)
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
    def _daemon_status(cls) -> Dict[str, Any]:
        return {
            "user_service_probe": cls._run(["systemctl", "--user", "is-active", "loofi-fedora-tweaks.service"], timeout=8) or "unknown",
            "user": "<masked>",
        }

    @classmethod
    def _web_api_status(cls) -> Dict[str, Any]:
        return {
            "enabled_hint": "optional",
            "user_service_probe": cls._run(["systemctl", "--user", "is-active", "loofi-fedora-tweaks-api.service"], timeout=8) or "unknown",
        }

    @staticmethod
    def _github_issue_text(readiness_summary: str, action_count: int, recurring_count: int = 0) -> str:
        return (
            "## Loofi Fedora Tweaks diagnostics\n\n"
            f"{readiness_summary}\n\n"
            f"Action Center candidates: {action_count}\n"
            f"Recurring health timeline issues: {recurring_count}\n"
            "Private paths, emails, tokens, and host identifiers are redacted in the attached support bundle."
        )

    @classmethod
    def generate_bundle(cls, target: str = "44") -> Dict[str, Any]:
        mode = "upgrade-plan" if target == "45-preview" else "check"
        readiness = ReleaseReadiness.run(target, mode=mode)
        package_report = readiness.package or DNF5HealthService.collect()
        readiness_payload = readiness.to_dict(advanced=True)
        action_plan = ReadinessActionService.build_plan(target, report=readiness)
        action_history = ActionExecutor.get_action_log(limit=25)
        action_center = ActionCenterService()
        action_center_items = action_center.candidates_from_readiness(target)
        action_center_history = action_center.recent_history(limit=25)
        system_info = ReportExporter.gather_system_info()
        release_plan = ReleaseReadiness.build_release_plan(readiness)
        daily_maintenance = DailyMaintenanceService().collect()
        current_snapshot = HealthSnapshot.from_daily_maintenance(daily_maintenance, action_center_items=action_center_items, fedora_target=target)
        timeline_store = HealthTimelineStore()
        stored_timeline = timeline_store.load()
        timeline = [*stored_timeline, current_snapshot]
        trend_summary = MaintenanceTrendAnalyzer(timeline).analyze()
        recommendations = action_center.recommendations_from_timeline()
        update_preview = {
            "package_manager": package_report.package_manager,
            "dnf_locked": package_report.dnf_locked,
            "repo_probe_ok": package_report.repo_probe_ok,
            "repo_risks": [risk.to_dict() for risk in package_report.repo_risks],
        }

        bundle: Dict[str, Any] = {
            "v": cls.BUNDLE_SCHEMA,
            "schema": cls.BUNDLE_SCHEMA,
            "support_bundle_version": 8,
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
            "action_center": {
                "candidates": [item.to_dict() for item in action_center_items],
                "history": action_center_history,
                "failed": [entry for entry in action_center_history if str(entry.get("event")) == "executed" and not cast(Dict[str, Any], entry.get("result", {})).get("success", False)],
                "succeeded": [entry for entry in action_center_history if str(entry.get("event")) == "executed" and cast(Dict[str, Any], entry.get("result", {})).get("success", False)],
                "rollback_hints": [item.rollback_hint for item in action_center_items if item.rollback_hint],
            },
            "daily_maintenance": daily_maintenance.to_dict(),
            "health_snapshot": current_snapshot.to_dict(),
            "health_timeline": {
                "schema_version": 1,
                "snapshots": [snapshot.to_dict() for snapshot in timeline[-10:]],
                "trend_summary": trend_summary.to_dict(),
                "corrupt_history_recovered": bool(timeline_store.last_error),
            },
            "recurring_problem_fingerprints": [item.to_dict() for item in trend_summary.recurring],
            "action_center_recommendations": [item.to_dict() for item in recommendations],
            "daemon_snapshot_status": {
                "latest_snapshot_timestamp": stored_timeline[-1].timestamp if stored_timeline else None,
                "last_error": timeline_store.last_error,
                "read_only": True,
            },
            "read_only_collection_errors": list(current_snapshot.collection_errors),
            "update_preview": update_preview,
            "readiness_delta": cls._readiness_delta(),
            "support_summary": readiness.support_summary(),
            "github_issue_text": cls._github_issue_text(readiness.support_summary(), len(action_center_items), len(trend_summary.recurring)),
            "daemon_status": cls._daemon_status(),
            "web_api_status": cls._web_api_status(),
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
