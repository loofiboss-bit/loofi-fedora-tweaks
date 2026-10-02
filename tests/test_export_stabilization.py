"""Private atomic exports and process-safe action logging."""

import json
import multiprocessing
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from core.executor.action_executor import ActionExecutor
from core.executor.action_result import ActionResult
from core.privacy import redact_text
from utils.journal import JournalManager, Result

PRIVATE = 'Authorization: Bearer SYNTHETIC_BEARER\npassword="SYNTHETIC SECRET" /home/synthetic-user/private\n198.51.100.42 01:23:45:67:89:ab synthetic@example.invalid\nGITHUB_TOKEN=SYNTHETIC_GITHUB refresh_token=SYNTHETIC_REFRESH client_secret=SYNTHETIC_CLIENT AWS_SECRET_ACCESS_KEY=SYNTHETIC_AWS'


def panic_writer(path, **kwargs):
    path.write_text(PRIVATE)
    return Result(True, "ok")


def log_writer(root, index):
    import core.executor.action_executor as module
    module._LOG_DIR = root
    module._ACTION_LOG_FILE = str(Path(root) / "log.jsonl")
    for offset in range(10):
        ActionExecutor()._log_action(["echo", f"writer-{index}-{offset}"], ActionResult.ok("ok"))


class TestSupportPrivacy(unittest.TestCase):
    @patch("core.export.support_bundle.SupportBundleWriter.generate_bundle")
    @patch.object(JournalManager, "export_panic_log", side_effect=panic_writer)
    @patch.object(JournalManager, "_get_system_info", return_value=PRIVATE)
    @patch.object(JournalManager, "get_recent_errors", return_value=PRIVATE)
    @patch("utils.journal.subprocess.run")
    def test_every_member_and_alias_is_sanitized_without_invalidating_large_json(self, query, recent, info, panic, payload):
        query.return_value = Mock(returncode=0, stdout=PRIVATE)
        payload.return_value = {"password": "SYNTHETIC_SECRET_JSON", "note": PRIVATE, "large": "x" * 7000,
                                "headers": {"Authorization": "Bearer SYNTHETIC_HEADER", "Proxy-Authorization": "Basic SYNTHETIC_PROXY"}}
        for session in (None, "selected-session"):
            with self.subTest(session=session), tempfile.TemporaryDirectory() as root:
                output = Path(root) / "bundle.zip"
                output.write_bytes(b"old archive")
                output.chmod(0o644)
                result = JournalManager.export_support_bundle(output, troubleshooting_session_id=session)
                self.assertTrue(result.success)
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                with zipfile.ZipFile(output) as archive:
                    self.assertEqual(len(archive.namelist()), 8)
                    for name in archive.namelist():
                        content = archive.read(name).decode()
                        for secret in ("SYNTHETIC_BEARER", "SYNTHETIC SECRET", "synthetic-user", "198.51.100.42", "01:23:45:67:89:ab", "synthetic@example.invalid", "SYNTHETIC_SECRET_JSON", "SYNTHETIC_GITHUB", "SYNTHETIC_REFRESH", "SYNTHETIC_CLIENT", "SYNTHETIC_AWS", "SYNTHETIC_HEADER", "SYNTHETIC_PROXY"):
                            self.assertNotIn(secret, content, name)
                        if name.endswith(".json"):
                            parsed = json.loads(content)
                            if name.startswith("support-bundle"):
                                self.assertEqual(len(parsed["large"]), 6000)  # Existing per-field privacy bound.

    @patch("core.export.support_bundle.SupportBundleWriter.generate_bundle", side_effect=ValueError("unavailable"))
    @patch.object(JournalManager, "export_panic_log", side_effect=panic_writer)
    @patch.object(JournalManager, "_get_system_info", return_value="info")
    @patch.object(JournalManager, "get_recent_errors", return_value="")
    @patch("utils.journal.subprocess.run")
    def test_selected_session_error_preserves_previous_archive(self, query, recent, info, panic, payload):
        query.return_value = Mock(returncode=0, stdout="")
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "bundle.zip"
            output.write_bytes(b"sentinel")
            result = JournalManager.export_support_bundle(output, troubleshooting_session_id="session")
            self.assertFalse(result.success)
            self.assertEqual(output.read_bytes(), b"sentinel")

    @patch("utils.journal.os.replace", side_effect=OSError("write failed"))
    @patch("core.export.support_bundle.SupportBundleWriter.generate_bundle", return_value={})
    @patch.object(JournalManager, "export_panic_log", side_effect=panic_writer)
    @patch.object(JournalManager, "_get_system_info", return_value="info")
    @patch.object(JournalManager, "get_recent_errors", return_value="")
    @patch("utils.journal.subprocess.run")
    def test_write_failure_keeps_previous_archive_and_cleans_staging(self, query, recent, info, panic, payload, replace):
        query.return_value = Mock(returncode=0, stdout="")
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "bundle.zip"
            output.write_bytes(b"sentinel")
            self.assertFalse(JournalManager.export_support_bundle(output).success)
            self.assertEqual(output.read_bytes(), b"sentinel")
            self.assertEqual(list(Path(root).iterdir()), [output])

    @patch("core.export.support_bundle.SupportBundleWriter.generate_bundle", return_value={})
    @patch.object(JournalManager, "export_panic_log", return_value=Result(False, "Collection denied"))
    @patch.object(JournalManager, "_get_system_info", return_value="COLLECTION_ERROR=kernel query unavailable")
    @patch.object(JournalManager, "get_recent_errors", side_effect=OSError("Access denied"))
    @patch("utils.journal.subprocess.run")
    def test_source_errors_are_explicit_and_masked(self, query, recent, info, panic, payload):
        query.return_value = Mock(returncode=1, stdout="looks healthy", stderr=PRIVATE)
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "bundle.zip"
            result = JournalManager.export_support_bundle(output)
            self.assertTrue(result.success)
            self.assertEqual(result.data["collection_status"], "partial")
            with zipfile.ZipFile(output) as archive:
                status = json.loads(archive.read("collection-status.json"))
                self.assertEqual(status["status"], "partial")
                self.assertEqual(len(status["errors"]), 4)
                self.assertNotIn("looks healthy", archive.read("failed-services.txt").decode())
                self.assertNotIn("SYNTHETIC_BEARER", json.dumps(status))

    def test_quoted_secrets_and_url_credentials(self):
        self.assertNotIn("SYNTHETIC SECRET", redact_text(PRIVATE))
        self.assertEqual(redact_text("https://username:secret-value@example.invalid/a"), "https://<masked>@example.invalid/a")
        self.assertEqual(redact_text('password="SYNTHETIC SECRET'), "password=<masked>")
        self.assertEqual(redact_text('password="SYNTHETIC \\"SECRET\\" SUFFIX" done'), "password=<masked> done")


