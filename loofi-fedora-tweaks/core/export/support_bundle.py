"""Canonical support-bundle writer and legacy schema adapters."""

from __future__ import annotations

from typing import Any, Mapping

from core.export.support_bundle_v10 import SupportBundleV10


class SupportBundleWriter(SupportBundleV10):
    """Current writer; versioned classes remain read adapters only."""


def import_legacy_bundle(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and copy a supported historical support-bundle payload."""
    version = payload.get("support_bundle_version")
    if not isinstance(version, int) or version not in range(2, 11):
        raise ValueError("Unsupported support bundle schema.")
    return dict(payload)
