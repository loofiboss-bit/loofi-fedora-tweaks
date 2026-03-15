"""Profile management API routes (v24.0)."""

from typing import Any, Dict, FrozenSet

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from services.security import AuditLogger
from services.security.safety import SafetyManager
from utils.auth import AuthManager
from utils.profiles import ProfileManager

router = APIRouter()
READ_ONLY_ROUTE_PATHS: FrozenSet[str] = frozenset({"/profiles", "/profiles/export-all"})
MUTATING_ROUTE_PATHS: FrozenSet[str] = frozenset(
    {"/profiles/apply", "/profiles/import-all", "/profiles/import"}
)


def is_read_only_route_path(path: str) -> bool:
    """Return True when the profile API path is read-only."""
    if path in READ_ONLY_ROUTE_PATHS:
        return True

    return path.startswith("/profiles/") and path.endswith("/export")


def _enforce_safe_mode_for_mutation(action: str, params: Dict[str, Any]) -> AuditLogger:
    """Block mutating profile actions while Safe Mode is enabled."""
    audit = AuditLogger()
    block_reason = SafetyManager.api_mutation_block_reason(
        action,
        preview=False,
        pkexec=False,
    )
    if block_reason:
        audit.log(
            "api.profiles.blocked.safe_mode",
            params={**params, "action": action, "reason": "safe_mode_enabled"},
            exit_code=None,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=block_reason,
        )
    return audit


def _profile_count(bundle: Dict[str, Any]) -> int:
    """Return the number of profiles in an imported bundle payload."""
    profiles = bundle.get("profiles", [])
    if isinstance(profiles, list):
        return len(profiles)
    return 0


class ProfileApplyPayload(BaseModel):
    """Payload for profile application."""

    name: str = Field(..., description="Profile key")
    create_snapshot: bool = Field(True, description="Create snapshot before apply")


class ProfileImportPayload(BaseModel):
    """Payload for importing one profile."""

    profile: Dict[str, Any] = Field(..., description="Profile payload")
    overwrite: bool = Field(False, description="Overwrite custom profile if it exists")


class ProfileImportAllPayload(BaseModel):
    """Payload for importing profile bundles."""

    bundle: Dict[str, Any] = Field(..., description="Profile bundle payload")
    overwrite: bool = Field(False, description="Overwrite custom profiles if they exist")


@router.get("/profiles")
def list_profiles(_auth: str = Depends(AuthManager.verify_bearer_token)):
    """Return available profiles and currently active key."""
    return {
        "profiles": ProfileManager.list_profiles(),
        "active_profile": ProfileManager.get_active_profile(),
    }


@router.post("/profiles/apply", status_code=status.HTTP_200_OK)
def apply_profile(
    payload: ProfileApplyPayload,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Apply a profile with optional snapshot hook."""
    audit = _enforce_safe_mode_for_mutation(
        "profiles.apply",
        {
            "profile_name": payload.name,
            "create_snapshot": payload.create_snapshot,
        },
    )
    result = ProfileManager.apply_profile(
        payload.name,
        create_snapshot=payload.create_snapshot,
    )
    audit.log(
        "api.profiles.apply",
        params={
            "profile_name": payload.name,
            "create_snapshot": payload.create_snapshot,
            "success": result.success,
        },
        exit_code=0 if result.success else 1,
    )
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
    }


@router.get("/profiles/export-all")
def export_all_profiles(
    include_builtins: bool = False,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Export all profiles as a bundle payload."""
    return ProfileManager.export_bundle_data(include_builtins=include_builtins)


@router.post("/profiles/import-all", status_code=status.HTTP_200_OK)
def import_all_profiles(
    payload: ProfileImportAllPayload,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Import bundle payload."""
    audit = _enforce_safe_mode_for_mutation(
        "profiles.import_all",
        {
            "overwrite": payload.overwrite,
            "profile_count": _profile_count(payload.bundle),
        },
    )
    result = ProfileManager.import_bundle_data(
        payload.bundle,
        overwrite=payload.overwrite,
    )
    audit.log(
        "api.profiles.import_all",
        params={
            "overwrite": payload.overwrite,
            "profile_count": _profile_count(payload.bundle),
            "success": result.success,
        },
        exit_code=0 if result.success else 1,
    )
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
    }


@router.get("/profiles/{name}/export")
def export_profile(
    name: str,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Export one profile as payload."""
    payload = ProfileManager.export_profile_data(name)
    return payload or {
        "error": f"Profile '{name}' not found.",
    }


@router.post("/profiles/import", status_code=status.HTTP_200_OK)
def import_profile(
    payload: ProfileImportPayload,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Import one profile payload."""
    profile_name = payload.profile.get("name") or payload.profile.get("key") or "unknown"
    audit = _enforce_safe_mode_for_mutation(
        "profiles.import",
        {
            "profile_name": profile_name,
            "overwrite": payload.overwrite,
        },
    )
    result = ProfileManager.import_profile_data(
        payload.profile,
        overwrite=payload.overwrite,
    )
    audit.log(
        "api.profiles.import",
        params={
            "profile_name": profile_name,
            "overwrite": payload.overwrite,
            "success": result.success,
        },
        exit_code=0 if result.success else 1,
    )
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
    }
