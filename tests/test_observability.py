"""v19 compatibility gate for the established v18 observability envelope."""

from __future__ import annotations

import unittest

from core.observability.snapshot import HealthSnapshot
from core.system_check.models import SystemCheckResult


class TestObservabilityCompatibility(unittest.TestCase):
    def test_v18_snapshot_without_system_check_remains_readable(self):
        snapshot = HealthSnapshot.from_dict({
            "schema_version": 1,
            "timestamp": 10.0,
            "app_version": "18.0.0",
            "app_codename": "Haven",
            "fedora_target": "44",
            "atomic": False,
            "daily_maintenance": {"cards": []},
            "action_center_summary": {"candidate_count": 0},
        })

        self.assertEqual(snapshot.schema_version, 1)
        self.assertNotIn("system_check", snapshot.daily_maintenance)

    def test_system_check_uses_nested_v18_compatible_envelope(self):
        result = SystemCheckResult(
            "check-1",
            "system-check-quick-v1",
            "completed",
            False,
            10.0,
            11.0,
        )

        snapshot = HealthSnapshot.from_system_check(result)
        encoded = snapshot.to_dict(privacy_safe=False)
        decoded = HealthSnapshot.from_dict(encoded)

        self.assertEqual(encoded["schema_version"], 1)
        self.assertEqual(
            decoded.daily_maintenance["system_check"]["check_id"],
            "check-1",
        )


if __name__ == "__main__":
    unittest.main()
