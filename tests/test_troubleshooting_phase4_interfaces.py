"""Phase 4 CLI, API, inspection, and Support Bundle v13 contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from cli.commands.troubleshooting_commands import (
    _run_with_cancellation,
    handle_troubleshoot,
)
from cli.parser import build_parser
from core.export.support_bundle import (
    CURRENT_SUPPORT_BUNDLE_VERSION,
    import_legacy_bundle,
)
from core.export.support_bundle_v13 import SupportBundleV13
from core.troubleshooting.adapters import adapt_structured_source
from core.troubleshooting.composition import compose_session
from core.troubleshooting.inspection import (
    TroubleshootingInspectionService,
    bounded_session_payload,
    sanitize_interface_payload,
)
from core.troubleshooting.lifecycle import new_session, start_session
from core.troubleshooting.models import NextStep, TroubleshootingFinding
from core.troubleshooting.service import TroubleshootingRun
from core.troubleshooting.storage import (
    STORE_SCHEMA_VERSION,
    SessionStoreSnapshot,
    UnsupportedFutureSessionSchema,
)
from utils.journal import JournalManager, Result


SESSION_ID = "12345678-1234-5678-9234-567812345678"
FOLLOWUP_ID = "22345678-1234-5678-9234-567812345678"


def _session(
    session_id: str = SESSION_ID,
    *,
    completed_at: float = 5.0,
):
    finding = TroubleshootingFinding.build(
        finding_type="network-state-degraded",
        category="network",
        severity="attention",
        title="Review /home/alice token=private-value",
        summary="Contact alice@example.com from host=workstation",
        evidence_explanation="Address 192.0.2.12 needs review.",
        source_id="network-state",
        collected_at=completed_at,
        freshness="fresh",
        evidence_quality="confirmed",
        applicable_variants=frozenset({"traditional"}),
        affected_resources=("network-manager",),
        evidence={
            "note": (
                "password=hunter2 mac=00:11:22:33:44:55 "
                "/home/alice/private"
            )
        },
        next_step=NextStep.navigation("network"),
    )
    running = start_session(
        new_session(
            "network_problem",
            "traditional",
            started_at=1.0,
            session_id=session_id,
        ),
        started_at=2.0,
    )
    evidence = adapt_structured_source(
        profile_id="network_problem",
        variant="traditional",
        source_id="network-state",
        state="completed",
        started_at=2.0,
        completed_at=completed_at,
        facts={"detail": "/home/alice token=private-value"},
        findings=(finding,),
    )
    return compose_session(
        running,
        (evidence,),
        completed_at=completed_at,
    )


class TestTroubleshootingInspection(unittest.TestCase):
    def test_session_payload_is_bounded_and_recursively_redacted(self):
        payload = bounded_session_payload(_session())
        rendered = json.dumps(payload, sort_keys=True)

        for sensitive in (
            "/home/alice",
            "private-value",
            "hunter2",
            "alice@example.com",
            "workstation",
            "192.0.2.12",
            "00:11:22:33:44:55",
        ):
            with self.subTest(sensitive=sensitive):
                self.assertNotIn(sensitive, rendered)

        stripped = sanitize_interface_payload(
            {
                "command": ["unsafe"],
                "stdout": "raw",
                "nested": {"api_token": "secret-value", "safe": "ok"},
            }
        )
        self.assertNotIn("command", stripped)
        self.assertNotIn("stdout", stripped)
        self.assertNotIn("api_token", stripped["nested"])
        self.assertEqual(stripped["nested"]["safe"], "ok")

    def test_future_session_schema_fails_closed(self):
        store = MagicMock()
        store.read.return_value = SessionStoreSnapshot(
            (),
            STORE_SCHEMA_VERSION + 1,
            False,
            "future-schema-read-only",
        )

        with self.assertRaises(UnsupportedFutureSessionSchema):
            TroubleshootingInspectionService(store).latest()


class TestTroubleshootingCli(unittest.TestCase):
    def test_all_phase4_commands_parse(self):
        parser = build_parser()
        commands = (
            (["troubleshoot", "profiles"], "profiles"),
            (["troubleshoot", "run", "system_slow"], "run"),
            (["troubleshoot", "show", SESSION_ID], "show"),
            (["troubleshoot", "latest"], "latest"),
            (
                [
                    "troubleshoot",
                    "compare",
                    SESSION_ID,
                    FOLLOWUP_ID,
                ],
                "compare",
            ),
            (["troubleshoot", "export", SESSION_ID], "export"),
        )
        for argv, expected in commands:
            with self.subTest(argv=argv):
                args = parser.parse_args(argv)
                self.assertEqual(args.command, "troubleshoot")
                self.assertEqual(args.troubleshoot_action, expected)

    def test_profiles_use_the_stable_versioned_envelope(self):
        output_json = MagicMock()

        result = handle_troubleshoot(
            SimpleNamespace(troubleshoot_action="profiles"),
            True,
            output_json,
            MagicMock(),
            MagicMock(),
        )

        self.assertEqual(result, 0)
        payload = output_json.call_args.args[0]
        self.assertEqual(payload["schema_id"], "loofi.troubleshooting")
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["command"], "profiles")
        self.assertEqual(payload["data"]["count"], 6)

    def test_run_passes_a_cooperative_cancellation_signal(self):
        service = MagicMock()
        service.run.return_value = SimpleNamespace(session=_session())

        result = _run_with_cancellation(
            service,
            "network_problem",
            None,
        )

        self.assertEqual(result.session.session_id, SESSION_ID)
        cancellation = service.run.call_args.kwargs["cancellation"]
        self.assertFalse(cancellation.is_cancelled())
        service.run.assert_called_once()

    @patch(
        "cli.commands.troubleshooting_commands."
        "TroubleshootingService"
    )
    def test_run_maps_the_real_service_persistence_contract(
        self,
        service_cls,
    ):
        service_cls.return_value.run.return_value = TroubleshootingRun(
            _session(),
            persistence_reason_code="session-store-unavailable",
        )
        output_json = MagicMock()

        result = handle_troubleshoot(
            SimpleNamespace(
                troubleshoot_action="run",
                profile_id="system_slow",
                application_id=None,
            ),
            True,
            output_json,
            MagicMock(),
            MagicMock(),
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            output_json.call_args.args[0]["data"]["persistence_warning"],
            "session-store-unavailable",
        )

    @patch(
        "cli.commands.troubleshooting_commands."
        "TroubleshootingInspectionService"
    )
    def test_export_selects_exactly_one_known_session(
        self,
        inspection_cls,
    ):
        inspection_cls.return_value.require.return_value = _session()
        journal = MagicMock()
        journal.export_support_bundle.return_value = Result(
            True,
            "saved",
            {"path": "/tmp/support.zip"},
        )
        output_json = MagicMock()

        result = handle_troubleshoot(
            SimpleNamespace(
                troubleshoot_action="export",
                session_id=SESSION_ID,
                output=None,
            ),
            True,
            output_json,
            MagicMock(),
            journal,
        )

        self.assertEqual(result, 0)
        journal.export_support_bundle.assert_called_once_with(
            None,
            troubleshooting_session_id=SESSION_ID,
        )
        self.assertEqual(
            output_json.call_args.args[0]["data"]["session_id"],
            SESSION_ID,
        )


class TestTroubleshootingApi(unittest.TestCase):
    @staticmethod
    def _iter_routes(routes):
        """Traverse direct and mounted FastAPI routes across supported versions."""
        for route in routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", None) or set()
            if isinstance(route, APIRoute) and path:
                yield path, tuple(sorted(methods))
                continue
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                yield from TestTroubleshootingApi._iter_routes(
                    getattr(original_router, "routes", ()),
                )

    @patch(
        "core.troubleshooting.storage."
        "TroubleshootingSessionStore.read"
    )
    def test_api_construction_does_not_read_or_collect_sessions(
        self,
        read,
    ):
        from utils.api_server import APIServer

        APIServer()
        read.assert_not_called()

    @patch(
        "api.routes.troubleshooting.TroubleshootingInspectionService"
    )
    def test_latest_and_known_session_are_authenticated_get_only(
        self,
        inspection_cls,
    ):
        from utils.api_server import APIServer
        from utils.auth import AuthManager

        inspection_cls.return_value.latest.return_value = _session()
        inspection_cls.return_value.require.return_value = _session()
        server = APIServer()
        server.app.dependency_overrides[
            AuthManager.verify_bearer_token
        ] = lambda: "token"
        client = TestClient(server.app)

        latest = client.get("/api/troubleshooting/latest")
        known = client.get(
            f"/api/troubleshooting/sessions/{SESSION_ID}"
        )

        self.assertEqual(latest.status_code, 200)
        self.assertTrue(latest.json()["read_only"])
        self.assertEqual(
            known.json()["session"]["session_id"],
            SESSION_ID,
        )
        paths = set(self._iter_routes(server.app.routes))
        self.assertIn(
            (
                "/api/troubleshooting/latest",
                ("GET",),
            ),
            paths,
        )
        self.assertNotIn(
            (
                "/api/troubleshooting/run",
                ("POST",),
            ),
            paths,
        )

    def test_latest_requires_authentication(self):
        from utils.api_server import APIServer

        response = TestClient(APIServer().app).get(
            "/api/troubleshooting/latest"
        )
        self.assertIn(response.status_code, {401, 403})


class TestSupportBundleV13(unittest.TestCase):
    @patch(
        "core.export.support_bundle_v12.SupportBundleV12.generate_bundle",
        return_value={"legacy": True},
    )
    @patch(
        "core.export.support_bundle_v13."
        "SupportBundleV13._linked_records",
        return_value=[],
    )
    def test_selected_session_is_bounded_redacted_and_inert(
        self,
        _linked_records,
        _legacy,
    ):
        store = MagicMock()
        store.read.return_value = SessionStoreSnapshot(
            (_session(),),
            STORE_SCHEMA_VERSION,
            True,
        )

        bundle = SupportBundleV13.generate_bundle(
            session_id=SESSION_ID,
            session_store=store,
        )
        support_case = bundle["troubleshooting_support_case"]
        rendered = json.dumps(bundle, sort_keys=True)

        self.assertEqual(bundle["support_bundle_version"], 13)
        self.assertEqual(CURRENT_SUPPORT_BUNDLE_VERSION, 13)
        self.assertEqual(support_case["limits"]["sessions"], 1)
        self.assertEqual(support_case["limits"]["findings"], 50)
        self.assertEqual(support_case["limits"]["related_changes"], 25)
        self.assertEqual(support_case["limits"]["linked_records"], 25)
        self.assertFalse(support_case["collection_started_by_export"])
        self.assertFalse(support_case["commands_included"])
        self.assertNotIn("private-value", rendered)
        self.assertNotIn("/home/alice", rendered)

    @patch(
        "core.export.support_bundle_v12.SupportBundleV12.generate_bundle",
        return_value={"legacy": True},
    )
    def test_unselected_bundle_does_not_read_session_state(self, _legacy):
        store = MagicMock()

        bundle = SupportBundleV13.generate_bundle(
            session_store=store,
        )

        self.assertIsNone(
            bundle["troubleshooting_support_case"]["session"]
        )
        store.read.assert_not_called()

    def test_v2_through_v12_readers_remain_supported(self):
        for version in range(2, 13):
            with self.subTest(version=version):
                imported = import_legacy_bundle(
                    {"support_bundle_version": version}
                )
                self.assertEqual(
                    imported["support_bundle_version"],
                    version,
                )
        with self.assertRaises(ValueError):
            import_legacy_bundle({"support_bundle_version": 14})

    @patch(
        "utils.journal.subprocess.run",
        return_value=SimpleNamespace(stdout=""),
    )
    @patch.object(
        JournalManager,
        "_get_system_info",
        return_value="",
    )
    @patch.object(
        JournalManager,
        "get_recent_errors",
        return_value="",
    )
    @patch.object(
        JournalManager,
        "export_panic_log",
        return_value=Result(True, "ok"),
    )
    @patch(
        "core.export.support_bundle."
        "SupportBundleWriter.generate_bundle",
        return_value={"support_bundle_version": 13},
    )
    def test_journal_export_forwards_selected_session(
        self,
        generate,
        _panic,
        _recent,
        _system_info,
        _run,
    ):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "support.zip"
            result = JournalManager.export_support_bundle(
                output,
                troubleshooting_session_id=SESSION_ID,
            )

        self.assertTrue(result.success)
        generate.assert_called_once_with(session_id=SESSION_ID)

    @patch(
        "utils.journal.subprocess.run",
        return_value=SimpleNamespace(stdout=""),
    )
    @patch.object(
        JournalManager,
        "_get_system_info",
        return_value="",
    )
    @patch.object(
        JournalManager,
        "get_recent_errors",
        return_value="",
    )
    @patch.object(
        JournalManager,
        "export_panic_log",
        return_value=Result(True, "ok"),
    )
    @patch(
        "core.export.support_bundle."
        "SupportBundleWriter.generate_bundle",
        side_effect=ValueError("future schema"),
    )
    def test_selected_session_export_fails_closed(
        self,
        generate,
        _panic,
        _recent,
        _system_info,
        _run,
    ):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "support.zip"
            result = JournalManager.export_support_bundle(
                output,
                troubleshooting_session_id=SESSION_ID,
            )

            self.assertFalse(result.success)
            self.assertFalse(output.exists())
        generate.assert_called_once_with(session_id=SESSION_ID)


if __name__ == "__main__":
    unittest.main()
