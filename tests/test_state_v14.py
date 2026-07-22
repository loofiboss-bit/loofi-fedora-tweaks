"""v14 Helm regression tests for state, restore and observability hardening."""

import hashlib
import json
import stat
import tempfile
import threading
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.observability.service import ObservabilityService
from core.observability.snapshot import HealthSnapshot
from core.observability.timeline import HealthTimelineStore
from core.state import backup as backup_module
from core.state.atomic_io import atomic_write_bytes as real_atomic_write_bytes
from core.state.backup import InvalidStateArchive, StateArchiveService, StateRestoreError
from core.state.doctor import StateDoctor
from core.state.inventory import StateInventory
from core.state.paths import StatePaths


def _snapshot(timestamp: float) -> HealthSnapshot:
    return HealthSnapshot(
        timestamp=timestamp,
        app_version="14.0.0",
        app_codename="Helm",
        fedora_target="44",
        atomic=False,
        daily_maintenance={"cards": []},
        action_center_summary={},
    )


class StateV14Case(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.paths = StatePaths(root / "cfg", root / "data", root / "cache", root / "run")
        self.inventory = StateInventory(self.paths)

    def tearDown(self):
        self.temp.cleanup()


class TestSchemaAwareState(StateV14Case):
    def test_doctor_reports_future_schema_without_mutating_it(self):
        target = self.inventory.get("health_snapshots").path
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps({"schema_version": 99, "snapshots": []}), encoding="utf-8")
        before = target.read_bytes()

        result = StateDoctor(self.inventory).run()

        self.assertEqual(target.read_bytes(), before)
        findings = [item for item in result["findings"] if item["domain"] == "health_snapshots"]
        self.assertIn("State uses a newer schema and is read-only", [item["summary"] for item in findings])

    def test_doctor_understands_action_run_jsonl_schema_key(self):
        target = self.inventory.get("action_runs").path
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps({"action_run_schema_version": 4, "run_id": "future"}) + "\n", encoding="utf-8")

        result = StateDoctor(self.inventory).run()

        findings = [item for item in result["findings"] if item["domain"] == "action_runs"]
        self.assertIn("State uses a newer schema and is read-only", [item["summary"] for item in findings])

    def test_doctor_accepts_supported_action_run_v2_migration(self):
        target = self.inventory.get("action_runs").path
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps({"action_run_schema_version": 2, "run_id": "legacy"}) + "\n", encoding="utf-8")

        result = StateDoctor(self.inventory).run()

        findings = [item for item in result["findings"] if item["domain"] == "action_runs"]
        summaries = [item["summary"] for item in findings]
        self.assertNotIn("State requires an unavailable migration", summaries)

    def test_timeline_migrates_supported_legacy_document_with_runner(self):
        target = self.inventory.get("health_snapshots").path
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps({"snapshots": [_snapshot(1).to_dict()]}), encoding="utf-8")

        loaded = HealthTimelineStore(target).load()

        self.assertEqual([item.timestamp for item in loaded], [1])
        self.assertEqual(json.loads(target.read_text())["schema_version"], 1)
        self.assertTrue(target.with_suffix(".json.migration.json").exists())

    def test_future_timeline_is_never_overwritten(self):
        target = self.inventory.get("health_snapshots").path
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps({"schema_version": 2, "snapshots": []}), encoding="utf-8")
        before = target.read_bytes()
        store = HealthTimelineStore(target)

        self.assertEqual(store.load(), [])
        self.assertIn("future-schema-read-only", store.last_error)
        with self.assertRaises(ValueError):
            store.append(_snapshot(1))
        self.assertEqual(target.read_bytes(), before)


