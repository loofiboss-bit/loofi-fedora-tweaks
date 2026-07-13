"""Anchor support bundle with canonical state and observability status."""

from __future__ import annotations

from typing import Any, Dict, cast

from core.export.support_bundle_v8 import SupportBundleV8


class SupportBundleV9(SupportBundleV8):
    """Preserve v5-v8 fields while adding v13 state integrity evidence."""

    BUNDLE_SCHEMA = "13.0.0-anchor-support-v9"

    @classmethod
    def generate_bundle(cls, target: str = "44") -> Dict[str, Any]:
        from core.observability import ObservabilityService
        from core.state import StateDoctor

        bundle = super().generate_bundle(target=target)
        bundle["v"] = cls.BUNDLE_SCHEMA
        bundle["schema"] = cls.BUNDLE_SCHEMA
        bundle["support_bundle_version"] = 9
        bundle["state_integrity"] = StateDoctor().run()
        bundle["observability_status"] = ObservabilityService().status(source="support-bundle").to_dict()
        bundle["state_archive_policy"] = {
            "private_domains_included": False,
            "raw_logs_included": False,
            "restore_requires_plan": True,
            "rollback_archive_before_apply": True,
        }
        return cast(Dict[str, Any], cls._redact(bundle))
