"""Canonical support-bundle writer and legacy schema adapters."""

from __future__ import annotations

from typing import Any, Mapping

from core.export.support_bundle_v11 import SupportBundleV11

MIN_SUPPORT_BUNDLE_VERSION = 2
CURRENT_SUPPORT_BUNDLE_VERSION = 11


class SupportBundleWriter(SupportBundleV11):
    """Current writer; versioned classes remain read adapters only."""


def import_legacy_bundle(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and copy a supported historical support-bundle payload."""
    version = payload.get("support_bundle_version")
    if (
        not isinstance(version, int)
        or version
        not in range(
            MIN_SUPPORT_BUNDLE_VERSION,
            CURRENT_SUPPORT_BUNDLE_VERSION + 1,
        )
    ):
        raise ValueError("Unsupported support bundle schema.")
    return dict(payload)
