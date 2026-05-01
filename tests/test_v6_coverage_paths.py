"""Focused coverage for v6 command and dashboard paths."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from cli.commands.agent_commands import handle_agent
from cli.commands.firewall_commands import handle_firewall
from cli.commands.monitoring_commands import handle_health_history, handle_logs
from cli.commands.network_mesh_commands import handle_mesh, handle_teleport
from cli.commands.tuning_commands import handle_backup, handle_boot, handle_snapshot, handle_tuner
from core.diagnostics.release_readiness import ReadinessCheck, ReleaseReadinessReport, TARGETS
from core.diagnostics.task_dashboard import DashboardTask
from services.security.firewall import FirewallInfo, ZoneInfo
from ui.atlas_dashboard_tab import AtlasDashboardTab, TaskCard
from ui.fedora44_readiness_dialog import Fedora44ReadinessDialog
from ui.release_readiness_dialog import ReadinessWorker, ReleaseReadinessDialog


app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class _Result:
    def __init__(self, success=True, message="ok", data=None):
        self.success = success
        self.message = message
        self.data = data or {"value": 1}


class _Timeline:
    def get_summary(self, hours=24):
        return {
            "cpu_temp": {"min": 40.0, "max": 50.0, "avg": 45.0, "count": 2},
            "custom": {"min": 1.0, "max": 3.0, "avg": 2.0, "count": 3},
        }

    def record_snapshot(self):
        return _Result(True, "recorded")

    def export_metrics(self, path, format="json"):
        return _Result(path.endswith((".json", ".csv")), "exported")

    def prune_old_data(self):
        return _Result(False, "nothing pruned")


class _LogEntry:
    def __init__(self, pattern_match="oom"):
        self.timestamp = "now"
        self.priority_label = "ERR"
        self.unit = "unit.service"
        self.message = "message"
        self.pattern_match = pattern_match


class _LogSummary:
    total_entries = 3
    critical_count = 1
    error_count = 1
    warning_count = 1
    top_units = [("unit.service", 2)]
    detected_patterns = [("oom", 1)]


class _Logs:
    @staticmethod
    def get_logs(unit=None, priority=None, since=None, lines=100):
        return [_LogEntry(), _LogEntry(pattern_match="")]

    @staticmethod
    def get_error_summary(since="24h ago"):
        return _LogSummary()

    @staticmethod
    def export_logs(entries, path, format="text"):
        return path.endswith((".json", ".txt"))


class _Workload:
    name = "desktop"
    cpu_percent = 12.0
    memory_percent = 34.0
    description = "normal"


class _Recommendation:
    governor = "balanced"
    swappiness = 20
    io_scheduler = "mq-deadline"
    thp = "madvise"
    reason = "balanced desktop"


class _History:
    timestamp = 1
    workload = "desktop"
    applied = True


class _AutoTuner:
    @staticmethod
    def detect_workload():
        return _Workload()

    @staticmethod
    def recommend(workload=None):
        return _Recommendation()

    @staticmethod
    def get_current_settings():
        return {"governor": "powersave"}

    @staticmethod
    def apply_recommendation(rec):
        return ("pkexec", ["true"], "apply")

    @staticmethod
    def apply_swappiness(value):
        return ("pkexec", ["true"], "swappiness")

    @staticmethod
    def get_tuning_history():
        return [_History()]


class _Snapshot:
    id = "1"
    backend = "snapper"
    label = "before"
    timestamp = 1


class _Backend:
    name = "snapper"
    available = True
    version = "1.0"


class _SnapshotManager:
    @staticmethod
    def list_snapshots():
        return [_Snapshot()]

    @staticmethod
    def create_snapshot(label):
        return ("pkexec", ["true"], label)

    @staticmethod
    def delete_snapshot(snapshot_id):
        return ("pkexec", ["true"], snapshot_id)

    @staticmethod
    def detect_backends():
        return [_Backend()]


class _BackupItem:
    id = "1"
    date = "today"
    description = "backup"
    tool = "snapper"


class _Backup:
    @staticmethod
    def detect_backup_tool():
        return "snapper"

    @staticmethod
    def get_available_tools():
        return ["snapper", "timeshift"]

    @staticmethod
    def create_snapshot(tool=None, description="CLI backup"):
        return ("pkexec", ["true"], description)

    @staticmethod
    def list_snapshots(tool=None):
        return [_BackupItem()]

    @staticmethod
    def restore_snapshot(snap_id, tool=None):
        return ("pkexec", ["true"], snap_id)

    @staticmethod
    def delete_snapshot(snap_id, tool=None):
        return ("pkexec", ["true"], snap_id)

    @staticmethod
    def get_backup_status():
        return {"active": "snapper"}


class _GrubConfig:
    default_entry = "0"
    timeout = 5
    theme = ""
    cmdline_linux = "quiet"


class _Kernel:
    title = "Fedora"
    version = "6.x"
    is_default = True


class _Boot:
    @staticmethod
    def get_grub_config():
        return _GrubConfig()

    @staticmethod
    def list_kernels():
        return [_Kernel()]

    @staticmethod
    def set_timeout(seconds):
        return ("pkexec", ["true"], str(seconds))

    @staticmethod
    def apply_grub_changes():
        return ("pkexec", ["true"], "apply")


class _Agent:
    id = "agent-1"
    agent_id = "agent-1"
    name = "Agent One"
    enabled = True
    description = "does work"
    notification_config = {}


class _AgentState:
    enabled = True
    last_run = None
    run_count = 2


class _Registry:
    @classmethod
    def instance(cls):
        return cls()

    def list_agents(self):
        return [_Agent()]

    def get_agent_summary(self):
        return {"total_agents": 1, "enabled": 1, "disabled": 0}

    def get_state(self, agent_id):
        return _AgentState()

    def enable_agent(self, agent_id):
        return agent_id == "agent-1"

    def disable_agent(self, agent_id):
        return agent_id == "agent-1"

    def register_agent(self, config):
        return config

    def remove_agent(self, agent_id):
        return agent_id == "agent-1"

    def get_recent_activity(self, limit=20):
        return [{"agent_id": "agent-1", "timestamp": 1, "status": "success"}]

    def get_agent(self, agent_id):
        return _Agent() if agent_id == "agent-1" else None

    def save(self):
        return None


class _RunResult:
    status = "success"
    duration = 0.1
    errors = []


class _ActionResult:
    def __init__(self, success=True):
        self.success = success
        self.message = "ok"


class _Scheduler:
    def run_agent_now(self, agent_id):
        return [_ActionResult(True), _ActionResult(True)]

    def get_schedules(self):
        return [SimpleNamespace(agent_id="agent-1", cron_expression="* * * * *", enabled=True)]


class _Planner:
    def execute_agent(self, agent_id):
        return _RunResult()


class _Notifier:
    def get_recent_notifications(self, limit=20):
        return [SimpleNamespace(timestamp=1, agent_id="agent-1", message="done", severity="low")]


class _EmptyRegistry(_Registry):
    def list_agents(self):
        return []

    def get_recent_activity(self, limit=20):
        return [{"agent_id": "other", "timestamp": 1, "status": "success"}]


class _SchedulerWithoutRun:
    def get_schedules(self):
        return []


class _SchedulerNoop(_SchedulerWithoutRun):
    run_agent_now = None


class _PlannerUnavailable:
    pass


class _Firewall:
    @staticmethod
    def is_available():
        return True

    @staticmethod
    def get_status():
        return FirewallInfo(
            running=True,
            default_zone="FedoraWorkstation",
            active_zones={"FedoraWorkstation": ["wlan0"]},
            services=["ssh"],
            ports=["8080/tcp"],
        )

    @staticmethod
    def list_ports():
        return ["8080/tcp"]

    @staticmethod
    def list_services():
        return ["ssh"]

    @staticmethod
    def get_zones():
        return ["FedoraWorkstation", "public"]

    @staticmethod
    def get_active_zones():
        return {"FedoraWorkstation": ["wlan0"]}

    @staticmethod
    def list_zones():
        return [ZoneInfo(name="FedoraWorkstation", active=True), ZoneInfo(name="public", active=False)]

    @staticmethod
    def add_service(service, zone=None):
        return ("pkexec", ["true"], service)

    remove_service = add_service

    @staticmethod
    def add_port(port, zone=None):
        return ("pkexec", ["true"], port)

    remove_port = add_port

    @staticmethod
    def set_default_zone(zone):
        return ("pkexec", ["true"], zone)

    @staticmethod
    def reload():
        return ("pkexec", ["true"], "reload")

    @staticmethod
    def open_port(port, proto):
        return _Result(True, f"opened {port}/{proto}")

    @staticmethod
    def close_port(port, proto):
        return _Result(False, f"closed {port}/{proto}")


class _FirewallUnavailable(_Firewall):
    @staticmethod
    def is_available():
        return False


@dataclass
class _Peer:
    hostname: str
    ip_address: str


class _Mesh:
    @staticmethod
    def discover_peers():
        return [_Peer("laptop", "192.0.2.10")]

    @staticmethod
    def get_device_id():
        return "device-1"

    @staticmethod
    def get_local_ips():
        return ["192.0.2.2"]


class _Teleport:
    @staticmethod
    def capture_full_state(path):
        return {"path": path}

    @staticmethod
    def create_teleport_package(state, target_device="unknown"):
        return SimpleNamespace(package_id="pkg-1", size_bytes=128)

    @staticmethod
    def get_package_dir():
        return "/tmp"

    @staticmethod
    def save_package_to_file(package, filepath):
        return _Result(True, "saved")

    @staticmethod
    def list_saved_packages():
        return [{"package_id": "pkg-1", "source_device": "device-1", "size_bytes": 128}]

    @staticmethod
    def load_package_from_file(filepath):
        return SimpleNamespace(package_id="pkg-1")

    @staticmethod
    def apply_teleport(package):
        return _Result(True, "restored")


def test_monitoring_command_handlers_text_and_json():
    printed = []
    json_payloads = []

    assert handle_health_history(SimpleNamespace(action="show"), False, json_payloads.append, printed.append, _Timeline) == 0
    assert handle_health_history(SimpleNamespace(action="record"), True, json_payloads.append, printed.append, _Timeline) == 0
    assert handle_health_history(SimpleNamespace(action="export", path="metrics.csv"), False, json_payloads.append, printed.append, _Timeline) == 0
    assert handle_health_history(SimpleNamespace(action="export", path=""), False, json_payloads.append, printed.append, _Timeline) == 1
    assert handle_health_history(SimpleNamespace(action="prune"), True, json_payloads.append, printed.append, _Timeline) == 1
    assert handle_health_history(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, _Timeline) == 1

    assert handle_logs(SimpleNamespace(action="show", unit=None, priority=None, since=None, lines=10), False, json_payloads.append, printed.append, _Logs) == 0
    assert handle_logs(SimpleNamespace(action="show", unit=None, priority=None, since=None, lines=10), True, json_payloads.append, printed.append, _Logs) == 0
    assert handle_logs(SimpleNamespace(action="errors", since=None), False, json_payloads.append, printed.append, _Logs) == 0
    assert handle_logs(SimpleNamespace(action="errors", since="1h ago"), True, json_payloads.append, printed.append, _Logs) == 0
    assert handle_logs(SimpleNamespace(action="export", path="logs.json", since=None, lines=5), False, json_payloads.append, printed.append, _Logs) == 0
    assert handle_logs(SimpleNamespace(action="export", path="", since=None, lines=5), False, json_payloads.append, printed.append, _Logs) == 1
    assert handle_logs(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, _Logs) == 1


def test_network_mesh_command_handlers_cover_branches():
    printed = []
    json_payloads = []

    assert handle_mesh(SimpleNamespace(action="discover"), False, json_payloads.append, printed.append, _Mesh) == 0
    assert handle_mesh(SimpleNamespace(action="discover"), True, json_payloads.append, printed.append, _Mesh) == 0
    assert handle_mesh(SimpleNamespace(action="status"), False, json_payloads.append, printed.append, _Mesh) == 0
    assert handle_mesh(SimpleNamespace(action="status"), True, json_payloads.append, printed.append, _Mesh) == 0
    assert handle_mesh(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, _Mesh) == 1

    assert handle_teleport(SimpleNamespace(action="capture", path="/tmp/project", target="desktop"), False, json_payloads.append, printed.append, _Teleport) == 0
    assert handle_teleport(SimpleNamespace(action="capture", path=None, target="desktop"), True, json_payloads.append, printed.append, _Teleport) == 0
    assert handle_teleport(SimpleNamespace(action="list"), False, json_payloads.append, printed.append, _Teleport) == 0
    assert handle_teleport(SimpleNamespace(action="list"), True, json_payloads.append, printed.append, _Teleport) == 0
    assert handle_teleport(SimpleNamespace(action="restore", package_id=""), False, json_payloads.append, printed.append, _Teleport) == 1
    with patch("cli.commands.network_mesh_commands.os.listdir", return_value=["pkg-1.json"]):
        assert handle_teleport(SimpleNamespace(action="restore", package_id="pkg-1"), False, json_payloads.append, printed.append, _Teleport) == 0
    with patch("cli.commands.network_mesh_commands.os.listdir", return_value=[]):
        assert handle_teleport(SimpleNamespace(action="restore", package_id="missing"), False, json_payloads.append, printed.append, _Teleport) == 1
    assert handle_teleport(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, _Teleport) == 1


def test_tuning_command_handlers_cover_branches():
    printed = []
    json_payloads = []
    run_operation = MagicMock(return_value=True)

    assert handle_tuner(SimpleNamespace(action="analyze"), False, json_payloads.append, printed.append, run_operation, _AutoTuner) == 0
    assert handle_tuner(SimpleNamespace(action="analyze"), True, json_payloads.append, printed.append, run_operation, _AutoTuner) == 0
    assert handle_tuner(SimpleNamespace(action="apply"), False, json_payloads.append, printed.append, run_operation, _AutoTuner) == 0
    assert handle_tuner(SimpleNamespace(action="history"), False, json_payloads.append, printed.append, run_operation, _AutoTuner) == 0
    assert handle_tuner(SimpleNamespace(action="history"), True, json_payloads.append, printed.append, run_operation, _AutoTuner) == 0
    assert handle_tuner(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, run_operation, _AutoTuner) == 1

    assert handle_snapshot(SimpleNamespace(action="list"), False, json_payloads.append, printed.append, run_operation, _SnapshotManager) == 0
    assert handle_snapshot(SimpleNamespace(action="list"), True, json_payloads.append, printed.append, run_operation, _SnapshotManager) == 0
    assert handle_snapshot(SimpleNamespace(action="create", label="manual"), False, json_payloads.append, printed.append, run_operation, _SnapshotManager) == 0
    assert handle_snapshot(SimpleNamespace(action="delete", snapshot_id="1"), False, json_payloads.append, printed.append, run_operation, _SnapshotManager) == 0
    assert handle_snapshot(SimpleNamespace(action="delete", snapshot_id=""), False, json_payloads.append, printed.append, run_operation, _SnapshotManager) == 1
    assert handle_snapshot(SimpleNamespace(action="backends"), False, json_payloads.append, printed.append, run_operation, _SnapshotManager) == 0
    assert handle_snapshot(SimpleNamespace(action="backends"), True, json_payloads.append, printed.append, run_operation, _SnapshotManager) == 0
    assert handle_snapshot(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, run_operation, _SnapshotManager) == 1

    assert handle_backup(SimpleNamespace(action="detect"), False, json_payloads.append, printed.append, run_operation, _Backup) == 0
    assert handle_backup(SimpleNamespace(action="detect"), True, json_payloads.append, printed.append, run_operation, _Backup) == 0
    assert handle_backup(SimpleNamespace(action="create", description="desc", tool="snapper"), False, json_payloads.append, printed.append, run_operation, _Backup) == 0
    assert handle_backup(SimpleNamespace(action="list", tool=None), False, json_payloads.append, printed.append, run_operation, _Backup) == 0
    assert handle_backup(SimpleNamespace(action="list", tool=None), True, json_payloads.append, printed.append, run_operation, _Backup) == 0
    assert handle_backup(SimpleNamespace(action="restore", snapshot_id="1", tool=None), False, json_payloads.append, printed.append, run_operation, _Backup) == 0
    assert handle_backup(SimpleNamespace(action="restore", snapshot_id="", tool=None), False, json_payloads.append, printed.append, run_operation, _Backup) == 1
    assert handle_backup(SimpleNamespace(action="delete", snapshot_id="1", tool=None), False, json_payloads.append, printed.append, run_operation, _Backup) == 0
    assert handle_backup(SimpleNamespace(action="delete", snapshot_id="", tool=None), False, json_payloads.append, printed.append, run_operation, _Backup) == 1
    assert handle_backup(SimpleNamespace(action="status"), False, json_payloads.append, printed.append, run_operation, _Backup) == 0
    assert handle_backup(SimpleNamespace(action="status"), True, json_payloads.append, printed.append, run_operation, _Backup) == 0
    assert handle_backup(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, run_operation, _Backup) == 1

    assert handle_boot(SimpleNamespace(action="config"), False, json_payloads.append, printed.append, run_operation, _Boot) == 0
    assert handle_boot(SimpleNamespace(action="config"), True, json_payloads.append, printed.append, run_operation, _Boot) == 0
    assert handle_boot(SimpleNamespace(action="kernels"), False, json_payloads.append, printed.append, run_operation, _Boot) == 0
    assert handle_boot(SimpleNamespace(action="kernels"), True, json_payloads.append, printed.append, run_operation, _Boot) == 0
    assert handle_boot(SimpleNamespace(action="timeout", seconds=5), False, json_payloads.append, printed.append, run_operation, _Boot) == 0
    assert handle_boot(SimpleNamespace(action="timeout", seconds=None), False, json_payloads.append, printed.append, run_operation, _Boot) == 1
    assert handle_boot(SimpleNamespace(action="apply"), False, json_payloads.append, printed.append, run_operation, _Boot) == 0
    assert handle_boot(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, run_operation, _Boot) == 1


def test_atlas_dashboard_card_and_routing():
    clicked = []
    card = TaskCard(
        DashboardTask(
            id="task-release-readiness",
            title="Release Readiness",
            description="Check readiness",
            icon_id="missing-icon",
        ),
        clicked.append,
    )
    card.btn.click()
    assert clicked == ["task-release-readiness"]

    tab = AtlasDashboardTab()
    assert tab.metadata().id == "atlas_dashboard"
    assert tab.create_widget() is tab
    assert tab.grid.count() >= 1
    tab._refresh_tasks()

    with patch("ui.release_readiness_dialog.ReleaseReadinessDialog") as dialog_cls:
        dialog_cls.return_value.exec.return_value = 0
        tab._on_task_clicked("task-release-readiness")
        dialog_cls.assert_called_once()

    with patch("ui.support_bundle_wizard.SupportBundleWizard") as wizard_cls:
        wizard_cls.return_value.exec.return_value = 0
        tab._on_task_clicked("task-support-bundle")
        wizard_cls.assert_called_once()

    with patch("ui.task_wizard.AtlasTaskWizard") as wizard_cls:
        wizard_cls.return_value.exec.return_value = 0
        tab._on_task_clicked("task-maintenance")
        wizard_cls.assert_called_once()

    tab._on_task_clicked("does-not-exist")


def test_fedora44_dialog_wrapper_instantiates():
    dialog = Fedora44ReadinessDialog(auto_run=False)
    assert dialog.target_key == "44"


def test_agent_command_handler_branches():
    printed = []
    json_payloads = []
    run_operation = MagicMock(return_value=True)

    deps = (_Registry, _Scheduler, _Planner, _Notifier)
    assert handle_agent(SimpleNamespace(action="list"), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="list"), True, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="status", agent_id=""), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="status", agent_id="agent-1"), True, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="enable", agent_id="agent-1"), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="disable", agent_id="missing"), False, json_payloads.append, printed.append, run_operation, *deps) == 1
    assert handle_agent(SimpleNamespace(action="enable", agent_id=""), False, json_payloads.append, printed.append, run_operation, *deps) == 1
    assert handle_agent(SimpleNamespace(action="run", agent_id="agent-1"), True, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="run", agent_id=""), False, json_payloads.append, printed.append, run_operation, *deps) == 1
    assert handle_agent(SimpleNamespace(action="schedule"), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="notifications"), True, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="create", goal="keep healthy"), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="create", goal=""), False, json_payloads.append, printed.append, run_operation, *deps) == 1
    assert handle_agent(SimpleNamespace(action="remove", agent_id="agent-1"), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="remove", agent_id=""), False, json_payloads.append, printed.append, run_operation, *deps) == 1
    assert handle_agent(SimpleNamespace(action="logs", agent_id="agent-1"), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="logs", agent_id=None), True, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="templates"), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="templates"), True, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="notify", agent_id=""), False, json_payloads.append, printed.append, run_operation, *deps) == 1
    assert handle_agent(SimpleNamespace(action="notify", agent_id="agent-1", webhook=""), False, json_payloads.append, printed.append, run_operation, *deps) == 1
    assert handle_agent(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, run_operation, *deps) == 1


def test_agent_command_handler_additional_branches():
    printed = []
    json_payloads = []
    run_operation = MagicMock(return_value=True)

    deps = (_Registry, _Scheduler, _Planner, _Notifier)
    assert handle_agent(SimpleNamespace(action="status", agent_id="agent-1"), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="schedule"), True, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="notifications"), False, json_payloads.append, printed.append, run_operation, *deps) == 0
    assert handle_agent(SimpleNamespace(action="remove", agent_id="missing"), False, json_payloads.append, printed.append, run_operation, *deps) == 1
    assert handle_agent(
        SimpleNamespace(action="notify", agent_id="missing", webhook="https://example.com/hook", min_severity="low"),
        False,
        json_payloads.append,
        printed.append,
        run_operation,
        *deps,
    ) == 1
    assert handle_agent(
        SimpleNamespace(action="notify", agent_id="agent-1", webhook="notaurl", min_severity="low"),
        False,
        json_payloads.append,
        printed.append,
        run_operation,
        *deps,
    ) == 1
    assert handle_agent(
        SimpleNamespace(action="notify", agent_id="agent-1", webhook="https://example.com/hook", min_severity="medium"),
        False,
        json_payloads.append,
        printed.append,
        run_operation,
        *deps,
    ) == 0

    fallback_deps = (_Registry, _SchedulerNoop, _Planner, _Notifier)
    assert handle_agent(SimpleNamespace(action="run", agent_id="agent-1"), False, json_payloads.append, printed.append, run_operation, *fallback_deps) == 0
    unavailable_deps = (_Registry, _SchedulerNoop, _PlannerUnavailable, _Notifier)
    assert handle_agent(SimpleNamespace(action="run", agent_id="agent-1"), False, json_payloads.append, printed.append, run_operation, *unavailable_deps) == 1

    empty_deps = (_EmptyRegistry, _SchedulerWithoutRun, _Planner, _Notifier)
    assert handle_agent(SimpleNamespace(action="list"), False, json_payloads.append, printed.append, run_operation, *empty_deps) == 0
    assert handle_agent(SimpleNamespace(action="schedule"), False, json_payloads.append, printed.append, run_operation, *empty_deps) == 0
    assert handle_agent(SimpleNamespace(action="logs", agent_id="agent-1"), False, json_payloads.append, printed.append, run_operation, *empty_deps) == 0


def test_firewall_command_handler_branches():
    printed = []
    json_payloads = []
    run_operation = MagicMock(return_value=True)

    assert handle_firewall(SimpleNamespace(action="status"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="status"), True, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="ports"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="ports"), True, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="services"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="services"), True, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="zones"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="zones"), True, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="list-zones"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="list-zones"), True, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="add-service", service="ssh", zone=None), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="add-service", service="", zone=None), False, json_payloads.append, printed.append, run_operation, _Firewall) == 1
    assert handle_firewall(SimpleNamespace(action="remove-service", service="ssh", zone=None), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="add-port", port="8080/tcp", zone=None), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="add-port", port="", zone=None), False, json_payloads.append, printed.append, run_operation, _Firewall) == 1
    assert handle_firewall(SimpleNamespace(action="remove-port", port="8080/tcp", zone=None), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="set-default-zone", zone="public"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="set-default-zone", zone=""), False, json_payloads.append, printed.append, run_operation, _Firewall) == 1
    assert handle_firewall(SimpleNamespace(action="reload"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="open-port", spec="8080"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="open-port", spec="8080/udp"), True, json_payloads.append, printed.append, run_operation, _Firewall) == 0
    assert handle_firewall(SimpleNamespace(action="open-port", spec=""), False, json_payloads.append, printed.append, run_operation, _Firewall) == 1
    assert handle_firewall(SimpleNamespace(action="close-port", spec="8080/tcp"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 1
    assert handle_firewall(SimpleNamespace(action="close-port", spec=""), False, json_payloads.append, printed.append, run_operation, _Firewall) == 1
    assert handle_firewall(SimpleNamespace(action="status"), False, json_payloads.append, printed.append, run_operation, _FirewallUnavailable) == 1
    assert handle_firewall(SimpleNamespace(action="unknown"), False, json_payloads.append, printed.append, run_operation, _Firewall) == 1


def test_release_readiness_dialog_worker_and_actions():
    report = ReleaseReadinessReport(
        target="Fedora KDE 44",
        generated_at=1.0,
        score=100,
        status="ready",
        summary="ready",
        checks=[
            ReadinessCheck(
                id="fedora-version",
                title="Fedora Version",
                category="system",
                status="pass",
                severity="info",
                summary="Fedora 44",
                beginner_guidance="ok",
                command_preview=["cat", "/etc/os-release"],
                advanced_detail="detail",
            )
        ],
        target_metadata=TARGETS["44"],
    )

    dialog = ReleaseReadinessDialog(auto_run=False)
    dialog.report = report
    dialog.advanced_toggle.setChecked(True)
    dialog.copy_support_summary()
    assert "Fedora KDE 44" in QApplication.clipboard().text()

    dialog.severity_filter.setCurrentIndex(dialog.severity_filter.findData("error"))
    dialog._render()

    with patch("ui.release_readiness_dialog.ReleaseReadiness.run", return_value=report):
        worker = ReadinessWorker("44")
        seen = []
        worker.finished.connect(seen.append)
        worker.run()
        assert seen[0] is report

    with patch("ui.release_readiness_dialog.ReleaseReadiness.run", side_effect=RuntimeError("boom")):
        worker = ReadinessWorker("44")
        errors = []
        worker.failed.connect(errors.append)
        worker.run()
        assert errors == ["boom"]

    with patch("ui.release_readiness_dialog.QFileDialog.getSaveFileName", return_value=("/tmp/test.json", "")):
        with patch("ui.release_readiness_dialog.SupportBundleV4.save_json", side_effect=OSError("no")):
            with patch("ui.release_readiness_dialog.QMessageBox.warning") as warning:
                dialog.export_support_bundle()
                warning.assert_called_once()
