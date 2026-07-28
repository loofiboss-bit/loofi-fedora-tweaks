"""Destination-record composition and inert handoff contract tests."""

from __future__ import annotations

import hashlib
import json
import unittest

from core.catalog_models import CapabilityState, NativeHandoffId
from core.product_catalog import CATALOG_DATA, catalog_entry, catalog_routes


_LEGACY_PROJECTION_HASHES = {
    "plugins": "4de0e1042361f087c983236cddd0bdc1cfd98931bbdcb48e3ba3a952cf959fb0",
    "routes": "400b721a36174970f4327694e5627b5990f58e9032095c4b42827e09e965c970",
    "placements": "092a027bcd33afb9b40b1c3bf8a51a7734677148dfc7cb91b82b01cc793238d5",
    "sections": "542de516155e36734421165fadb88ae934573e8d6ee2e28705217adf6433bd50",
    "destinations": "cc6df4c11cfbbae78f3e6f85d13b0a74f90cdd16d16550624ce8360619cddca4",
}
_LEGACY_ROUTE_ORDER_HASH = "c89ecb919719171982bf46a9ab5dfd0f49558b3f5386e01d58218e4630726560"


def _legacy_projection(records):
    """Remove V22-only inert fields before comparing the V21 projection."""
    return tuple(
        {
            key: value
            for key, value in record.items()
            if key != "native_handoff_id"
        }
        for record in records
    )


def _serialized_hash(records) -> str:
    serialized = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class TestDestinationOwnedCatalogRecords(unittest.TestCase):
    def test_legacy_serialized_projections_remain_exact(self):
        for key, expected_hash in _LEGACY_PROJECTION_HASHES.items():
            with self.subTest(projection=key):
                self.assertEqual(_serialized_hash(_legacy_projection(CATALOG_DATA[key])), expected_hash)

    def test_route_order_and_identity_remain_exact(self):
        route_ids = tuple(route.id for route in catalog_routes())

        self.assertEqual(len(route_ids), 81)
        self.assertEqual(len(set(route_ids)), 81)
        self.assertEqual(_serialized_hash(route_ids), _LEGACY_ROUTE_ORDER_HASH)

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
                "desktop:theming": NativeHandoffId.PLASMA_APPEARANCE.value,
                "desktop:display": NativeHandoffId.PLASMA_DISPLAY.value,
                "desktop:director": NativeHandoffId.PLASMA_WINDOW_MANAGEMENT.value,
            },
        )
        self.assertEqual(
            catalog_entry("desktop:display").placement.native_handoff_id,
            NativeHandoffId.PLASMA_DISPLAY,
        )

    def test_capability_states_are_data_only_presentation_values(self):
        self.assertEqual(
            {state.value for state in CapabilityState},
            {"supported", "read_only", "native_handoff", "manual_only", "unavailable", "pending_reboot"},
        )


if __name__ == "__main__":
    unittest.main()
