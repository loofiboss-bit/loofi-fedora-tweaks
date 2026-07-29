"""Authenticated retrieval-only troubleshooting API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.troubleshooting.inspection import (
    INTERFACE_SCHEMA_ID,
    INTERFACE_SCHEMA_VERSION,
    TroubleshootingInspectionService,
    bounded_session_payload,
)
from core.troubleshooting.models import TroubleshootingSession
from core.troubleshooting.storage import UnsupportedFutureSessionSchema
from utils.auth import AuthManager


def _response(
    session: TroubleshootingSession | None,
) -> dict[str, object]:
    return {
        "schema_id": INTERFACE_SCHEMA_ID,
        "schema_version": INTERFACE_SCHEMA_VERSION,
        "read_only": True,
        "source_status": "available" if session is not None else "empty",
        "session": (
            bounded_session_payload(session)
            if session is not None
            else None
        ),
    }


def get_latest_troubleshooting_session(
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return the latest retained session without collecting or persisting."""
    try:
        return _response(TroubleshootingInspectionService().latest())
    except UnsupportedFutureSessionSchema as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Troubleshooting session storage is unavailable.",
        ) from exc


def get_troubleshooting_session(
    session_id: str,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Return one known bounded session without exposing collection."""
    try:
        session = TroubleshootingInspectionService().require(session_id)
    except UnsupportedFutureSessionSchema as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OSError, TypeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Troubleshooting session storage is unavailable.",
        ) from exc
    return _response(session)


def get_troubleshooting_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/troubleshooting",
        tags=["troubleshooting"],
    )
    router.add_api_route(
        "/latest",
        get_latest_troubleshooting_session,
        methods=["GET"],
    )
    router.add_api_route(
        "/sessions/{session_id}",
        get_troubleshooting_session,
        methods=["GET"],
    )
    return router


router = get_troubleshooting_router()
