"""System information API routes.

Every route requires Bearer JWT authentication.
"""

from core.agents import AgentRegistry
from core.change_journal.models import ChangeSource
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import cast
from services.system import SystemManager
from utils.auth import AuthManager
from utils.monitor import SystemMonitor


class HealthResponse(BaseModel):
    """Health response payload — no version info for unauthenticated callers."""

    status: str


def get_health(_auth: str = Depends(AuthManager.verify_bearer_token)):
    """Authenticated basic health check without a version leak."""
    return HealthResponse(status="ok")


def get_info(
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return system info and health metrics (authenticated)."""
    from version import __version__, __version_codename__

    health = SystemMonitor.get_system_health()
    return {
        "version": __version__,
        "codename": __version_codename__,
        "system_type": "Atomic" if SystemManager.is_atomic() else "Traditional",
        "package_manager": SystemManager.get_package_manager(),
        "health": {
            "hostname": health.hostname,
            "uptime": health.uptime,
            "memory": {
                "used": health.memory.used_human if health.memory else None,
                "total": health.memory.total_human if health.memory else None,
                "percent": health.memory.percent_used if health.memory else None,
                "status": health.memory_status,
            },
            "cpu": {
                "load_1min": health.cpu.load_1min if health.cpu else None,
                "load_5min": health.cpu.load_5min if health.cpu else None,
                "load_15min": health.cpu.load_15min if health.cpu else None,
                "cores": health.cpu.core_count if health.cpu else None,
                "load_percent": health.cpu.load_percent if health.cpu else None,
                "status": health.cpu_status,
            },
        },
    }


def get_agents(
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return agent configs and runtime states (authenticated)."""
    registry = AgentRegistry.instance()
    agents = registry.list_agents()
    return {
        "agents": [a.to_dict() for a in agents],
        "states": [registry.get_state(a.agent_id).to_dict() for a in agents],
        "summary": registry.get_agent_summary(),
    }


def get_current_health_snapshot(
    target: str = FEDORA_RELEASE_POLICY.stable_target,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Collect one bounded snapshot without persisting API-triggered state."""
    from core.observability import HealthSnapshot

    snapshot = HealthSnapshot.collect(fedora_target=target)
    return {"schema_version": 1, "read_only": True, "snapshot": snapshot.to_dict()}


def get_health_timeline(
    limit: int = 10,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return bounded v12 health timeline data."""
    from core.observability import HealthTimelineStore

    return HealthTimelineStore().export(limit=max(1, min(limit, 30)))


def get_observability_status(
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return the canonical read-only collector and storage status."""
    from core.observability import ObservabilityService

    return ObservabilityService().status(source="api").to_dict()


def get_state_status(
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Authenticated, read-only State Doctor endpoint."""
    from core.state import StateDoctor

    return StateDoctor().run()


def get_latest_system_check(
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return only the latest saved privacy-safe System Check result."""
    from core.observability import HealthTimelineStore
    from core.privacy import redact_payload
    from core.system_check.comparison import results_from_snapshots

    store = HealthTimelineStore()
    results = results_from_snapshots(store.load())
    latest = results[-1].to_dict() if results else None
    if latest is not None:
        latest["findings"] = list(latest.get("findings", []))[:50]
        latest["source_errors"] = list(
            latest.get("source_errors", [])
        )[:10]
    return {
        "schema_id": "loofi.system-check",
        "schema_version": 1,
        "read_only": True,
        "result": redact_payload(latest) if latest is not None else None,
        "source_status": (
            "unavailable"
            if store.last_error
            else ("available" if latest is not None else "empty")
        ),
    }


def get_activity(
    limit: int = 50,
    source: str | None = None,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return a bounded, read-only Trusted Change Journal snapshot."""
    from core.change_journal import ChangeJournalService

    allowed = {
        "action_center",
        "dnf5",
        "rpm_ostree",
        "flatpak",
        "fwupd",
        "loofi_app",
        "session",
    }
    if source is not None and source not in allowed:
        raise HTTPException(status_code=400, detail="Unknown activity source.")
    selected = [cast(ChangeSource, source)] if source else None
    return {
        **ChangeJournalService().snapshot(
            limit=max(1, min(limit, 100)),
            sources=selected,
        ).to_dict(),
        "read_only": True,
    }


def get_activity_event(
    event_id: str,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return one inert activity event without exposing mutation endpoints."""
    from core.change_journal import ChangeJournalService

    event = ChangeJournalService().get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Activity event not found.")
    return {
        "schema": "loofi.change-journal/v1",
        "read_only": True,
        "event": event.to_dict(),
    }


def get_system_router() -> APIRouter:
    r = APIRouter(prefix="/api", tags=["system"])
    r.add_api_route("/health", get_health, methods=["GET"], response_model=HealthResponse)
    r.add_api_route("/info", get_info, methods=["GET"])
    r.add_api_route("/agents", get_agents, methods=["GET"])
    r.add_api_route("/observability/current", get_current_health_snapshot, methods=["GET"])
    r.add_api_route("/observability/timeline", get_health_timeline, methods=["GET"])
    r.add_api_route("/observability/status", get_observability_status, methods=["GET"])
    r.add_api_route("/state/status", get_state_status, methods=["GET"])
    r.add_api_route("/system-check/latest", get_latest_system_check, methods=["GET"])
    r.add_api_route("/activity", get_activity, methods=["GET"])
    r.add_api_route("/activity/{event_id}", get_activity_event, methods=["GET"])
    return r


router = get_system_router()
