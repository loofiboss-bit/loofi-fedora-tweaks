"""Tests for v12 observability API routes."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))


class TestObservabilityApiRoutes(unittest.TestCase):
    """API routes expose bounded, authenticated v12 observability payloads."""

    @patch("core.observability.HealthSnapshot.collect")
    def test_collect_health_snapshot_returns_read_only_envelope(self, collect_snapshot):
        from api.routes.system import get_current_health_snapshot

        snapshot = MagicMock()
        snapshot.to_dict.return_value = {"schema_version": 1, "fedora_target": "45-preview"}
        collect_snapshot.return_value = snapshot

        payload = get_current_health_snapshot(target="45-preview", _auth="token")

        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["snapshot"]["fedora_target"], "45-preview")
        collect_snapshot.assert_called_once_with(fedora_target="45-preview")

    @patch("core.observability.HealthTimelineStore")
    def test_get_health_timeline_clamps_limit(self, mock_store_cls):
        from api.routes.system import get_health_timeline

        mock_store_cls.return_value.export.return_value = {"count": 0}

        payload = get_health_timeline(limit=999, _auth="token")

        self.assertEqual(payload["count"], 0)
        mock_store_cls.return_value.export.assert_called_once_with(limit=30)

    @patch("api.routes.system.AgentRegistry")
    def test_get_agents_serializes_configs_states_and_summary(self, registry_cls):
        from api.routes.system import get_agents

        agent = SimpleNamespace(agent_id="agent-1", to_dict=lambda: {"id": "agent-1"})
        state = SimpleNamespace(to_dict=lambda: {"state": "idle"})
        registry = registry_cls.instance.return_value
        registry.list_agents.return_value = [agent]
        registry.get_state.return_value = state
        registry.get_agent_summary.return_value = {"total": 1}

        payload = get_agents(_auth="token")

        self.assertEqual(payload["agents"], [{"id": "agent-1"}])
        self.assertEqual(payload["states"], [{"state": "idle"}])
        self.assertEqual(payload["summary"], {"total": 1})


if __name__ == "__main__":
    unittest.main()
