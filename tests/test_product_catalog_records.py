"""Destination-record composition and inert handoff contract tests."""

from __future__ import annotations

import hashlib
import json
import unittest

from core.catalog_models import CapabilityState, NativeHandoffId
from core.product_catalog import CATALOG_DATA, catalog_entry, catalog_routes


_CONTROL_CENTER_PROJECTION_HASHES = {
    "plugins": "6e8074e7430b27a1249fb46181b9a3f0fc2f2e190b1a8dcd3d93cc28710115e1",
    "routes": "7d3f231ff3e6d1fa3a51b45fc6227ad6fece7aaeb7d8931ee9d4666209a56e70",
    "placements": "fe2beae733554d45426326feeab0a337df4a7b544e214fa02a9b9d5c674fed69",
    "sections": "768112e0887eff728e02ac306a2ebf0495996e2b6565ba76177c05b3eab39f93",
    "destinations": "7b3ece4a4d2f5d4b6c325424090a0afcfa3980fa9de753d75475656cd7aa5901",
}
_CONTROL_CENTER_ROUTE_ORDER_HASH = "669b82b9c80c80be0b8cc6f5e481cad61e165482dfc50a4e0fcacbaec26e75d9"


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

        self.assertEqual(len(route_ids), 45)
        self.assertEqual(len(set(route_ids)), 45)
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
