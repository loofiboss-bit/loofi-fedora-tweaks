"""Read-only profile inspection API routes."""

from fastapi import APIRouter, Depends
from utils.auth import AuthManager
from utils.profiles import ProfileManager

router = APIRouter(prefix="/api", tags=["profiles"])


@router.get("/profiles")
def list_profiles(_auth: str = Depends(AuthManager.verify_bearer_token)):
    """Return available profiles and currently active key."""
    return {
        "profiles": ProfileManager.list_profiles(),
        "active_profile": ProfileManager.get_active_profile(),
    }


@router.get("/profiles/export-all")
def export_all_profiles(
    include_builtins: bool = False,
    _auth: str = Depends(AuthManager.verify_bearer_token),
):
    """Export all profiles as a bundle payload."""
    return ProfileManager.export_bundle_data(include_builtins=include_builtins)


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
