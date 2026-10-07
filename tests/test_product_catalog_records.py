"""Destination-record composition and inert handoff contract tests."""

from __future__ import annotations

import hashlib
import json
import unittest

from core.catalog_models import CapabilityState, NativeHandoffId
from core.product_catalog import CATALOG_DATA, catalog_entry, catalog_routes


_CONTROL_CENTER_PROJECTION_HASHES = {
    "plugins": "429a9fa0e28102ca6807a5ab9a603c2838c5f5eb91b40c22de2e0bd0bf35a142",
    "routes": "98edb6a54ab33d69366ba3e19cf36217bef073e7a79fc11a360556415f5e5e57",
    "placements": "f24a7d014468701104a87ef53b7924ac7bc3b3a2dc00ec6a4e7df21ee3729995",
    "sections": "99e0ce7f4c5200bda40e9aaac7fdeb7a8fba6cad589d1bf1bc10ed965b957d4d",
    "destinations": "ae763154940059012b92e64ae54039a75e99ad292fae70e4933f008288142a06",
}
_CONTROL_CENTER_ROUTE_ORDER_HASH = "692c167357b9a4ca8c94c7d64f885db0a187d3cb204ae0afdde38ab077d8fcce"


def _serialized_hash(records) -> str:
    serialized = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class TestDestinationOwnedCatalogRecords(unittest.TestCase):
    def test_serialized_projections_remain_exact(self):
        for key, expected_hash in _CONTROL_CENTER_PROJECTION_HASHES.items():
            with self.subTest(projection=key):
                self.assertEqual(_serialized_hash(CATALOG_DATA[key]), expected_hash)

    def test_route_order_and_identity_remain_exact(self):
        route_ids = tuple(route.id for route in catalog_routes())

        self.assertEqual(len(route_ids), 44)
        self.assertEqual(len(set(route_ids)), 44)
        self.assertEqual(_serialized_hash(route_ids), _CONTROL_CENTER_ROUTE_ORDER_HASH)

    def test_application_settings_uses_current_plain_language(self):
        route = next(
            record
            for record in CATALOG_DATA["routes"]
            if record["id"] == "settings:application"
        )
        section = next(
            record
            for record in CATALOG_DATA["sections"]
            if record["id"] == "application"
            and record["destination_id"] == "settings"
        )
        self.assertEqual(route["label"], "Application")
        self.assertEqual(section["label"], "Application")

    def test_native_handoff_metadata_is_limited_to_the_architecture_allowlist(self):
        handoffs = {
            placement["route_id"]: placement.get("native_handoff_id")
            for placement in CATALOG_DATA["placements"]
            if placement.get("native_handoff_id") is not None
        }

        self.assertEqual(
            handoffs,
            {
                "software:apps": NativeHandoffId.PLASMA_DISCOVER.value,
                "network:connections": NativeHandoffId.PLASMA_NETWORK_CONNECTIONS.value,
            },
        )
        self.assertEqual(
            catalog_entry("software:apps").placement.native_handoff_id,
            NativeHandoffId.PLASMA_DISCOVER,
        )

    def test_capability_states_are_data_only_presentation_values(self):
        self.assertEqual(
            {state.value for state in CapabilityState},
            {"supported", "read_only", "native_handoff", "manual_only", "unavailable", "pending_reboot"},
        )


if __name__ == "__main__":
    unittest.main()