class TestTimelineConcurrency(StateV14Case):
    def test_append_locks_the_complete_read_modify_write(self):
        target = self.inventory.get("health_snapshots").path
        store = HealthTimelineStore(target, retention=20)
        threads = [threading.Thread(target=store.append, args=(_snapshot(float(index)),)) for index in range(10)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual([item.timestamp for item in store.load()], [float(index) for index in range(10)])


class TestObservabilityFacade(StateV14Case):
    def test_collect_snapshot_uses_facade_lease_and_records_owner_atomically(self):
        snapshot_store = MagicMock()
        snapshot_store.collect_and_append.return_value = _snapshot(1)
        lease = self.paths.runtime / "collector"
        service = ObservabilityService(snapshot_store=snapshot_store, lease_path=lease)

        result = service.collect_snapshot(target="45-preview", source="api")

        self.assertEqual(result.timestamp, 1)
        snapshot_store.collect_and_append.assert_called_once_with(fedora_target="45-preview")
        self.assertTrue(lease.read_text(encoding="utf-8").strip())
        self.assertTrue(lease.with_name("collector.lock").exists())


class TestRestorePlanBinding(StateV14Case):
    def setUp(self):
        super().setUp()
        self.service = StateArchiveService(self.inventory)
        self.settings = self.inventory.get("settings").path
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{"theme":"archive"}', encoding="utf-8")
        self.archive = Path(self.temp.name) / "state.zip"
        self.service.backup(self.archive, ["settings"])
        self.settings.write_text('{"theme":"baseline"}', encoding="utf-8")

    def test_plan_expires_after_thirty_minutes(self):
        plan = self.service.plan_restore(self.archive)

        with patch("core.state.backup.time.time", return_value=plan["expires_at"] + 1):
            with self.assertRaisesRegex(InvalidStateArchive, "expired"):
                self.service.apply_restore(self.archive, plan["plan_id"])
        self.assertEqual(self.settings.read_text(), '{"theme":"baseline"}')

    def test_target_drift_after_plan_is_rejected(self):
        plan = self.service.plan_restore(self.archive)
        self.settings.write_text('{"theme":"drifted"}', encoding="utf-8")

        with self.assertRaisesRegex(InvalidStateArchive, "target changed"):
            self.service.apply_restore(self.archive, plan["plan_id"])

    def test_archive_digest_change_after_plan_is_rejected(self):
        plan = self.service.plan_restore(self.archive)
        self.settings.write_text('{"theme":"other archive"}', encoding="utf-8")
        self.service.backup(self.archive, ["settings"])
        self.settings.write_text('{"theme":"baseline"}', encoding="utf-8")

        with self.assertRaisesRegex(InvalidStateArchive, "changed after planning"):
            self.service.apply_restore(self.archive, plan["plan_id"])


class TestRestoreRollback(StateV14Case):
    def test_inflight_domain_is_rolled_back_when_write_fails_after_replace(self):
        service = StateArchiveService(self.inventory)
        settings = self.inventory.get("settings").path
        settings.parent.mkdir(parents=True)
        settings.write_text('{"value":"archive"}', encoding="utf-8")
        archive = Path(self.temp.name) / "state.zip"
        service.backup(archive, ["settings"])
        settings.write_text('{"value":"baseline"}', encoding="utf-8")
        plan = service.plan_restore(archive)
        failed_after_replace = False

        def replace_then_fail(path, content, **kwargs):
            nonlocal failed_after_replace
            real_atomic_write_bytes(Path(path), content, **kwargs)
            if Path(path) == settings and not failed_after_replace:
                failed_after_replace = True
                raise OSError("injected post-replace failure")

        with patch("core.state.backup.atomic_write_bytes", side_effect=replace_then_fail):
            with self.assertRaisesRegex(StateRestoreError, "automatic rollback completed"):
                service.apply_restore(archive, plan["plan_id"])

        self.assertTrue(failed_after_replace)
        self.assertEqual(settings.read_text(), '{"value":"baseline"}')

    def test_partial_multi_domain_failure_rolls_back_applied_domains(self):
        service = StateArchiveService(self.inventory)
        settings = self.inventory.get("settings").path
        plugins = self.inventory.get("plugin_state").path
        settings.parent.mkdir(parents=True)
        settings.write_text('{"value":"archive settings"}', encoding="utf-8")
        plugins.write_text('{"value":"archive plugins"}', encoding="utf-8")
        archive = Path(self.temp.name) / "state.zip"
        service.backup(archive, ["settings", "plugin_state"])
        settings.write_text('{"value":"baseline settings"}', encoding="utf-8")
        plugins.write_text('{"value":"baseline plugins"}', encoding="utf-8")
        plan = service.plan_restore(archive)

        failed_second_target = False

        def fail_second_target(path, content, **kwargs):
            nonlocal failed_second_target
            if Path(path) == plugins and not failed_second_target:
                failed_second_target = True
                raise OSError("injected second-domain failure")
            return real_atomic_write_bytes(Path(path), content, **kwargs)

        with patch("core.state.backup.atomic_write_bytes", side_effect=fail_second_target):
            with self.assertRaisesRegex(StateRestoreError, "automatic rollback completed"):
                service.apply_restore(archive, plan["plan_id"])

        self.assertEqual(settings.read_text(), '{"value":"baseline settings"}')
        self.assertEqual(plugins.read_text(), '{"value":"baseline plugins"}')


class TestArchiveThreatValidation(StateV14Case):
    def test_older_domain_schema_is_rejected_instead_of_written_unmigrated(self):
        archive_path = Path(self.temp.name) / "legacy-schema.zip"
        domain = self.inventory.get("settings")
        content = b'{"schema_version":0}'
        name = f"state/{domain.id}/{domain.path.name}"
        entry = {
            "domain": domain.id,
            "path": name,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
            "schema_id": domain.schema_id,
            "schema_version": 0,
        }
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(name, content)
            archive.writestr("manifest.json", json.dumps({"archive_schema_version": 1, "entries": [entry]}))

        with self.assertRaisesRegex(InvalidStateArchive, "Incompatible state schema"):
            StateArchiveService(self.inventory).plan_restore(archive_path)

    def test_zip_symlink_is_rejected(self):
        archive_path = Path(self.temp.name) / "symlink.zip"
        link = zipfile.ZipInfo("state/settings/settings.json")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(link, b"target")
            archive.writestr("manifest.json", json.dumps({"archive_schema_version": 1, "entries": []}))

        with self.assertRaisesRegex(InvalidStateArchive, "Unsafe archive entry"):
            StateArchiveService(self.inventory).plan_restore(archive_path)

    def test_cumulative_uncompressed_limit_is_enforced(self):
        archive_path = Path(self.temp.name) / "oversized.zip"
        content = b"123456"
        entries = []
        with zipfile.ZipFile(archive_path, "w") as archive:
            for domain_id in ("settings", "plugin_state"):
                domain = self.inventory.get(domain_id)
                name = f"state/{domain.id}/{domain.path.name}"
                archive.writestr(name, content)
                entries.append({
                    "domain": domain.id,
                    "path": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                    "schema_id": domain.schema_id,
                    "schema_version": domain.schema_version,
                })
            archive.writestr("manifest.json", json.dumps({"archive_schema_version": 1, "entries": entries}))

        with patch.object(backup_module, "MAX_TOTAL_UNCOMPRESSED_BYTES", 10):
            with self.assertRaisesRegex(InvalidStateArchive, "Unsafe archive entry"):
                StateArchiveService(self.inventory).plan_restore(archive_path)

    def test_failed_backup_does_not_replace_existing_output(self):
        output = Path(self.temp.name) / "existing.zip"
        output.write_bytes(b"existing")
        settings = self.inventory.get("settings").path
        settings.parent.mkdir(parents=True)
        external = Path(self.temp.name) / "external.json"
        external.write_text("{}", encoding="utf-8")
        settings.symlink_to(external)

        with self.assertRaisesRegex(InvalidStateArchive, "symbolic link"):
            StateArchiveService(self.inventory).backup(output, ["settings"])
        self.assertEqual(output.read_bytes(), b"existing")


class TestArchiveValidationBranches(StateV14Case):
    def test_schema_detection_and_target_baselines(self):
        service = StateArchiveService(self.inventory)
        domain = self.inventory.get("settings")

        self.assertEqual(service._content_schema_version(domain, b'{"schema_version": 7}'), 7)
        self.assertEqual(service._content_schema_version(domain, b"not-json"), domain.schema_version)

        missing = Path(self.temp.name) / "missing.json"
        self.assertEqual(service._target_baseline(missing), {"exists": False, "sha256": None, "size": 0})
        directory = Path(self.temp.name) / "directory"
        directory.mkdir()
        with self.assertRaisesRegex(InvalidStateArchive, "not a regular file"):
            service._target_baseline(directory)
        link = Path(self.temp.name) / "link.json"
        link.symlink_to(missing)
        with self.assertRaisesRegex(InvalidStateArchive, "symbolic link"):
            service._target_baseline(link)

    def test_restore_plan_validation_rejects_each_binding_boundary(self):
        service = StateArchiveService(self.inventory)
        archive = Path(self.temp.name) / "archive.zip"
        actions = []
        binding = {"archive": str(archive.resolve()), "archive_sha256": "digest", "actions": actions}
        plan_id = service._plan_id(binding)
        base = {
            "schema_version": backup_module.RESTORE_PLAN_SCHEMA_VERSION,
            "plan_id": plan_id,
            **binding,
            "expires_at": 9999999999,
        }

        cases = [
            ({**base, "schema_version": 99}, "schema is unsupported"),
            ({**base, "plan_id": "0" * 24}, "identity mismatch"),
            ({**base, "archive": str(Path(self.temp.name) / "other.zip")}, "does not match archive path"),
            ({**base, "expires_at": "invalid"}, "expiry is invalid"),
            ({**base, "actions": "invalid"}, "modified after creation"),
        ]
        for plan, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(InvalidStateArchive, message):
                    service._validate_plan(plan, archive, plan_id)

    def test_apply_rejects_invalid_or_missing_plan_id(self):
        service = StateArchiveService(self.inventory)
        archive = Path(self.temp.name) / "archive.zip"

        with self.assertRaisesRegex(InvalidStateArchive, "plan id is invalid"):
            service.apply_restore(archive, "not-a-plan")
        with self.assertRaisesRegex(InvalidStateArchive, "missing or invalid"):
            service.apply_restore(archive, "0" * 24)

    def test_invalid_archive_shapes_are_rejected(self):
        service = StateArchiveService(self.inventory)
        missing = Path(self.temp.name) / "missing.zip"
        with self.assertRaisesRegex(InvalidStateArchive, "regular non-symlink"):
            service._validate(missing)

        invalid_zip = Path(self.temp.name) / "invalid.zip"
        invalid_zip.write_bytes(b"not a zip")
        with self.assertRaisesRegex(InvalidStateArchive, "content is invalid"):
            service._validate(invalid_zip)

        missing_manifest = Path(self.temp.name) / "missing-manifest.zip"
        with zipfile.ZipFile(missing_manifest, "w") as archive:
            archive.writestr("payload.json", "{}")
        with self.assertRaisesRegex(InvalidStateArchive, "Manifest is missing or invalid"):
            service._validate(missing_manifest)

        unsupported = Path(self.temp.name) / "unsupported.zip"
        with zipfile.ZipFile(unsupported, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"archive_schema_version": 99, "entries": []}))
        with self.assertRaisesRegex(InvalidStateArchive, "Unsupported archive schema"):
            service._validate(unsupported)

    def test_manifest_entry_shape_and_undeclared_content_are_rejected(self):
        service = StateArchiveService(self.inventory)
        invalid_entry = Path(self.temp.name) / "invalid-entry.zip"
        with zipfile.ZipFile(invalid_entry, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"archive_schema_version": 1, "entries": ["invalid"]}))
        with self.assertRaisesRegex(InvalidStateArchive, "Manifest entry is invalid"):
            service._validate(invalid_entry)

        undeclared = Path(self.temp.name) / "undeclared.zip"
        with zipfile.ZipFile(undeclared, "w") as archive:
            archive.writestr("extra.json", "{}")
            archive.writestr("manifest.json", json.dumps({"archive_schema_version": 1, "entries": []}))
        with self.assertRaisesRegex(InvalidStateArchive, "undeclared content"):
            service._validate(undeclared)
