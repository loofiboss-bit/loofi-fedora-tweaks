"""Fedora deployment capability and platform profiling contracts."""

from core.platform.capabilities import ACTION_CAPABILITIES, ActionCapability, capability_for
from core.platform.profile import (
    DeploymentBackend,
    DesktopEnvironment,
    PlatformProfile,
    SessionType,
    detect_desktop,
    detect_deployment_backend,
    detect_platform_profile,
    detect_session_type,
)

__all__ = [
    "ACTION_CAPABILITIES",
    "ActionCapability",
    "DeploymentBackend",
    "DesktopEnvironment",
    "PlatformProfile",
    "SessionType",
    "capability_for",
    "detect_desktop",
    "detect_deployment_backend",
    "detect_platform_profile",
    "detect_session_type",
]
