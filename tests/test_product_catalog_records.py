"""Destination-record composition and inert handoff contract tests."""

from __future__ import annotations

import hashlib
import json
import unittest

from core.catalog_models import CapabilityState, NativeHandoffId
from core.product_catalog import CATALOG_DATA, catalog_entry, catalog_routes


_V27_PROJECTION_HASHES = {
    "plugins": "43ba43a31963c5a26ee37c8271be674ebb7ee32023ab284ae740e1c6e1235845",
    "routes": "918bfd05b8cd08f39dcd1d5395959d89f8aead83f1c7a8b17ac5a318102dcc12",
    "placements": "e9c51932a14d89ede32bbc53df9aaf9743004b0b0e30512ee3b2446c1aa51387",
    "sections": "50a511235068f91722d63781bf6370486229d064e63a29af5594446695e83ac9",
    "destinations": "0a58f8d50f6a30c580feb7b3f658a3afc67b50b93a7c29cd684ccda95ee6f318",
}
_V27_ROUTE_ORDER_HASH = "341b383dbef96d2b7e401eca5a5dbd1706ae760855eed0730c58594cb28c65ea"


def _serialized_hash(records) -> str:
    serialized = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class TestDestinationOwnedCatalogRecords(unittest.TestCase):
    def test_serialized_projections_remain_exact(self):
        for key, expected_hash in _V27_PROJECTION_HASHES.items():
            with self.subTest(projection=key):
                self.assertEqual(_serialized_hash(CATALOG_DATA[key]), expected_hash)

    def test_route_order_and_identity_remain_exact(self):
        route_ids = tuple(route.id for route in catalog_routes())

        self.assertEqual(len(route_ids), 45)
        self.assertEqual(len(set(route_ids)), 45)
        self.assertEqual(_serialized_hash(route_ids), _V27_ROUTE_ORDER_HASH)

    def test_specialist_settings_uses_current_plain_language(self):
        route = next(
            record
            for record in CATALOG_DATA["routes"]
            if record["id"] == "settings:advanced"
        )
        section = next(
            record
            for record in CATALOG_DATA["sections"]
            if record["id"] == "advanced"
            and record["destination_id"] == "settings"
        )
        self.assertEqual(route["label"], "Specialist Tools")
        self.assertEqual(section["label"], "Specialist Tools")

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
