"""Compatibility wrapper for Support Bundle v4 imports."""

from __future__ import annotations

from core.export.support_bundle_v5 import SupportBundleV5


class SupportBundleV4(SupportBundleV5):
    """Backward-compatible import path for existing support-bundle consumers."""

    pass
