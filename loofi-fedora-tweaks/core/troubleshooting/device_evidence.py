"""Hardware and app/network evidence collection for troubleshooting sessions."""

from __future__ import annotations

from typing import Any

from core.troubleshooting.adapters import SourceEvidence, adapt_structured_source
from core.troubleshooting.lifecycle import CancellationSignal
from core.troubleshooting.models import NextStep, TroubleshootingFinding, TroubleshootingSession


class TroubleshootingDeviceEvidenceMixin:
    """Keep device-specific probes out of the main session orchestrator."""

    def _hardware(
        self: Any, source_id: str, session: TroubleshootingSession,
        started_at: float, cancellation: CancellationSignal,
    ) -> SourceEvidence:
        from services.hardware.diagnostic_probes import HardwareDiagnosticProbe

        kind_by_source = {
            "audio-state": "audio",
            "bluetooth-state": "bluetooth",
            "battery-power": "energy",
            "display-state": "display",
            "input-state": "input",
            "printer-state": "printer",
        }
        kind = kind_by_source[source_id]
        remaining = max(0.0, session.started_at + 14.0 - self.clock())
        result = HardwareDiagnosticProbe().collect(kind, cancellation=cancellation, budget=remaining)
        facts = {
            **result.facts,
            "probe_availability": {
                key: "available" if value is not None else "unknown"
                for key, value in result.facts.items()
            },
            "probe_errors": getattr(result, "errors", {}),
        }
        problems = []
        findings: tuple[TroubleshootingFinding, ...] = ()
        if kind in {"energy", "display", "input", "printer"}:
            guidance_by_kind = {
                "energy": "Review the battery and energy details in Overview, then open Energy Saving settings if needed.",
                "display": "Review the observed outputs, then use Display Configuration to adjust them yourself.",
                "input": "Review the observed device counts and touchpad setting, then use Mouse and Touchpad settings.",
                "printer": "Review the aggregate queue results, then use Printer Settings. Check individual jobs there.",
            }
            if kind == "energy":
                batteries = facts.get("batteries") or []
                if not batteries and facts.get("battery_count") == 0:
                    problems.append("No battery was reported by this computer.")
                elif facts.get("ac_online") is False:
                    problems.append("No AC power source is currently reported.")
            elif kind == "display":
                displays = facts.get("displays") or {}
                connected = displays.get("connected_count")
                active = displays.get("active_count")
                if isinstance(connected, int) and isinstance(active, int) and connected > active:
                    problems.append("A connected display is not currently enabled; this may be intentional.")
            elif kind == "input":
                if facts.get("touchpads", 0) and facts.get("touchpad_setting") is False:
                    problems.append("KDE reports the touchpad as disabled.")
            else:
                if facts.get("cups_state") not in {None, "active"}:
                    problems.append("The CUPS service is not active.")
                queues = facts.get("queues") or {}
                acceptance = facts.get("queue_acceptance") or {}
                if queues.get("disabled", 0) or acceptance.get("rejecting", 0):
                    problems.append("One or more printer queues are disabled or rejecting jobs.")
                if facts.get("pending_job_count", 0):
                    problems.append("Print jobs are waiting in the queues.")
            if result.state in {"completed", "partial"} and problems:
                findings = (self._finding(
                    session, source_id=source_id, finding_type=f"{kind}-observations",
                    category="hardware", severity="attention" if problems else "info",
                    title={"energy": "Battery and power observations", "display": "Display and docking observations",
                           "input": "Input device observations", "printer": "Printer queue observations"}[kind],
                    summary=" ".join(problems) if problems else "Available hardware metadata was collected. Confirm the behavior in the corresponding KDE settings or application.",
                    evidence=facts, resources=(f"hardware:{kind}",),
                    next_step=NextStep.manual(guidance_by_kind[kind], reason_code=f"review-{kind}-settings"),
                    evidence_quality="limited" if result.state == "partial" else "supported",
                ),)
            return adapt_structured_source(
                profile_id=session.profile_id, variant=session.variant, source_id=source_id,
                state=result.state, started_at=started_at, completed_at=self.clock(),
                facts=facts if result.state != "unavailable" else None, findings=findings,
                reason_code=result.reason_code,
                message="Some hardware observations are unknown. No devices or settings were changed." if result.reason_code else "",
            )
        if kind == "audio":
            for service in ("pipewire", "wireplumber"):
                state = facts.get(f"{service}_state")
                if state is not None and state != "active":
                    problems.append(f"{service.title()} is {state}.")
            volume = facts.get("output_volume")
            if volume is not None and (volume["muted"] or volume["level"] == 0):
                problems.append("The default output is muted or its volume is zero.")
            guidance = "Open Sound Settings, choose the intended output, and test playback. Run this check again after changing settings."
        else:
            if facts.get("service_state") not in {None, "active"}:
                problems.append("The Bluetooth service is not active.")
            adapter = facts.get("adapter")
            if adapter is not None and not adapter["powered"]:
                problems.append("The Bluetooth adapter is powered off.")
            radio = facts.get("radio")
            if radio is not None:
                if radio["adapter_count"] == 0:
                    problems.append("No Bluetooth radio was reported.")
                elif radio["soft_blocked"] or radio["hard_blocked"]:
                    problems.append("The Bluetooth radio is blocked.")
            guidance = "Open Bluetooth Settings and review the adapter and paired devices. Run this check again after changing settings."
        if result.state in {"completed", "partial"} and problems:
            findings = (self._finding(
                session, source_id=source_id, finding_type=f"{kind}-observations",
                category=kind, severity="attention" if problems else "info",
                title="Sound check observations" if kind == "audio" else "Bluetooth check observations",
                summary=" ".join(problems) if problems else "The available metadata was checked. Confirm playback or device connectivity yourself.",
                evidence=facts, resources=(f"hardware:{kind}",),
                next_step=NextStep.manual(guidance, reason_code=f"review-{kind}-settings"),
                evidence_quality="limited" if result.state == "partial" else "supported",
            ),)
        return adapt_structured_source(
            profile_id=session.profile_id, variant=session.variant, source_id=source_id,
            state=result.state, started_at=started_at, completed_at=self.clock(),
            facts=facts if result.state != "unavailable" else None, findings=findings,
            reason_code=result.reason_code,
            message="Some device observations are unknown. No device settings were changed." if result.reason_code else "",
        )

    def _application_network(
        self: Any,
        source_id: str,
        session: TroubleshootingSession,
        started_at: float,
        cancellation: CancellationSignal,
    ) -> SourceEvidence:
        from services.troubleshooting.application_network import (
            ApplicationIdentity,
            ApplicationNetworkProbe,
        )

        probe = ApplicationNetworkProbe()
        parameters = dict(session.profile_parameters)
        findings: tuple[TroubleshootingFinding, ...] = ()
        if source_id == "network-state":
            result = probe.collect_network(cancellation=cancellation, budget=8.0)
            facts = {
                **result.facts,
                "probe_availability": result.availability,
                "probe_errors": result.errors,
            }
            problems = []
            if facts.get("active_link") is False:
                problems.append("No active network link was reported.")
            if facts.get("default_route") is False:
                problems.append("No default route was reported.")
            if facts.get("resolver_configured") is False:
                problems.append("No resolver is configured.")
            connectivity = facts.get("networkmanager_connectivity")
            if connectivity in {"none", "portal", "limited"}:
                problems.append(f"NetworkManager's last connectivity result is {connectivity}.")
            if result.state in {"completed", "partial"} and problems:
                findings = (self._finding(
                    session, source_id=source_id, finding_type="network-observations",
                    category="network", severity="attention", title="Network observations need review",
                    summary=" ".join(problems) + " These local observations do not prove that every internet service is reachable.",
                    evidence=facts, resources=("network-manager", "default-route", "dns-resolver"),
                    next_step=NextStep.navigation("network", reason_code="review-network-state"),
                    evidence_quality="limited" if result.state == "partial" else "supported",
                ),)
            state = result.state if result.state != "completed" or findings else "empty"
            return adapt_structured_source(
                profile_id=session.profile_id, variant=session.variant, source_id=source_id,
                state=state, started_at=started_at, completed_at=self.clock(),
                facts=facts if state != "unavailable" else None, findings=findings,
                reason_code=result.reason_code,
                message="Some network observations are unknown; no external traffic test was run." if result.reason_code else "",
            )

        raw_id = str(parameters.get("application_id", ""))
        scope = str(parameters.get("application_scope", "rpm"))
        source = "rpm" if scope == "rpm" else "flatpak"
        installation = (
            scope.partition(":")[2]
            if scope.startswith("flatpak-installation:")
            else "system" if scope in {"rpm", "flatpak-system"} else "user"
        )
        identity = ApplicationIdentity(source, raw_id, installation)
        launch_attempted = bool(parameters.get("launch_attempted", False))
        result = probe.collect_application(
            identity,
            launch_attempted=launch_attempted and source_id == "application-journal",
            cancellation=cancellation,
            budget=8.0,
        )
        probe_facts = {
            **result.facts,
            "probe_availability": result.availability,
            "probe_errors": result.errors,
        }
        if source_id == "application-inventory":
            installed = probe_facts.get("installed")
            resource = f"{scope}:{raw_id}"
            if result.state in {"completed", "partial"} and installed is False:
                findings = (self._finding(
                    session, source_id=source_id, finding_type="application-not-found",
                    category="applications", severity="attention", title="The selected application installation was not found",
                    summary="The exact selected RPM package or Flatpak reference was not reported as installed.",
                    evidence={"installed": False, "scope": scope}, resources=(resource,),
                    next_step=NextStep.navigation("software:apps", {"application_id": raw_id}, reason_code="review-application-inventory"),
                ),)
            state = result.state if result.state != "completed" or findings else "empty"
            facts = {key: probe_facts[key] for key in (
                "installed", "probe_availability", "probe_errors",
            ) if key in probe_facts}
        else:
            errors = probe_facts.get("recent_error_count")
            if launch_attempted and result.state in {"completed", "partial"} and isinstance(errors, int) and errors > 0:
                findings = (self._finding(
                    session, source_id=source_id, finding_type="application-recent-errors",
                    category="applications", severity="attention", title="Recent application errors were found",
                    summary=f"The user's recent journal contains {errors} error-level entries matching this application. Review the app's output and logs before drawing a conclusion.",
                    evidence={"recent_error_count": errors, "recent_matching_entry_count": probe_facts.get("recent_matching_entry_count")},
                    resources=(f"{scope}:{raw_id}",),
                    next_step=NextStep.navigation("software:apps", {"application_id": raw_id}, reason_code="review-application-inventory"),
                    evidence_quality="limited",
                ),)
            state = result.state if result.state != "completed" else "completed" if findings else "empty"
            facts = {key: probe_facts.get(key) for key in (
                "recent_error_count", "recent_warning_count", "recent_matching_entry_count",
                "recent_metadata_match_count", "recent_message_match_count", "probe_availability", "probe_errors",
            )}
            facts["collection_requested"] = launch_attempted
        return adapt_structured_source(
            profile_id=session.profile_id, variant=session.variant, source_id=source_id,
            state=state, started_at=started_at, completed_at=self.clock(),
            facts=facts if state != "unavailable" else None, findings=findings,
            reason_code=result.reason_code,
            message="Some application evidence is unknown. Raw logs were not retained." if result.reason_code else "",
        )
