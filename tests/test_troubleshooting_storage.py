"""Bounded, future-safe Compass session persistence."""

from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path

from core.state.inventory import StateInventory
from core.state.paths import StatePaths
from core.troubleshooting.lifecycle import finalize_session, new_session, start_session
from core.troubleshooting.storage import (
    STORE_SCHEMA_ID,
    TroubleshootingSessionStore,
    UnsupportedFutureSessionSchema,
)


class TestTroubleshootingStorage(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "troubleshooting_sessions.json"
        self.store = TroubleshootingSessionStore(self.path)

    @staticmethod
    def _session(session_id: str, completed_at: float):
        queued = new_session(
            "network_problem",
            "traditional",
            started_at=1.0,
            session_id=session_id,
        )
        running = start_session(queued, started_at=1.0)
        return finalize_session(
            running,
            completed_at=completed_at,
            source_results=(),
        )

    def test_explicit_terminal_save_is_atomic_private_and_round_trips(self):
        session = self._session(
            "12345678-1234-5678-9234-567812345678",
            2.0,
        )

        self.store.save(session)
        restored = self.store.read()

        self.assertTrue(restored.writable)
        self.assertEqual(restored.sessions, (session,))
        self.assertEqual(
            stat.S_IMODE(self.path.stat().st_mode),
            0o600,
        )
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_id"], STORE_SCHEMA_ID)

    def test_active_sessions_are_never_persisted(self):
        queued = new_session(
            "network_problem",
            "traditional",
            started_at=1.0,
            session_id="12345678-1234-5678-9234-567812345678",
        )

        with self.assertRaisesRegex(ValueError, "Active"):
            self.store.save(queued)
        self.assertFalse(self.path.exists())

    def test_store_retains_only_twenty_newest_sessions(self):
        for index in range(22):
            session_id = f"12345678-1234-5678-9234-{index:012d}"
            self.store.save(self._session(session_id, float(index + 2)))

        snapshot = self.store.read()

        self.assertEqual(len(snapshot.sessions), 20)
        self.assertEqual(
            snapshot.sessions[0].session_id,
            "12345678-1234-5678-9234-000000000021",
        )
        self.assertEqual(
            snapshot.sessions[-1].session_id,
            "12345678-1234-5678-9234-000000000002",
        )

    def test_future_schema_is_read_only_and_never_rewritten(self):
        payload = {
            "schema_id": STORE_SCHEMA_ID,
            "schema_version": 99,
            "sessions": [{"future": True}],
        }
        original = json.dumps(payload, sort_keys=True)
        self.path.write_text(original, encoding="utf-8")
        session = self._session(
            "12345678-1234-5678-9234-567812345678",
            2.0,
        )

        snapshot = self.store.read()
        self.assertFalse(snapshot.writable)
        self.assertEqual(snapshot.reason_code, "future-schema-read-only")
        with self.assertRaises(UnsupportedFutureSessionSchema):
            self.store.save(session)
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_malformed_and_oversized_stores_fail_closed(self):
        self.path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "JSON object"):
            self.store.read()

        self.path.write_text("x" * (512 * 1024 + 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "file size"):
            self.store.read()

    def test_state_inventory_registers_private_bounded_session_domain(self):
        paths = StatePaths(
            self.root / "config",
            self.root / "data",
            self.root / "cache",
            self.root / "runtime",
        )
        domain = StateInventory(paths).get("troubleshooting_sessions")

        self.assertEqual(domain.owner, "troubleshooting")
        self.assertEqual(domain.path, paths.data / "troubleshooting_sessions.json")
        self.assertEqual(domain.schema_id, STORE_SCHEMA_ID)
        self.assertEqual(domain.schema_version, 1)
        self.assertEqual(domain.retention, "20 sessions")
        self.assertEqual(domain.sensitivity, "private")


if __name__ == "__main__":
    unittest.main()
