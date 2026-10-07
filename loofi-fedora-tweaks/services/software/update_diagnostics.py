"""Source-specific, explicit update diagnostics using existing Health sessions."""

from __future__ import annotations

import json
import shutil
import time
from threading import Event

from core.executor.command_facade import CommandFacade
from core.troubleshooting.adapters import SourceEvidence
from core.troubleshooting.lifecycle import CancellationSignal
from core.troubleshooting.models import NextStep, TroubleshootingSession
from core.troubleshooting.service import DefaultEvidenceCollector, TroubleshootingService
from services.software.update_overview import OverviewRuntime
from services.software.flatpak_maintenance import INSTALLATION_PATTERN, REF_PATTERN

SOURCE_PROFILES = {
    "system": "updates_failed",
    "flatpak": "flatpak_updates_failed",
    "firmware": "firmware_updates_failed",
}
PROFILE_SOURCES = {profile: source for source, profile in SOURCE_PROFILES.items()}


class UpdateDiagnosticsService:
    """GUI and CLI share the same persisted, source-owned diagnostic outcome."""

    def __init__(self, service=None):
        self.service = service or TroubleshootingService()

    def diagnose(self, source: str, *, run_id: str | None = None):
        if source not in SOURCE_PROFILES:
            raise ValueError("Unknown update source.")
        return self.service.run(
            SOURCE_PROFILES[source], parameters={"run_id": run_id} if run_id else {},
        )


class _DiagnosticRuntime(OverviewRuntime):
    _QUERIES = {
        ("flatpak", "list", "--all", "--columns=ref,runtime,installation"),
        ("flatpak", "remotes", "--columns=name,options"),
        ("systemctl", "is-active", "fwupd.service"),
        ("fwupdmgr", "get-devices", "--json"),
    }


class _CancellationEvent(Event):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def is_set(self):
        return self.signal.is_cancelled()


def collect_update_health(
    collector: DefaultEvidenceCollector, source_id: str, session: TroubleshootingSession,
    started_at: float, cancellation: CancellationSignal,
) -> SourceEvidence:
    """Read local metadata only; retain counts instead of raw/private output."""
    source = "flatpak" if source_id == "flatpak-update-health" else "firmware"
    tool = "flatpak" if source == "flatpak" else "fwupdmgr"
    if not shutil.which(tool):
        return collector._state(
            source_id, session, "unavailable", started_at,
            reason_code="update-tool-missing", message=f"{tool} is unavailable; review its installation in the desktop software manager.",
        )
    runtime = _DiagnosticRuntime(CommandFacade(), cancelled=_CancellationEvent(cancellation), output_limit=1024 * 1024)
    deadline = time.monotonic() + 15

    def query(vector):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        return runtime.execute_read_only(vector, action_id="update-diagnostics", timeout=remaining)

    facts = {"update_source": source, "tool_available": True}
    error = ""
    next_step = "Review the source in the desktop software manager, then deliberately check updates again."
    if source == "flatpak":
        inventory = query(("flatpak", "list", "--all", "--columns=ref,runtime,installation"))
        remotes = query(("flatpak", "remotes", "--columns=name,options"))
        for name, result in (("inventory", inventory), ("remotes", remotes)):
            facts[name + "_available"] = bool(result and result.success)
        if not inventory or not inventory.success or not remotes or not remotes.success:
            error = "local-flatpak-probe-failed"
        else:
            rows = [line.split("\t") for line in inventory.stdout.splitlines() if line.strip()]
            remote_rows = [line.split("\t") for line in remotes.stdout.splitlines() if line.strip()]
            if any(len(row) != 3 or not REF_PATTERN.fullmatch("runtime/" + row[0])
                   or (row[1] and not REF_PATTERN.fullmatch("runtime/" + row[1]))
                   or not INSTALLATION_PATTERN.fullmatch(row[2]) for row in rows):
                error = "local-flatpak-inventory-invalid"
            elif any(len(row) != 2 or not row[0] for row in remote_rows):
                error = "local-flatpak-remotes-invalid"
            else:
                installed = {(row[2], row[0]) for row in rows if not row[1]}
                public_runtimes = {ref for installation, ref in installed if installation != "user"}
                missing = sum(1 for ref, runtime_ref, installation in rows
                              if runtime_ref and (installation, runtime_ref) not in installed
                              and runtime_ref not in public_runtimes)
                facts.update(installed_ref_count=len(rows), missing_runtime_count=missing)
                facts["remote_count"] = len(remote_rows)
                if missing:
                    error = "flatpak-runtime-missing"
                    next_step = "Inspect the affected apps and runtimes in Apps before changing or reinstalling anything."
    else:
        active = query(("systemctl", "is-active", "fwupd.service"))
        devices = query(("fwupdmgr", "get-devices", "--json"))
        service_state = active.stdout.strip() if active else "unknown"
        facts["service_state"] = service_state if service_state in {"active", "inactive", "failed", "activating", "deactivating"} else "unknown"
        facts["devices_available"] = bool(devices and devices.success)
        if not devices or not devices.success:
            error = "firmware-device-probe-failed"
        else:
            try:
                payload = json.loads(devices.stdout)
                device_list = payload.get("Devices")
                if not isinstance(device_list, list) or any(not isinstance(device, dict) for device in device_list):
                    raise ValueError("Invalid devices")
                facts["device_count"] = len(device_list)
            except (ValueError, TypeError, AttributeError):
                error = "firmware-device-payload-invalid"
        if facts["service_state"] == "unknown" and not error:
            error = "firmware-service-state-unavailable"
        elif facts["service_state"] != "active" and not error:
            error = "firmware-service-not-active"
        next_step = "Review the fwupd service and device availability before deliberately checking firmware updates again."
    facts["error_code"] = error
    finding = collector._finding(
        session, source_id=source_id, finding_type=source + "-update-diagnosis", category="updates",
        severity="attention" if error else "info", title=source.title() + " update diagnosis",
        summary="The local checks need review." if error else "Local metadata was observed; this does not verify an update or remote availability.",
        evidence=facts, resources=(source + "-updates",),
        next_step=NextStep.manual(next_step, reason_code="review-" + source + "-update-source"),
    )
    if error in {
        "local-flatpak-probe-failed", "local-flatpak-inventory-invalid", "local-flatpak-remotes-invalid",
        "firmware-device-probe-failed", "firmware-device-payload-invalid", "firmware-service-state-unavailable",
    }:
        from core.troubleshooting.adapters import adapt_structured_source

        return adapt_structured_source(
            profile_id=session.profile_id, variant=session.variant, source_id=source_id, state="partial",
            started_at=started_at, completed_at=collector.clock(), facts=facts, findings=(finding,),
            reason_code=error, message="A local read-only probe failed; availability remains unverified.",
        )
    return collector._completed(source_id, session, started_at, facts, (finding,))
