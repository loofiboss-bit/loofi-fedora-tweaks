import pytest
import os
import sys

# Add source path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from core.diagnostics.health_registry import HealthRegistry
from core.executor.action_model import AtlasActionRegistry, SystemAction
from core.diagnostics.upgrade_checker import UpgradeAssistant
from core.diagnostics.task_dashboard import TaskManager
from core.export.support_bundle_v2 import SupportBundleV2

def test_v4_integration_flow():
    # 1. Setup Registry
    registry = HealthRegistry()
    
    # 2. Setup Assistant (registers more checks)
    assistant = UpgradeAssistant(registry)
    all_checks = registry.list_checks()
    assert any(c.id.startswith("upgrade-") for c in all_checks)
    
    # 3. Setup Tasks
    task_manager = TaskManager(registry)
    tasks = task_manager.get_tasks()
    assert len(tasks) >= 3
    assert tasks[0].id == "task-repair"  # Priority 0

    # 4. Setup Actions
    action_registry = AtlasActionRegistry()
    action = action_registry.get_action("dnf-clean-all")
    assert action.risk_level == "low"
    assert action.privileged is True

    # 5. Support Bundle
    bundle_gen = SupportBundleV2(registry)
    bundle = bundle_gen.generate_bundle()
    assert bundle["v"] == "4.0.0-atlas"
    assert "system" in bundle
    assert "health" in bundle
    assert len(bundle["health"]) == len(all_checks)

def test_upgrade_assistant_audit():
    registry = HealthRegistry()
    assistant = UpgradeAssistant(registry)
    results = assistant.run_pre_upgrade_audit()
    assert len(results) == 5
    for r in results:
        assert r.status == "healthy" # Based on mock run_check

def test_system_action_model():
    action = SystemAction(
        id="test",
        title="Test",
        explanation="Explain",
        command="echo",
        args=["hello"],
        risk_level="info"
    )
    assert action.risk_level == "info"
    assert action.confirmation_required is True