class TestPrivateActionLog(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "log.jsonl"
        for name, value in (("_LOG_DIR", str(self.root)), ("_ACTION_LOG_FILE", str(self.path))):
            patcher = patch("core.executor.action_executor." + name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_existing_permissions_repaired_and_secrets_redacted(self):
        self.root.chmod(0o755)
        self.path.write_text("")
        self.path.chmod(0o644)
        ActionExecutor()._log_action(["echo", "--token", "SYNTHETIC_ARG_SECRET"], ActionResult.ok(PRIVATE))
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        content = self.path.read_text()
        self.assertNotIn("SYNTHETIC_ARG_SECRET", content)
        self.assertNotIn("SYNTHETIC_BEARER", content)
        self.assertFalse(self.path.with_suffix(".jsonl.lkg").exists())

    def test_message_redaction_precedes_size_limit(self):
        secret = "SYNTHETIC_" + "PRIVATE WORD " * 50
        ActionExecutor()._log_action(["echo"], ActionResult.ok('password="' + secret + '"'))
        content = self.path.read_text()
        self.assertNotIn("PRIVATE WORD", content)
        self.assertNotIn("SYNTHETIC_", content)

    def test_read_repairs_permissions_without_rewriting_history_and_masks_returned_values(self):
        content = json.dumps({"cmd": ["echo", "--access-token", "SYNTHETIC_OLD_SECRET"], "message": PRIVATE}) + "\n"
        self.path.write_text(content)
        self.path.chmod(0o644)
        self.root.chmod(0o755)
        rows = ActionExecutor.get_action_log()
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.path.read_text(), content)
        self.assertNotIn("SYNTHETIC_OLD_SECRET", json.dumps(rows))
        self.assertNotIn("SYNTHETIC_BEARER", json.dumps(rows))
        ActionExecutor()._log_action(["echo", "new"], ActionResult.ok("ok"))
        self.assertEqual(len(self.path.read_text().splitlines()), 2)
        self.assertNotIn("SYNTHETIC_OLD_SECRET", self.path.read_text())
        self.assertNotIn("SYNTHETIC_BEARER", self.path.read_text())

    def _concurrent_rows(self):
        processes = [multiprocessing.get_context("fork").Process(target=log_writer, args=(str(self.root), index)) for index in range(4)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            self.assertEqual(process.exitcode, 0)
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_concurrent_processes_preserve_every_record(self):
        rows = self._concurrent_rows()
        self.assertEqual(len(rows), 40)
        self.assertEqual(len({row["cmd"][1] for row in rows}), 40)

    @patch("core.executor.action_executor.MAX_LOG_ENTRIES", 25)
    def test_concurrent_processes_bound_trimming(self):
        rows = self._concurrent_rows()
        self.assertEqual(len(rows), 25)
        self.assertEqual(len({row["cmd"][1] for row in rows}), 25)

    @patch("core.executor.action_executor.atomic_write_text", side_effect=OSError("full"))
    def test_logging_failure_preserves_file_and_action_result(self, write):
        self.path.write_bytes(b"sentinel\n")
        result = ActionResult.ok("valid action")
        ActionExecutor()._log_action(["echo"], result)
        self.assertTrue(result.success)
        self.assertEqual(self.path.read_bytes(), b"sentinel\n")
