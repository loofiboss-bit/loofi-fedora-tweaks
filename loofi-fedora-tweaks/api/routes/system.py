"""System information API routes.

Every route requires Bearer JWT authentication.
"""

from core.agents import AgentRegistry
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from services.system import SystemManager
from utils.auth import AuthManager
from utils.monitor import SystemMonitor

router = APIRouter(prefix="/api", tags=["system"])


class HealthResponse(BaseModel):
    """Health response payload — no version info for unauthenticated callers."""

    status: str


@router.get("/health", response_model=HealthResponse)
def get_health(_auth: str = Depends(AuthManager.verify_bearer_token)):
    """Authenticated basic health check without a version leak."""
    return HealthResponse(status="ok")


@router.get("/info")
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


@router.get("/agents")
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


@router.get("/observability/current")
def get_current_health_snapshot(
    target: str = FEDORA_RELEASE_POLICY.stable_target,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Collect one bounded snapshot without persisting API-triggered state."""
    from core.observability import HealthSnapshot

    snapshot = HealthSnapshot.collect(fedora_target=target)
    return {"schema_version": 1, "read_only": True, "snapshot": snapshot.to_dict()}


@router.get("/observability/timeline")
def get_health_timeline(
    limit: int = 10,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return bounded v12 health timeline data."""
    from core.observability import HealthTimelineStore

    return HealthTimelineStore().export(limit=max(1, min(limit, 30)))


@router.get("/observability/status")
def get_observability_status(
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return the canonical read-only collector and storage status."""
    from core.observability import ObservabilityService

    return ObservabilityService().status(source="api").to_dict()


@router.get("/state/status")
def get_state_status(
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Authenticated, read-only State Doctor endpoint."""
    from core.state import StateDoctor

    return StateDoctor().run()


@router.get("/system-check/latest")
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
