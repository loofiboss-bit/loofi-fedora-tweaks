"""Current support bundle import path for Harbor diagnostics."""

from core.export.support_bundle_v5 import SupportBundleV5


class SupportBundleV7(SupportBundleV5):
    """Backward-compatible subclass for the v7 support bundle schema."""
