import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Add source path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loofi-fedora-tweaks'))

from core.diagnostics.health_model import HealthCheck, HealthResult
from core.diagnostics.health_registry import HealthRegistry
from core.executor.action_result import ActionResult

def test_health_check_model():
    check = HealthCheck(
        id="test-check",
        title="Test Check",
        severity="info",
        category="system",
        description="Just a test"
    )
    assert check.id == "test-check"
    assert check.severity == "info"
    
    data = check.to_dict()
    assert data["id"] == "test-check"
    assert data["title"] == "Test Check"

def test_health_registry_initialization():
    registry = HealthRegistry()
    checks = registry.list_checks()
    assert len(checks) >= 5
    
    ids = [c.id for c in checks]
    assert "dnf-lock" in ids
    assert "failed-services" in ids

@patch("core.executor.action_executor.ActionExecutor.execute")
@patch("services.system.system.SystemManager.is_atomic")
def test_run_check_dnf_lock_unhealthy(mock_is_atomic, mock_execute):
    mock_is_atomic.return_value = False
    mock_execute.return_value = ActionResult(success=True, message="Found", exit_code=0, stdout="fuser: /var/lib/dnf/labels.db: 1234")
    
    registry = HealthRegistry()
    result = registry.run_check("dnf-lock")
    
    assert result.status == "unhealthy"
    assert "Another process is using DNF" in result.message

@patch("core.executor.action_executor.ActionExecutor.execute")
@patch("services.system.system.SystemManager.is_atomic")
def test_run_check_dnf_lock_healthy(mock_is_atomic, mock_execute):
    mock_is_atomic.return_value = False
    mock_execute.return_value = ActionResult(success=False, message="Not Found", exit_code=1, stdout="")
    
    registry = HealthRegistry()
    result = registry.run_check("dnf-lock")
    
    assert result.status == "healthy"
    assert "DNF is not locked" in result.message

@patch("core.executor.action_executor.ActionExecutor.execute")
def test_run_check_failed_services(mock_execute):
    mock_execute.return_value = ActionResult(success=True, message="Failures", exit_code=0, stdout="failed-svc.service loaded failed failed My Failed Service")
    
    registry = HealthRegistry()
    result = registry.run_check("failed-services")
    
    assert result.status == "unhealthy"
    assert "1 failed system services detected" in result.message

@patch("shutil.disk_usage")
def test_run_check_disk_space(mock_disk_usage):
    # (total, used, free)
    mock_disk_usage.return_value = (100*1024**3, 98*1024**3, 2*1024**3) # 2GB free
    
    registry = HealthRegistry()
    result = registry.run_check("disk-space-root")
    
    assert result.status == "unhealthy"
    assert "Low disk space" in result.message

@patch("services.system.system.SystemManager.is_atomic")
@patch("services.system.system.SystemManager.has_pending_deployment")
def test_run_check_atomic_reboot(mock_pending, mock_is_atomic):
    mock_is_atomic.return_value = True
    mock_pending.return_value = True
    
    registry = HealthRegistry()
    result = registry.run_check("atomic-pending-reboot")
    
    assert result.status == "unhealthy"
    assert "reboot" in result.message

@patch("services.system.system.SystemManager.is_atomic")
@patch("services.system.system.SystemManager.get_layered_packages")
def test_run_check_atomic_layered(mock_get_layered, mock_is_atomic):
    mock_is_atomic.return_value = True
    mock_get_layered.return_value = ["htop", "vim"]
    
    registry = HealthRegistry()
    result = registry.run_check("atomic-layered-packages")
    
    print(f"DEBUG: result.message = {result.message}")
    assert result.status == "info"
    assert "2 layered packages" in result.message
    assert "htop" in result.affected_entities
