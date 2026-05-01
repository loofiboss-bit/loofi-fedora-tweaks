"""Compatibility wrapper for Support Bundle v3 imports."""

from __future__ import annotations

from core.export.support_bundle_v4 import SupportBundleV4


class SupportBundleV3(SupportBundleV4):
    """Backward-compatible import path for existing support-bundle consumers."""

    pass
