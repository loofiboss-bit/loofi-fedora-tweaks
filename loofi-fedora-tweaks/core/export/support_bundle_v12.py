"""Continuity support bundle with bounded Trusted Change Journal evidence."""

from __future__ import annotations

from typing import Any, Dict, cast

from core.export.support_bundle_v11 import SupportBundleV11


class SupportBundleV12(SupportBundleV11):
    """Preserve prior evidence and add redacted source readiness and events."""

    BUNDLE_SCHEMA = "20.0.0-continuity-support-v12"

    @classmethod
    def generate_bundle(cls, target: str = "44") -> Dict[str, Any]:
        from core.change_journal import ChangeJournalService

        bundle = super().generate_bundle(target=target)
        snapshot = ChangeJournalService().snapshot(limit=50, refresh=True)
        payload = snapshot.to_dict()
        bundle["v"] = cls.BUNDLE_SCHEMA
        bundle["schema"] = cls.BUNDLE_SCHEMA
        bundle["support_bundle_version"] = 12
        bundle["change_journal"] = {
            "schema": payload["schema"],
            "generated_at": payload["generated_at"],
            "truncated": payload["truncated"],
            "events": payload["events"],
            "sources": payload["sources"],
            "event_limit": 50,
            "raw_command_output_included": False,
            "recovery_commands_included": False,
        }
        return cast(Dict[str, Any], cls._redact(bundle))
