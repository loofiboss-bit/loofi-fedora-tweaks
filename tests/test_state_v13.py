"""Failure-path and contract coverage for v13 Anchor state integrity."""

import hashlib
import json
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core.state.atomic_io import StateBusyError, StateWriteError, advisory_lock, atomic_write_json
from core.state.backup import InvalidStateArchive, StateArchiveService
from core.state.doctor import StateDoctor
from core.state.inventory import StateInventory
from core.state.paths import StatePaths
from core.state.schema import SchemaRegistry, UnsupportedFutureSchema


class TestStatePathsAndInventory(TestCase):
    def test_temporary_xdg_roots_never_touch_home(self):
        paths = StatePaths.from_environment({
            "HOME": "/forbidden", "XDG_CONFIG_HOME": "/tmp/cfg", "XDG_DATA_HOME": "/tmp/data",
            "XDG_CACHE_HOME": "/tmp/cache", "XDG_RUNTIME_DIR": "/tmp/run",
        })
        inventory = StateInventory(paths)
        self.assertTrue(all("/forbidden" not in str(domain.path) for domain in inventory.all()))
        self.assertEqual(len(inventory.all()), 14)
        self.assertEqual(inventory.get("audit_log").path, paths.config / "audit.jsonl")
        self.assertEqual(inventory.get("action_log").path, paths.data / "action_log.jsonl")


class TestAtomicIO(TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_atomic_write_creates_private_file_and_backup(self):
        atomic_write_json(self.path, {"value": 1})
        atomic_write_json(self.path, {"value": 2})
        self.assertEqual(json.loads(self.path.read_text()), {"value": 2})
        self.assertEqual(json.loads(self.path.with_suffix(".json.lkg").read_text()), {"value": 1})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    @patch("core.state.atomic_io.os.replace", side_effect=OSError("disk full"))
    def test_replace_failure_preserves_canonical_file(self, _replace):
        self.path.write_text('{"value": 1}', encoding="utf-8")
        with self.assertRaises(StateWriteError):
            atomic_write_json(self.path, {"value": 2})
        self.assertEqual(json.loads(self.path.read_text()), {"value": 1})

    def test_concurrent_lock_returns_typed_busy_error(self):
        with advisory_lock(self.path):
            with self.assertRaises(StateBusyError):
                with advisory_lock(self.path, timeout=0):
                    pass


class TestSchemaRegistry(TestCase):
    def setUp(self):
        self.registry = SchemaRegistry()
        self.registry.register("example", 2)
        self.registry.add_migration("example", 0, lambda value: {**value, "schema_version": 1, "one": True})
        self.registry.add_migration("example", 1, lambda value: {**value, "schema_version": 2, "two": True})

    def test_ordered_migration_is_idempotent(self):
        migrated = self.registry.migrate("example", {})
        self.assertEqual(self.registry.migrate("example", migrated), migrated)

    def test_dry_run_does_not_return_migrated_payload(self):
        self.assertEqual(self.registry.migrate("example", {}, dry_run=True), {})

    def test_future_schema_is_read_only(self):
        with self.assertRaises(UnsupportedFutureSchema):
            self.registry.migrate("example", {"schema_version": 3})


class TestStateDoctor(TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.inventory = StateInventory(StatePaths(root / "cfg", root / "data", root / "cache", root / "run"))

    def tearDown(self):
        self.temp.cleanup()

    def test_doctor_is_read_only_and_reports_corrupt_json(self):
        target = self.inventory.get("settings").path
        target.parent.mkdir(parents=True)
        target.write_text("{broken", encoding="utf-8")
        before = target.read_bytes()
        result = StateDoctor(self.inventory).run()
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["findings"][0]["domain"], "settings")


class TestStateArchive(TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.inventory = StateInventory(StatePaths(root / "cfg", root / "data", root / "cache", root / "run"))
        self.service = StateArchiveService(self.inventory)
        self.settings = self.inventory.get("settings").path
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{"theme":"dark"}', encoding="utf-8")
        self.archive = root / "state.zip"

    def tearDown(self):
        self.temp.cleanup()

    def test_backup_plan_apply_round_trip_and_rollback(self):
        manifest = self.service.backup(self.archive, ["settings", "auth_state"])
        self.assertEqual([entry["domain"] for entry in manifest["entries"]], ["settings"])
        self.settings.write_text('{"theme":"light"}', encoding="utf-8")
        plan = self.service.plan_restore(self.archive)
        result = self.service.apply_restore(self.archive, plan["plan_id"])
        self.assertEqual(self.settings.read_text(), '{"theme":"dark"}')
        self.assertTrue(Path(result["rollback_archive"]).exists())

    def test_tampered_payload_is_rejected(self):
        self.service.backup(self.archive, ["settings"])
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("state/settings/settings.json", b"tampered")
        with self.assertRaises(InvalidStateArchive):
            self.service.plan_restore(self.archive)

    def test_zip_slip_is_rejected(self):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("../escape", b"bad")
            archive.writestr("manifest.json", json.dumps({"archive_schema_version": 1, "entries": []}))
        with self.assertRaises(InvalidStateArchive):
            self.service.plan_restore(self.archive)

    def test_hash_mismatch_is_rejected(self):
        content = b"state"
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("state/settings/settings.json", content)
            archive.writestr("manifest.json", json.dumps({"archive_schema_version": 1, "entries": [{
                "domain": "settings", "path": "state/settings/settings.json", "sha256": hashlib.sha256(b"other").hexdigest(),
                "schema_id": "loofi.settings", "schema_version": 1,
            }]}))
        with self.assertRaises(InvalidStateArchive):
            self.service.plan_restore(self.archive)
