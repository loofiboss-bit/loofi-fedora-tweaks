"""Tests for ui/maintenance_tab.py — MaintenanceTab and all sub-tabs.

Comprehensive tests covering:
- MaintenanceTab metadata and widget creation
- _UpdatesSubTab: system updates, flatpak, firmware, update-all queue
- _CleanupSubTab: dnf cache clean, autoremove, timeshift check
- _OverlaysSubTab: layered packages, remove, reset, reboot
- _SmartUpdatesSubTab: check updates, preview conflicts, schedule, rollback

All PyQt6 classes are stubbed at module level — no real QApplication needed.
"""
# pyright: reportAttributeAccessIssue=false

import importlib
import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loofi-fedora-tweaks"))


# ---------------------------------------------------------------------------
# PyQt6 + dependency stubs (installed before importing the module under test)
# ---------------------------------------------------------------------------

_original_modules = {}


def _install_stubs():
    """Replace PyQt6 and direct dependencies with lightweight stubs."""

    class _Dummy:
        """Dummy widget/object that accepts any constructor args.

        Returns MagicMock for unknown attributes to support chained
        attribute access like ``btn.clicked.connect(fn)``.
        The ``tr()`` method returns the input string so ``.format()``
        works on the result.
        """

        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            if name == "tr":
                return lambda text, *a, **kw: text
            return MagicMock()

    # --- QMessageBox stub with StandardButton enum ---
    class _StubStandardButton:
        Yes = 1
        No = 0

    class _StubQMessageBox(_Dummy):
        StandardButton = _StubStandardButton
        warning = staticmethod(lambda *a, **kw: _StubStandardButton.No)
        question = staticmethod(lambda *a, **kw: _StubStandardButton.No)
        information = staticmethod(lambda *a, **kw: None)
        critical = staticmethod(lambda *a, **kw: None)

    # --- QColor stub ---
    class _StubQColor:
        def __init__(self, *args, **kwargs):
            pass

    # --- QListWidgetItem stub ---
    class _StubQListWidgetItem:
        def __init__(self, text=""):
            self._text = text

        def text(self):
            return self._text

        def setForeground(self, *args):
            pass

    # --- QtWidgets ---
    qt_widgets = types.ModuleType("PyQt6.QtWidgets")
    qt_widgets.QWidget = _Dummy
    qt_widgets.QVBoxLayout = _Dummy
    qt_widgets.QHBoxLayout = _Dummy
    qt_widgets.QLabel = _Dummy
    qt_widgets.QPushButton = _Dummy
    qt_widgets.QTextEdit = _Dummy
    qt_widgets.QGroupBox = _Dummy
    qt_widgets.QProgressBar = _Dummy
    qt_widgets.QTabWidget = _Dummy
    qt_widgets.QListWidget = _Dummy
    qt_widgets.QListWidgetItem = _StubQListWidgetItem
    qt_widgets.QFrame = _Dummy
    qt_widgets.QMessageBox = _StubQMessageBox
    qt_widgets.QInputDialog = type(
        "QInputDialog",
        (),
        {"getText": staticmethod(lambda *a, **kw: ("", False))},
    )
    qt_widgets.QTableWidget = _Dummy
    qt_widgets.QTableWidgetItem = _Dummy
    qt_widgets.QFileDialog = _Dummy

    # --- QtCore ---
    qt_core = types.ModuleType("PyQt6.QtCore")
    qt_core.Qt = types.SimpleNamespace(
        GlobalColor=types.SimpleNamespace(darkGray=0),
    )
    qt_core.QProcess = _Dummy
    qt_core.pyqtSignal = lambda *a, **kw: MagicMock()
    qt_core.QObject = _Dummy
    qt_core.QThread = _Dummy

    class _StubQTimer(_Dummy):
        """QTimer stub with singleShot as a static/class method."""
        singleShot = staticmethod(lambda ms, fn: fn())

    qt_core.QTimer = _StubQTimer

    # --- QtGui ---
    qt_gui = types.ModuleType("PyQt6.QtGui")
    qt_gui.QColor = _StubQColor

    # --- PyQt6 root ---
    pyqt = types.ModuleType("PyQt6")
    pyqt.QtWidgets = qt_widgets
    pyqt.QtCore = qt_core
    pyqt.QtGui = qt_gui

    # --- utils.command_runner ---
    class _StubCommandRunner:
        """Minimal CommandRunner stub with signal-like attributes."""

        def __init__(self, *args, **kwargs):
            self.output_received = MagicMock()
            self.progress_update = MagicMock()
            self.finished = MagicMock()
            self.stderr_received = MagicMock()
            self.error_occurred = MagicMock()
            self.run_command = MagicMock()

    cmd_runner_mod = types.ModuleType("utils.command_runner")
    cmd_runner_mod.CommandRunner = _StubCommandRunner

    # --- ui.base_tab ---
    class _StubBaseTab(_Dummy):
        """BaseTab stub with real method implementations for testing."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.output_area = MagicMock()
            self.runner = _StubCommandRunner()
            self.runner.output_received.connect = MagicMock()
            self.runner.finished.connect = MagicMock()
            self.runner.error_occurred.connect = MagicMock()
            self.runner.progress_update.connect = MagicMock()

        def run_command(self, cmd, args, description=""):
            self.output_area.clear()
            if description:
                self.append_output(f"{description}\n")
            self.runner.run_command(cmd, args)

        def append_output(self, text):
            self.output_area.moveCursor(MagicMock())
            self.output_area.insertPlainText(text)

        def on_command_finished(self, exit_code):
            pass

        def show_success(self, message):
            pass

        def show_error(self, message):
            pass

    base_tab_mod = types.ModuleType("ui.base_tab")
    base_tab_mod.BaseTab = _StubBaseTab

    # --- ui.tab_utils ---
    tab_utils_mod = types.ModuleType("ui.tab_utils")
    tab_utils_mod.configure_top_tabs = lambda *a, **kw: None

    # --- services.system ---
    services_system_mod = types.ModuleType("services.system")
    services_system_mod.__path__ = []
    services_system_mod.SystemManager = type(
        "SystemManager",
        (),
        {
            "get_package_manager": staticmethod(lambda: "dnf"),
            "is_atomic": staticmethod(lambda: False),
            "get_variant_name": staticmethod(lambda: "Workstation"),
            "get_layered_packages": staticmethod(lambda: []),
            "has_pending_deployment": staticmethod(lambda: False),
        },
    )

    services_system_system_mod = types.ModuleType("services.system.system")
    services_system_system_mod.cached_which = lambda name: f"/usr/bin/{name}"

    # --- core.plugins.metadata ---
    metadata_mod = types.ModuleType("core.plugins.metadata")

    class _StubPluginMetadata:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    metadata_mod.PluginMetadata = _StubPluginMetadata

    # --- core.plugins.interface ---
    interface_mod = types.ModuleType("core.plugins.interface")
    interface_mod.PluginInterface = _Dummy

    # --- utils.log ---
    utils_log_mod = types.ModuleType("utils.log")
    utils_log_mod.get_logger = lambda name: MagicMock()

    # --- utils.update_manager ---
    update_manager_mod = types.ModuleType("utils.update_manager")

    class _StubUpdateManager:
        """Stub UpdateManager with all static methods used by _SmartUpdatesSubTab."""

        @staticmethod
        def check_updates():
            return []

        @staticmethod
        def preview_conflicts(packages=None):
            return []

        @staticmethod
        def schedule_update(packages=None, when="now"):
            return MagicMock(id="test", packages=[], scheduled_time=when, timer_unit="test.timer")

        @staticmethod
        def get_schedule_commands(schedule):
            return []

        @staticmethod
        def rollback_last():
            return (
                "pkexec",
                ["dnf", "history", "undo", "last", "-y"],
                "Rolling back...",
            )

        @staticmethod
        def get_update_history(limit=10):
            return []

    update_manager_mod.UpdateManager = _StubUpdateManager

    # Register in sys.modules
    _module_map = {
        "PyQt6": pyqt,
        "PyQt6.QtWidgets": qt_widgets,
        "PyQt6.QtCore": qt_core,
        "PyQt6.QtGui": qt_gui,
        "ui.base_tab": base_tab_mod,
        "ui.tab_utils": tab_utils_mod,
        "utils.command_runner": cmd_runner_mod,
        "services.system": services_system_mod,
        "services.system.system": services_system_system_mod,
        "core.plugins.metadata": metadata_mod,
        "core.plugins.interface": interface_mod,
        "utils.log": utils_log_mod,
        "utils.update_manager": update_manager_mod,
    }

    for name, mod in _module_map.items():
        _original_modules[name] = sys.modules.get(name)
        sys.modules[name] = mod


def _uninstall_stubs():
    """Restore original modules."""
    for name, mod in _original_modules.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


# Install stubs before importing the module under test
_install_stubs()
sys.modules.pop("ui.maintenance_tab", None)
_mt = importlib.import_module("ui.maintenance_tab")

# Keep references to stub classes for patching
_QMessageBox = sys.modules["PyQt6.QtWidgets"].QMessageBox
_QInputDialog = sys.modules["PyQt6.QtWidgets"].QInputDialog
_SystemManager = sys.modules["services.system"].SystemManager

# Restore original modules immediately so collection of other test files
# is not polluted.  Keep ui.maintenance_tab — @patch decorators need it.
for _name, _orig in _original_modules.items():
    if _name == "ui.maintenance_tab":
        continue
    if _orig is not None:
        sys.modules[_name] = _orig
    else:
        sys.modules.pop(_name, None)


# ===================================================================
# Test: MaintenanceTab
# ===================================================================


class TestMaintenanceTabMetadata(unittest.TestCase):
    """Tests for MaintenanceTab.metadata() and create_widget()."""

    def setUp(self):
        self.tab = _mt.MaintenanceTab()

    def test_metadata_returns_plugin_metadata(self):
        """metadata() returns a PluginMetadata instance."""
        meta = self.tab.metadata()
        self.assertIsNotNone(meta)

    def test_metadata_id(self):
        """metadata().id is 'maintenance'."""
        self.assertEqual(self.tab.metadata().id, "maintenance")

    def test_metadata_name(self):
        """metadata().name is 'Maintenance'."""
        self.assertEqual(self.tab.metadata().name, "Maintenance")

    def test_metadata_category(self):
        """metadata().category is 'Packages'."""
        self.assertEqual(self.tab.metadata().category, "Packages")

    def test_metadata_icon(self):
        """metadata() has an icon set."""
        self.assertTrue(len(self.tab.metadata().icon) > 0)

    def test_create_widget_returns_self(self):
        """create_widget() returns self."""
        self.assertIs(self.tab.create_widget(), self.tab)

    def test_has_tabs_attribute(self):
        """MaintenanceTab has a tabs attribute."""
        self.assertTrue(hasattr(self.tab, "tabs"))

    def test_has_action_center_subtab_factory(self):
        """MaintenanceTab exposes the v11 Action Center as a real GUI sub-tab."""
        labels = [label for label, _factory in self.tab._sub_tab_factories]
        self.assertIn("Action Center", labels)

    def test_has_health_timeline_subtab_factory(self):
        """MaintenanceTab exposes the v12 Health Timeline as a Maintenance sub-tab."""
        labels = [label for label, _factory in self.tab._sub_tab_factories]
        self.assertIn("Health Timeline", labels)


# ===================================================================
# Test: _UpdatesSubTab — static helper
# ===================================================================


class TestUpdatesSubTabSystemUpdateStep(unittest.TestCase):
    """Tests for _UpdatesSubTab._system_update_step()."""

    def test_dnf_returns_pkexec(self):
        """DNF step returns 'pkexec' as binary."""
        cmd, args, desc = _mt._UpdatesSubTab._system_update_step("dnf")
        self.assertEqual(cmd, "pkexec")

    def test_dnf_returns_update_args(self):
        """DNF step args contain 'dnf', 'update', '-y'."""
        cmd, args, desc = _mt._UpdatesSubTab._system_update_step("dnf")
        self.assertEqual(args, ["dnf", "update", "-y"])

    def test_dnf_returns_update_description(self):
        """DNF step description says 'Update'."""
        cmd, args, desc = _mt._UpdatesSubTab._system_update_step("dnf")
        self.assertIn("Update", desc)

    def test_rpm_ostree_returns_pkexec(self):
        """rpm-ostree step returns 'pkexec' as binary."""
        cmd, args, desc = _mt._UpdatesSubTab._system_update_step("rpm-ostree")
        self.assertEqual(cmd, "pkexec")

    def test_rpm_ostree_returns_upgrade_args(self):
        """rpm-ostree step args contain 'rpm-ostree' and 'upgrade'."""
        cmd, args, desc = _mt._UpdatesSubTab._system_update_step("rpm-ostree")
        self.assertEqual(args, ["rpm-ostree", "upgrade"])

    def test_rpm_ostree_returns_upgrade_description(self):
        """rpm-ostree step description says 'Upgrade'."""
        cmd, args, desc = _mt._UpdatesSubTab._system_update_step("rpm-ostree")
        self.assertIn("Upgrade", desc)


# ===================================================================
# Test: _ActionCenterSubTab
# ===================================================================


class TestUpgradeAssistantSubTab(unittest.TestCase):
    """Tests for the Upgrade Assistant GUI surface."""

    @patch("core.diagnostics.release_readiness.ReleaseReadiness.list_targets")
    def test_init_renders_targets_and_changes(self, list_targets):
        list_targets.return_value = [
            SimpleNamespace(
                key="45-preview",
                label="Fedora 45 Preview",
                status_label="Preview",
                release_phase="planning",
                important_changes=[SimpleNamespace(title="Qt", summary="Packaging shift")],
            )
        ]

        tab = _mt._UpgradeAssistantSubTab()

        self.assertIsNotNone(tab)
        list_targets.assert_called_once_with()

    @patch.object(_QMessageBox, "information")
    @patch("core.export.support_bundle_v5.SupportBundleV5.save_json")
    @patch("core.diagnostics.release_readiness.ReleaseReadiness.list_targets", return_value=[])
    def test_export_bundle_shows_success(self, _list_targets, save_json, information):
        tab = _mt._UpgradeAssistantSubTab()

        tab._export_bundle("45-preview")

        save_json.assert_called_once_with("loofi-readiness-45-preview.json", target="45-preview")
        information.assert_called_once()

    @patch.object(_QMessageBox, "critical")
    @patch("core.export.support_bundle_v5.SupportBundleV5.save_json", side_effect=RuntimeError("write failed"))
    @patch("core.diagnostics.release_readiness.ReleaseReadiness.list_targets", return_value=[])
    def test_export_bundle_shows_failure(self, _list_targets, _save_json, critical):
        tab = _mt._UpgradeAssistantSubTab()

        tab._export_bundle("44")

        critical.assert_called_once()


class TestActionCenterSubTab(unittest.TestCase):
    """Tests for the v11 Action Center GUI surface."""

    def setUp(self):
        def run_inline(_tab, operation, on_success, _failure_title):
            on_success(operation())

        self.operation_patcher = patch.object(
            _mt._ActionCenterSubTab,
            "_start_operation",
            autospec=True,
            side_effect=run_inline,
        )
        self.operation_patcher.start()

    def tearDown(self):
        self.operation_patcher.stop()

    def _item(self):
        return SimpleNamespace(
            id="readiness-test",
            title="Review repository risk",
            source="readiness:44",
            description="Repository changes need review.",
            risk_level="medium",
            privilege="none",
            command_preview=["dnf", "repolist"],
            verification_command=["dnf", "repolist"],
            rollback_hint="Disable the repository if it causes package issues.",
            manual_only=False,
            state="planned",
            metadata={},
        )

    def _catalog_item(self, action_id="fstrim-all"):
        item = self._item()
        item.id = action_id
        item.title = action_id
        item.source = "catalog:v14"
        item.command_preview = []
        item.risk_level = "low" if action_id != "restart-failed-service" else "medium"
        return item

    @patch("core.actions.center.ActionCenterService")
    def test_load_target_uses_action_center_service(self, service_cls):
        service = service_cls.return_value
        service.candidates_from_readiness.return_value = [self._item()]

        tab = _mt._ActionCenterSubTab()

        service.candidates_from_readiness.assert_called_with("44")
        self.assertEqual(tab._items[0].id, "readiness-test")

    @patch("core.actions.center.ActionCenterService")
    def test_merged_items_keeps_full_catalog_without_duplicate_adapter(self, service_cls):
        service = service_cls.return_value
        catalog_item = self._catalog_item("dnf-clean-all")
        adapter = self._item()
        adapter.id = "readiness-repo-cache-clean"
        manual = self._item()
        manual.id = "manual-guidance"
        service.catalog_items.return_value = [catalog_item]
        service.candidates_from_readiness.return_value = [adapter, manual]
        tab = _mt._ActionCenterSubTab()

        items = tab._merged_items("44")

        self.assertEqual([item.id for item in items], ["dnf-clean-all", "manual-guidance"])

    @patch("core.actions.center.ActionCenterService")
    def test_preview_selected_uses_preview_not_execution(self, service_cls):
        service = service_cls.return_value
        service.candidates_from_readiness.return_value = []
        service.preview.return_value = SimpleNamespace(message="preview ok")

        tab = _mt._ActionCenterSubTab()
        tab._items = [self._item()]
        tab.action_list = MagicMock()
        tab.action_list.currentRow.return_value = 0
        tab.detail_area = MagicMock()

        tab._preview_selected()

        service.preview.assert_called_once_with(tab._items[0])
        self.assertFalse(service.execute_next.called)
        tab.detail_area.setPlainText.assert_called_once()

    @patch("core.actions.center.ActionCenterService")
    def test_catalog_preview_defers_exact_command_to_fresh_plan(self, service_cls):
        service_cls.return_value.candidates_from_readiness.return_value = []
        tab = _mt._ActionCenterSubTab()
        tab._items = [self._catalog_item()]
        tab.action_list = MagicMock()
        tab.action_list.currentRow.return_value = 0
        tab.detail_area = MagicMock()

        tab._preview_selected()

        service_cls.return_value.preview.assert_not_called()
        detail = tab.detail_area.setPlainText.call_args.args[0]
        self.assertIn("fresh preflight", detail)

    @patch.object(_QInputDialog, "getText", staticmethod(lambda *a, **kw: ("broken.service", True)))
    @patch("core.actions.center.ActionCenterService")
    def test_restart_catalog_item_prompts_for_exact_service(self, service_cls):
        service_cls.return_value.candidates_from_readiness.return_value = []
        tab = _mt._ActionCenterSubTab()
        tab._items = [self._catalog_item("restart-failed-service")]
        tab.action_list = MagicMock()
        tab.action_list.currentRow.return_value = 0
        orchestrator = MagicMock()
        policy = MagicMock(reason_code="preflight_ok", explanation="ready")
        orchestrator.plan.return_value = MagicMock(
            plan_id="plan-service",
            action_id="restart-failed-service",
            state="needs_review",
            risk_level="medium",
            privileged=True,
            policy_decision=policy,
            preview=["systemctl", "restart", "broken.service"],
            recovery_guidance="Inspect logs.",
            expires_at=2000.0,
        )
        tab._orchestrator = orchestrator

        tab._plan_selected()

        orchestrator.plan.assert_called_once_with(
            "restart-failed-service",
            {"service": "broken.service"},
            target="44",
        )

    @patch("core.actions.center.ActionCenterService")
    def test_review_creates_canonical_plan_without_execution(self, service_cls):
        service_cls.return_value.candidates_from_readiness.return_value = []
        tab = _mt._ActionCenterSubTab()
        item = self._item()
        item.id = "readiness-repo-cache-clean"
        item.metadata = {}
        tab._items = [item]
        tab.action_list = MagicMock()
        tab.action_list.currentRow.return_value = 0
        tab.detail_area = MagicMock()
        tab.run_button = MagicMock()
        tab.verify_button = MagicMock()
        orchestrator = MagicMock()
        policy = MagicMock(reason_code="preflight_ok", explanation="ready")
        orchestrator.plan.return_value = MagicMock(
            plan_id="plan-1",
            action_id="dnf-clean-all",
            state="ready",
            risk_level="low",
            privileged=True,
            policy_decision=policy,
            preview=["dnf", "clean", "all"],
            recovery_guidance="Rebuild metadata.",
            expires_at=2000.0,
        )
        tab._orchestrator = orchestrator

        tab._plan_selected()

        orchestrator.plan.assert_called_once_with("dnf-clean-all", {}, target="44")
        orchestrator.prepare_run.assert_not_called()
        tab.run_button.setEnabled.assert_called_with(True)

    @patch.object(
        _QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: _QMessageBox.StandardButton.Yes),
    )
    @patch("core.actions.center.ActionCenterService")
    def test_run_plan_uses_async_command_runner_then_records_result(self, service_cls):
        service_cls.return_value.candidates_from_readiness.return_value = []
        tab = _mt._ActionCenterSubTab()
        tab.run_button = MagicMock()
        tab.verify_button = MagicMock()
        tab._current_plan = MagicMock(
            plan_id="plan-1",
            risk_level="low",
            rollback_supported=True,
        )
        prepared = MagicMock(
            run_id="run-1",
            action_id="dnf-clean-all",
            command=("dnf", "clean", "all"),
            privileged=True,
        )
        run = MagicMock(
            run_id="run-1",
            plan_id="plan-1",
            action_id="dnf-clean-all",
            state="verifying",
            execution_result={"message": "finished"},
            verification_result=None,
            recovery_status="available",
        )
        orchestrator = MagicMock()
        orchestrator.prepare_run.return_value = prepared
        orchestrator.facade.asynchronous_execution_vector.return_value = ["pkexec", "dnf", "clean", "all"]
        orchestrator.complete_run.return_value = run
        tab._orchestrator = orchestrator

        tab._run_current_plan()

        tab.runner.run_command.assert_called_once_with("pkexec", ["dnf", "clean", "all"])
        orchestrator.complete_run.assert_not_called()

        tab.on_command_finished(0)

        orchestrator.complete_run.assert_called_once()
        self.assertEqual(tab._current_run.state, "verifying")
        tab.verify_button.setEnabled.assert_called_with(True)

    @patch("core.actions.center.ActionCenterService")
    def test_cancel_keeps_lease_until_process_finished(self, service_cls):
        service_cls.return_value.candidates_from_readiness.return_value = []
        tab = _mt._ActionCenterSubTab()
        prepared = MagicMock(run_id="run-1", action_id="dnf-clean-all")
        interrupted = MagicMock(
            run_id="run-1",
            plan_id="plan-1",
            action_id="dnf-clean-all",
            state="interrupted",
            execution_result=None,
            verification_result=None,
            recovery_status="manual-review-required",
        )
        orchestrator = MagicMock()
        orchestrator.interrupt_run.return_value = interrupted
        tab._orchestrator = orchestrator
        tab._prepared_run = prepared
        tab.runner = MagicMock()
        tab.runner.is_running.return_value = True

        tab._cancel_command()

        tab.runner.stop.assert_called_once_with()
        orchestrator.interrupt_run.assert_not_called()
        self.assertIs(tab._prepared_run, prepared)

        tab.on_command_finished(-15)

        orchestrator.interrupt_run.assert_called_once_with("run-1", "user-cancelled")
        self.assertIsNone(tab._prepared_run)

    @patch("core.actions.center.ActionCenterService")
    def test_verify_current_run_uses_background_operation_result(self, service_cls):
        service_cls.return_value.candidates_from_readiness.return_value = []
        tab = _mt._ActionCenterSubTab()
        tab.verify_button = MagicMock()
        tab.detail_area = MagicMock()
        pending = MagicMock(run_id="run-1")
        verified = MagicMock(
            run_id="run-1",
            plan_id="plan-1",
            action_id="fstrim-all",
            state="succeeded",
            execution_result={"message": "done"},
            verification_result={"message": "verified"},
            recovery_status="not-required",
        )
        orchestrator = MagicMock()
        orchestrator.verify.return_value = verified
        tab._orchestrator = orchestrator
        tab._current_run = pending

        tab._verify_current_run()

        orchestrator.verify.assert_called_once_with("run-1")
        self.assertIs(tab._current_run, verified)
        tab.verify_button.setEnabled.assert_called_with(False)

    @patch("core.actions.center.ActionCenterService")
    def test_start_operation_wires_worker_thread_lifecycle(self, service_cls):
        service_cls.return_value.candidates_from_readiness.return_value = []
        tab = _mt._ActionCenterSubTab()
        self.operation_patcher.stop()
        tab._operation_thread = None

        tab._start_operation(lambda: "ok", MagicMock(), "failed")

        self.assertIsNotNone(tab._operation_thread)
        tab._clear_operation_worker()
        self.assertIsNone(tab._operation_thread)
        self.operation_patcher.start()

    def test_ui_layer_has_no_subprocess_import(self):
        from pathlib import Path

        source = Path(_mt.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import subprocess", source)


# ===================================================================
# Test: _HealthTimelineSubTab
# ===================================================================


class TestHealthTimelineSubTab(unittest.TestCase):
    """Tests for the v12 Health Timeline GUI surface."""

    def _summary_cls(self):
        class _Analyzer:
            def __init__(self, snapshots):
                self.snapshots = snapshots

            def analyze(self):
                return SimpleNamespace(
                    summary=f"{len(self.snapshots)} snapshot(s) loaded",
                    new=[object()],
                    recurring=[object(), object()],
                    resolved=[],
                    worsening=[object()],
                )

        return _Analyzer

    @patch("core.observability.MaintenanceTrendAnalyzer")
    @patch("core.observability.ObservabilityService")
    def test_load_timeline_renders_summary_and_recent_items(self, service_cls, analyzer_cls):
        analyzer_cls.side_effect = self._summary_cls()
        snapshots = [
            SimpleNamespace(timestamp=1.0, problem_fingerprints=[]),
            SimpleNamespace(timestamp=2.0, problem_fingerprints=[object(), object()]),
        ]
        service_cls.return_value.snapshots.load.return_value = snapshots

        tab = _mt._HealthTimelineSubTab()
        tab.timeline_list = MagicMock()
        tab.summary_label = MagicMock()
        tab.detail_area = MagicMock()

        tab._load_timeline()

        tab.timeline_list.clear.assert_called_once_with()
        self.assertEqual(tab.timeline_list.addItem.call_count, 2)
        tab.summary_label.setText.assert_called_with("2 snapshot(s) loaded")
        detail = tab.detail_area.setPlainText.call_args.args[0]
        self.assertIn("Snapshots: 2", detail)
        self.assertIn("Recurring: 2", detail)

    @patch.object(_QMessageBox, "warning")
    @patch("core.observability.MaintenanceTrendAnalyzer")
    @patch("core.observability.ObservabilityService")
    def test_record_snapshot_handles_collection_failure(self, service_cls, analyzer_cls, warning):
        analyzer_cls.side_effect = self._summary_cls()
        service_cls.return_value.snapshots.load.return_value = []
        service_cls.return_value.collect_snapshot.side_effect = RuntimeError("read failed")

        tab = _mt._HealthTimelineSubTab()
        tab._load_timeline = MagicMock()

        tab._record_snapshot()

        warning.assert_called_once()
        tab._load_timeline.assert_not_called()

    @patch("core.observability.MaintenanceTrendAnalyzer")
    @patch("core.observability.ObservabilityService")
    def test_record_snapshot_refreshes_on_success(self, service_cls, analyzer_cls):
        analyzer_cls.side_effect = self._summary_cls()
        service_cls.return_value.snapshots.load.return_value = []

        tab = _mt._HealthTimelineSubTab()
        tab._load_timeline = MagicMock()

        tab._record_snapshot()

        service_cls.return_value.collect_snapshot.assert_called_with(target="44", source="gui")
        tab._load_timeline.assert_called_once_with()


# ===================================================================
# Test: _UpdatesSubTab — instance methods
# ===================================================================


class TestUpdatesSubTabInstance(unittest.TestCase):
    """Tests for _UpdatesSubTab instance methods."""

    def setUp(self):
        self.tab = _mt._UpdatesSubTab()
        # Replace internal widgets/runner with mocks for introspection
        self.tab.output_area = MagicMock()
        self.tab.progress_bar = MagicMock()
        self.tab.progress_bar.value.return_value = 0
        self.tab.runner = MagicMock()
        self.tab.btn_dnf = MagicMock()
        self.tab.btn_flatpak = MagicMock()
        self.tab.btn_fw = MagicMock()
        self.tab.btn_update_all = MagicMock()

    # -- start_process --

    def test_start_process_clears_output(self):
        """start_process() clears the output area."""
        self.tab.start_process()
        self.tab.output_area.clear.assert_called_once()

    def test_start_process_resets_progress(self):
        """start_process() resets progress bar to 0."""
        self.tab.start_process()
        self.tab.progress_bar.setValue.assert_called_with(0)

    def test_start_process_disables_dnf_button(self):
        """start_process() disables the DNF button."""
        self.tab.start_process()
        self.tab.btn_dnf.setEnabled.assert_called_with(False)

    def test_start_process_disables_flatpak_button(self):
        """start_process() disables the Flatpak button."""
        self.tab.start_process()
        self.tab.btn_flatpak.setEnabled.assert_called_with(False)

    def test_start_process_disables_fw_button(self):
        """start_process() disables the firmware button."""
        self.tab.start_process()
        self.tab.btn_fw.setEnabled.assert_called_with(False)

    def test_start_process_disables_update_all_button(self):
        """start_process() disables the update-all button."""
        self.tab.start_process()
        self.tab.btn_update_all.setEnabled.assert_called_with(False)

    # -- append_output --

    def test_append_output_inserts_text(self):
        """append_output() inserts plain text into output_area."""
        self.tab.append_output("hello")
        self.tab.output_area.insertPlainText.assert_called_with("hello")

    # -- update_progress --

    def test_update_progress_indeterminate(self):
        """update_progress(-1, status) sets indeterminate range."""
        self.tab.update_progress(-1, "Working...")
        self.tab.progress_bar.setRange.assert_called_with(0, 0)

    def test_update_progress_percentage(self):
        """update_progress(50, status) sets value to 50."""
        self.tab.update_progress(50, "Halfway")
        self.tab.progress_bar.setRange.assert_called_with(0, 100)
        self.tab.progress_bar.setValue.assert_called_with(50)

    def test_update_progress_percentage_format(self):
        """update_progress(50, status) sets format string with percentage."""
        self.tab.update_progress(50, "Halfway")
        self.tab.progress_bar.setFormat.assert_called_with("50% - Halfway")

    # -- run_single_command --

    def test_run_single_command_clears_output(self):
        """run_single_command() clears output before running."""
        self.tab.run_single_command("rpm", ["-qa", "kernel"], "Listing...")
        self.tab.output_area.clear.assert_called_once()

    def test_run_single_command_runs_command(self):
        """run_single_command() calls runner.run_command."""
        self.tab.run_single_command("rpm", ["-qa", "kernel"], "Listing...")
        self.tab.runner.run_command.assert_called_once_with("rpm", ["-qa", "kernel"])

    # -- run_flatpak_update --

    def test_run_flatpak_update_starts_process(self):
        """run_flatpak_update() calls start_process."""
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_flatpak_update()
        self.tab.start_process.assert_called_once()

    def test_run_flatpak_update_runs_flatpak(self):
        """run_flatpak_update() runs 'flatpak update -y'."""
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_flatpak_update()
        self.tab.runner.run_command.assert_called_once_with("flatpak", ["update", "-y"])

    # -- run_fw_update --

    @patch("utils.safety.SafetyManager.confirm_action", return_value=False)
    def test_run_fw_update_not_confirmed(self, mock_confirm):
        """run_fw_update() returns early if not confirmed."""
        self.tab.start_process = MagicMock()
        self.tab.run_fw_update()
        self.tab.start_process.assert_not_called()

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    def test_run_fw_update_confirmed(self, mock_confirm):
        """run_fw_update() runs fwupdmgr when confirmed."""
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_fw_update()
        self.tab.start_process.assert_called_once()
        self.tab.runner.run_command.assert_called_once_with("pkexec", ["fwupdmgr", "update", "-y"])

    # -- run_dnf_update --

    @patch("utils.safety.SafetyManager.confirm_action", return_value=False)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_dnf_update_not_confirmed(self, mock_lock, mock_confirm):
        """run_dnf_update() returns early if not confirmed."""
        self.tab.package_manager = "dnf"
        self.tab.start_process = MagicMock()
        self.tab.run_dnf_update()
        self.tab.start_process.assert_not_called()

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=True)
    def test_run_dnf_update_locked(self, mock_lock, mock_confirm):
        """run_dnf_update() shows warning when dnf is locked."""
        self.tab.package_manager = "dnf"
        self.tab.start_process = MagicMock()
        self.tab.run_dnf_update()
        self.tab.start_process.assert_not_called()

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_dnf_update_success(self, mock_lock, mock_confirm):
        """run_dnf_update() runs system update when confirmed and unlocked."""
        self.tab.package_manager = "dnf"
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_dnf_update()
        self.tab.start_process.assert_called_once()
        self.tab.runner.run_command.assert_called_once_with("pkexec", ["dnf", "update", "-y"])

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_dnf_update_rpm_ostree(self, mock_lock, mock_confirm):
        """run_dnf_update() uses rpm-ostree upgrade on atomic systems."""
        self.tab.package_manager = "rpm-ostree"
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_dnf_update()
        self.tab.start_process.assert_called_once()
        self.tab.runner.run_command.assert_called_once_with("pkexec", ["rpm-ostree", "upgrade"])

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_dnf_update_skips_lock_check_for_ostree(self, mock_lock, mock_confirm):
        """run_dnf_update() skips dnf lock check when package_manager is rpm-ostree."""
        self.tab.package_manager = "rpm-ostree"
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_dnf_update()
        mock_lock.assert_not_called()

    # -- run_update_all --

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=True)
    def test_run_update_all_locked(self, mock_lock, mock_confirm):
        """run_update_all() shows warning when dnf is locked."""
        self.tab.package_manager = "dnf"
        self.tab.start_process = MagicMock()
        self.tab.run_update_all()
        self.tab.start_process.assert_not_called()

    @patch("utils.safety.SafetyManager.confirm_action", return_value=False)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_update_all_not_confirmed(self, mock_lock, mock_confirm):
        """run_update_all() returns early if not confirmed."""
        self.tab.package_manager = "dnf"
        self.tab.start_process = MagicMock()
        self.tab.run_update_all()
        self.tab.start_process.assert_not_called()

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_update_all_builds_queue(self, mock_lock, mock_confirm):
        """run_update_all() builds a 3-step update queue."""
        self.tab.package_manager = "dnf"
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_update_all()
        self.assertEqual(len(self.tab.update_queue), 3)
        self.assertEqual(self.tab.current_update_index, 0)

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_update_all_starts_first_command(self, mock_lock, mock_confirm):
        """run_update_all() starts the first command in the queue."""
        self.tab.package_manager = "dnf"
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_update_all()
        self.tab.runner.run_command.assert_called_once_with("pkexec", ["dnf", "update", "-y"])

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_update_all_queue_contains_flatpak(self, mock_lock, mock_confirm):
        """run_update_all() queue includes flatpak update step."""
        self.tab.package_manager = "dnf"
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_update_all()
        flatpak_step = self.tab.update_queue[1]
        self.assertEqual(flatpak_step[0], "flatpak")
        self.assertEqual(flatpak_step[1], ["update", "-y"])

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_update_all_queue_contains_firmware(self, mock_lock, mock_confirm):
        """run_update_all() queue includes firmware update step."""
        self.tab.package_manager = "dnf"
        self.tab.start_process = MagicMock()
        self.tab.append_output = MagicMock()
        self.tab.run_update_all()
        fw_step = self.tab.update_queue[2]
        self.assertEqual(fw_step[0], "pkexec")
        self.assertIn("fwupdmgr", fw_step[1])

    # -- on_command_finished --

    def test_on_command_finished_mid_queue_advances(self):
        """on_command_finished() advances to next command when queue is active."""
        self.tab.update_queue = [
            ("pkexec", ["dnf", "update", "-y"], "DNF Update"),
            ("flatpak", ["update", "-y"], "Flatpak Update"),
            ("pkexec", ["fwupdmgr", "update", "-y"], "Firmware Update"),
        ]
        self.tab.current_update_index = 0
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(0)
        self.assertEqual(self.tab.current_update_index, 1)
        self.tab.runner.run_command.assert_called_once_with("flatpak", ["update", "-y"])

    def test_on_command_finished_mid_queue_second_to_third(self):
        """on_command_finished() advances from index 1 to 2."""
        self.tab.update_queue = [
            ("pkexec", ["dnf", "update", "-y"], "DNF Update"),
            ("flatpak", ["update", "-y"], "Flatpak Update"),
            ("pkexec", ["fwupdmgr", "update", "-y"], "Firmware Update"),
        ]
        self.tab.current_update_index = 1
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(0)
        self.assertEqual(self.tab.current_update_index, 2)
        self.tab.runner.run_command.assert_called_once_with("pkexec", ["fwupdmgr", "update", "-y"])

    def test_on_command_finished_end_of_queue_re_enables(self):
        """on_command_finished() re-enables buttons at end of queue."""
        self.tab.update_queue = [
            ("pkexec", ["dnf", "update", "-y"], "DNF Update"),
        ]
        self.tab.current_update_index = 0
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(0)
        self.tab.btn_dnf.setEnabled.assert_called_with(True)
        self.tab.btn_flatpak.setEnabled.assert_called_with(True)
        self.tab.btn_fw.setEnabled.assert_called_with(True)
        self.tab.btn_update_all.setEnabled.assert_called_with(True)

    def test_on_command_finished_end_of_queue_sets_100(self):
        """on_command_finished() sets progress to 100% at end of queue."""
        self.tab.update_queue = [
            ("pkexec", ["dnf", "update", "-y"], "DNF Update"),
        ]
        self.tab.current_update_index = 0
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(0)
        self.tab.progress_bar.setValue.assert_called_with(100)

    def test_on_command_finished_clears_queue(self):
        """on_command_finished() clears queue after last command."""
        self.tab.update_queue = [
            ("pkexec", ["dnf", "update", "-y"], "DNF Update"),
        ]
        self.tab.current_update_index = 0
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(0)
        self.assertEqual(self.tab.update_queue, [])
        self.assertEqual(self.tab.current_update_index, 0)

    def test_on_command_finished_no_queue_re_enables(self):
        """on_command_finished() re-enables buttons when no queue is set."""
        self.tab.update_queue = []
        self.tab.current_update_index = 0
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(0)
        self.tab.btn_dnf.setEnabled.assert_called_with(True)

    def test_on_command_finished_appends_exit_code(self):
        """on_command_finished() appends exit code to output."""
        self.tab.update_queue = []
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(42)
        call_args = self.tab.append_output.call_args[0][0]
        self.assertIn("42", call_args)

    def test_on_command_finished_success_calls_show_success(self):
        """on_command_finished() calls show_success on exit code 0 (regression: AttributeError)."""
        self.tab.update_queue = []
        self.tab.append_output = MagicMock()
        self.tab.show_success = MagicMock()
        self.tab.on_command_finished(0)
        self.tab.show_success.assert_called_once()

    def test_on_command_finished_failure_calls_show_error(self):
        """on_command_finished() calls show_error on nonzero exit code (regression: AttributeError)."""
        self.tab.update_queue = []
        self.tab.append_output = MagicMock()
        self.tab.show_error = MagicMock()
        self.tab.on_command_finished(1)
        self.tab.show_error.assert_called_once()

    def test_show_success_no_attribute_error(self):
        """show_success() exists and does not raise AttributeError (regression)."""
        self.tab.show_success("Test message")

    def test_show_error_no_attribute_error(self):
        """show_error() exists and does not raise AttributeError (regression)."""
        self.tab.show_error("Test message")

    def test_show_success_single_arg_signature(self):
        """show_success() accepts a single message argument (regression: wrong signature)."""
        self.tab.append_output = MagicMock()
        try:
            self.tab.show_success("Done")
        except TypeError:
            self.fail("show_success() should accept a single message argument")

    def test_show_error_single_arg_signature(self):
        """show_error() accepts a single message argument (regression: wrong signature)."""
        self.tab.append_output = MagicMock()
        try:
            self.tab.show_error("Failed")
        except TypeError:
            self.fail("show_error() should accept a single message argument")


class TestCleanupSubTab(unittest.TestCase):
    """Tests for _CleanupSubTab methods."""

    def setUp(self):
        self.tab = _mt._CleanupSubTab()
        self.tab.output_area = MagicMock()
        self.tab.runner = MagicMock()

    # -- append_output --

    def test_append_output_inserts_text(self):
        """append_output() inserts text into output_area."""
        self.tab.append_output("cleaning...")
        self.tab.output_area.insertPlainText.assert_called_with("cleaning...")

    # -- on_command_finished --

    def test_on_command_finished_appends_exit_code(self):
        """on_command_finished() appends exit code message."""
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(0)
        call_args = self.tab.append_output.call_args[0][0]
        self.assertIn("0", call_args)

    def test_on_command_finished_nonzero_exit(self):
        """on_command_finished() shows nonzero exit code."""
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(1)
        call_args = self.tab.append_output.call_args[0][0]
        self.assertIn("1", call_args)

    # -- run_command --

    def test_run_command_clears_output(self):
        """run_command() clears output area first."""
        self.tab.append_output = MagicMock()
        self.tab.run_command("pkexec", ["dnf", "clean", "all"], "Cleaning...")
        self.tab.output_area.clear.assert_called_once()

    def test_run_command_runs_command(self):
        """run_command() calls runner.run_command."""
        self.tab.append_output = MagicMock()
        self.tab.run_command("pkexec", ["dnf", "clean", "all"], "Cleaning...")
        self.tab.runner.run_command.assert_called_once_with("pkexec", ["dnf", "clean", "all"])

    def test_run_command_appends_description(self):
        """run_command() appends description to output."""
        self.tab.append_output = MagicMock()
        self.tab.run_command("pkexec", ["dnf", "clean", "all"], "Cleaning...")
        self.tab.append_output.assert_called_once_with("Cleaning...\n")

    # -- check_timeshift --

    @patch("ui.maintenance_tab.cached_which", return_value="/usr/bin/timeshift")
    def test_check_timeshift_found(self, mock_which):
        """check_timeshift() runs timeshift --list when installed."""
        self.tab.run_command = MagicMock()
        self.tab.check_timeshift()
        self.tab.run_command.assert_called_once()
        args = self.tab.run_command.call_args[0]
        self.assertEqual(args[0], "pkexec")
        self.assertIn("timeshift", args[1])

    @patch("ui.maintenance_tab.cached_which", return_value=None)
    def test_check_timeshift_not_found(self, mock_which):
        """check_timeshift() reports not found when timeshift missing."""
        self.tab.append_output = MagicMock()
        self.tab.check_timeshift()
        call_args = self.tab.append_output.call_args[0][0]
        self.assertIn("not found", call_args.lower())

    # -- run_autoremove --

    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=True)
    def test_run_autoremove_locked(self, mock_lock):
        """run_autoremove() shows warning when dnf is locked."""
        self.tab.run_command = MagicMock()
        self.tab.run_autoremove()
        self.tab.run_command.assert_not_called()

    @patch("utils.safety.SafetyManager.confirm_action", return_value=False)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_autoremove_not_confirmed(self, mock_lock, mock_confirm):
        """run_autoremove() does nothing when not confirmed."""
        self.tab.run_command = MagicMock()
        self.tab.run_autoremove()
        self.tab.run_command.assert_not_called()

    @patch("utils.safety.SafetyManager.confirm_action", return_value=True)
    @patch("utils.safety.SafetyManager.check_dnf_lock", return_value=False)
    def test_run_autoremove_success(self, mock_lock, mock_confirm):
        """run_autoremove() runs autoremove when confirmed and unlocked."""
        self.tab.run_command = MagicMock()
        self.tab.run_autoremove()
        self.tab.run_command.assert_called_once()
        args = self.tab.run_command.call_args[0]
        self.assertEqual(args[0], "pkexec")
        self.assertIn("autoremove", args[1])

    def test_on_command_finished_success_calls_show_success(self):
        """on_command_finished() calls show_success on exit code 0 (regression: AttributeError)."""
        self.tab.append_output = MagicMock()
        self.tab.show_success = MagicMock()
        self.tab.on_command_finished(0)
        self.tab.show_success.assert_called_once()

    def test_on_command_finished_failure_calls_show_error(self):
        """on_command_finished() calls show_error on nonzero exit code (regression: AttributeError)."""
        self.tab.append_output = MagicMock()
        self.tab.show_error = MagicMock()
        self.tab.on_command_finished(1)
        self.tab.show_error.assert_called_once()

    def test_show_success_no_attribute_error(self):
        """show_success() exists and does not raise AttributeError (regression)."""
        self.tab.show_success("Test message")

    def test_show_error_no_attribute_error(self):
        """show_error() exists and does not raise AttributeError (regression)."""
        self.tab.show_error("Test message")

    def test_show_success_single_arg_signature(self):
        """show_success() accepts a single message argument (regression: wrong signature)."""
        self.tab.append_output = MagicMock()
        try:
            self.tab.show_success("Done")
        except TypeError:
            self.fail("show_success() should accept a single message argument")

    def test_show_error_single_arg_signature(self):
        """show_error() accepts a single message argument (regression: wrong signature)."""
        self.tab.append_output = MagicMock()
        try:
            self.tab.show_error("Failed")
        except TypeError:
            self.fail("show_error() should accept a single message argument")


# ===================================================================
# Test: _OverlaysSubTab
# ===================================================================


class TestOverlaysSubTab(unittest.TestCase):
    """Tests for _OverlaysSubTab methods."""

    def _make_tab(self):
        """Create an _OverlaysSubTab with PackageManager mocked."""
        with patch("utils.package_manager.PackageManager") as MockPM:
            mock_pm_instance = MagicMock()
            MockPM.return_value = mock_pm_instance
            tab = _mt._OverlaysSubTab()
            tab.packages_list = MagicMock()
            tab.reboot_warning = MagicMock()
            tab.btn_reboot = MagicMock()
            tab.btn_refresh = MagicMock()
            tab.btn_remove = MagicMock()
            tab.btn_reset = MagicMock()
            tab.reboot_runner = MagicMock()
            return tab, mock_pm_instance

    # -- refresh_list --

    @patch.object(
        _SystemManager,
        "has_pending_deployment",
        staticmethod(lambda: False),
    )
    @patch.object(
        _SystemManager,
        "get_layered_packages",
        staticmethod(lambda: ["vim", "htop"]),
    )
    def test_refresh_list_with_packages(self):
        """refresh_list() populates list when packages are layered."""
        tab, _ = self._make_tab()
        tab.refresh_list()
        tab.packages_list.clear.assert_called()
        # addItem called for each package
        self.assertEqual(tab.packages_list.addItem.call_count, 2)

    @patch.object(
        _SystemManager,
        "has_pending_deployment",
        staticmethod(lambda: False),
    )
    @patch.object(
        _SystemManager,
        "get_layered_packages",
        staticmethod(lambda: []),
    )
    def test_refresh_list_empty(self):
        """refresh_list() shows placeholder when no packages exist."""
        tab, _ = self._make_tab()
        tab.refresh_list()
        tab.packages_list.clear.assert_called()
        tab.packages_list.addItem.assert_called_once()

    @patch.object(
        _SystemManager,
        "has_pending_deployment",
        staticmethod(lambda: True),
    )
    @patch.object(
        _SystemManager,
        "get_layered_packages",
        staticmethod(lambda: []),
    )
    def test_refresh_list_pending_reboot(self):
        """refresh_list() shows reboot warning when pending deployment."""
        tab, _ = self._make_tab()
        tab.refresh_list()
        tab.reboot_warning.setVisible.assert_called_with(True)
        tab.btn_reboot.setVisible.assert_called_with(True)

    @patch.object(
        _SystemManager,
        "has_pending_deployment",
        staticmethod(lambda: False),
    )
    @patch.object(
        _SystemManager,
        "get_layered_packages",
        staticmethod(lambda: []),
    )
    def test_refresh_list_no_pending_reboot(self):
        """refresh_list() hides reboot warning when no pending deployment."""
        tab, _ = self._make_tab()
        tab.refresh_list()
        tab.reboot_warning.setVisible.assert_called_with(False)
        tab.btn_reboot.setVisible.assert_called_with(False)

    # -- remove_selected --

    def test_remove_selected_no_selection(self):
        """remove_selected() shows warning when nothing selected."""
        tab, _ = self._make_tab()
        tab.packages_list.currentItem.return_value = None
        # Should not raise; QMessageBox.warning is a stub
        tab.remove_selected()

    def test_remove_selected_no_layered_item(self):
        """remove_selected() returns silently for 'No layered' placeholder."""
        tab, mock_pm = self._make_tab()
        mock_item = MagicMock()
        mock_item.text.return_value = "No layered packages (clean base image)"
        tab.packages_list.currentItem.return_value = mock_item
        tab.remove_selected()
        mock_pm.remove.assert_not_called()

    @patch.object(
        _QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: _QMessageBox.StandardButton.No),
    )
    def test_remove_selected_confirm_no(self):
        """remove_selected() does nothing when user says No."""
        tab, mock_pm = self._make_tab()
        mock_item = MagicMock()
        mock_item.text.return_value = "\U0001f4e6 vim"
        tab.packages_list.currentItem.return_value = mock_item
        tab.remove_selected()
        mock_pm.remove.assert_not_called()

    @patch.object(
        _QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: _QMessageBox.StandardButton.Yes),
    )
    @patch.object(
        _SystemManager,
        "has_pending_deployment",
        staticmethod(lambda: False),
    )
    @patch.object(
        _SystemManager,
        "get_layered_packages",
        staticmethod(lambda: []),
    )
    def test_remove_selected_confirm_yes_success(self):
        """remove_selected() calls pkg_manager.remove on confirmation."""
        tab, mock_pm = self._make_tab()
        mock_item = MagicMock()
        mock_item.text.return_value = "\U0001f4e6 vim"
        tab.packages_list.currentItem.return_value = mock_item
        mock_pm.remove.return_value = MagicMock(success=True, message="OK")
        tab.remove_selected()
        mock_pm.remove.assert_called_once_with(["vim"])

    @patch.object(
        _QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: _QMessageBox.StandardButton.Yes),
    )
    def test_remove_selected_confirm_yes_failure(self):
        """remove_selected() shows error on removal failure."""
        tab, mock_pm = self._make_tab()
        mock_item = MagicMock()
        mock_item.text.return_value = "\U0001f4e6 vim"
        tab.packages_list.currentItem.return_value = mock_item
        mock_pm.remove.return_value = MagicMock(success=False, message="Permission denied")
        tab.remove_selected()
        mock_pm.remove.assert_called_once_with(["vim"])

    # -- reset_to_base --

    @patch.object(
        _QMessageBox,
        "warning",
        staticmethod(lambda *a, **kw: _QMessageBox.StandardButton.No),
    )
    def test_reset_to_base_confirm_no(self):
        """reset_to_base() does nothing when user says No."""
        tab, mock_pm = self._make_tab()
        tab.reset_to_base()
        mock_pm.reset_to_base.assert_not_called()

    @patch.object(
        _QMessageBox,
        "warning",
        staticmethod(lambda *a, **kw: _QMessageBox.StandardButton.Yes),
    )
    @patch.object(
        _SystemManager,
        "has_pending_deployment",
        staticmethod(lambda: False),
    )
    @patch.object(
        _SystemManager,
        "get_layered_packages",
        staticmethod(lambda: []),
    )
    def test_reset_to_base_confirm_yes_success(self):
        """reset_to_base() calls pkg_manager.reset_to_base on confirmation."""
        tab, mock_pm = self._make_tab()
        mock_pm.reset_to_base.return_value = MagicMock(success=True, message="Reset complete")
        tab.reset_to_base()
        mock_pm.reset_to_base.assert_called_once()

    @patch.object(
        _QMessageBox,
        "warning",
        staticmethod(lambda *a, **kw: _QMessageBox.StandardButton.Yes),
    )
    def test_reset_to_base_confirm_yes_failure(self):
        """reset_to_base() shows error dialog on failure."""
        tab, mock_pm = self._make_tab()
        mock_pm.reset_to_base.return_value = MagicMock(success=False, message="Error resetting")
        tab.reset_to_base()
        mock_pm.reset_to_base.assert_called_once()

    # -- reboot_system --

    @patch.object(
        _QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: _QMessageBox.StandardButton.No),
    )
    def test_reboot_system_confirm_no(self):
        """reboot_system() does nothing when user says No."""
        tab, _ = self._make_tab()
        tab.reboot_system()
        tab.reboot_runner.run_command.assert_not_called()

    @patch.object(
        _QMessageBox,
        "question",
        staticmethod(lambda *a, **kw: _QMessageBox.StandardButton.Yes),
    )
    def test_reboot_system_confirm_yes(self):
        """reboot_system() runs pkexec systemctl reboot when confirmed."""
        tab, _ = self._make_tab()
        tab.reboot_system()
        tab.reboot_runner.run_command.assert_called_once_with("pkexec", ["systemctl", "reboot"])


# ===================================================================
# Test: _SmartUpdatesSubTab
# ===================================================================


class TestSmartUpdatesSubTab(unittest.TestCase):
    """Tests for _SmartUpdatesSubTab methods."""

    def setUp(self):
        self.tab = _mt._SmartUpdatesSubTab()
        self.tab.output_area = MagicMock()
        self.tab.updates_list = MagicMock()
        self.tab.runner = MagicMock()

    # -- _append_output --

    def test_append_output_inserts_text(self):
        """_append_output() inserts text into output_area."""
        self.tab._append_output("info")
        self.tab.output_area.insertPlainText.assert_called_with("info")

    # -- _check_updates --

    @patch("utils.update_manager.UpdateManager.check_updates")
    def test_check_updates_found(self, mock_check):
        """_check_updates() populates list when updates are found."""
        update = MagicMock()
        update.name = "vim"
        update.old_version = "9.0"
        update.new_version = "9.1"
        update.source = "fedora"
        mock_check.return_value = [update]
        self.tab._append_output = MagicMock()
        self.tab._check_updates()
        self.tab.updates_list.clear.assert_called_once()
        self.tab.updates_list.addItem.assert_called_once()

    @patch("utils.update_manager.UpdateManager.check_updates")
    def test_check_updates_none(self, mock_check):
        """_check_updates() shows 'up to date' when no updates found."""
        mock_check.return_value = []
        self.tab._append_output = MagicMock()
        self.tab._check_updates()
        self.tab.updates_list.clear.assert_called_once()
        # 1 addItem for "System is up to date."
        self.tab.updates_list.addItem.assert_called_once()

    @patch("utils.update_manager.UpdateManager.check_updates")
    def test_check_updates_none_output(self, mock_check):
        """_check_updates() appends 'Found 0 available updates.'"""
        mock_check.return_value = []
        self.tab._append_output = MagicMock()
        self.tab._check_updates()
        call_args = self.tab._append_output.call_args[0][0]
        self.assertIn("0", call_args)

    @patch("utils.update_manager.UpdateManager.check_updates")
    def test_check_updates_multiple(self, mock_check):
        """_check_updates() adds item per update and reports count."""
        updates = []
        for name in ("vim", "htop", "git"):
            u = MagicMock()
            u.name = name
            u.old_version = "1.0"
            u.new_version = "2.0"
            u.source = "fedora"
            updates.append(u)
        mock_check.return_value = updates
        self.tab._append_output = MagicMock()
        self.tab._check_updates()
        self.assertEqual(self.tab.updates_list.addItem.call_count, 3)

    @patch(
        "utils.update_manager.UpdateManager.check_updates",
        side_effect=OSError("Network error"),
    )
    def test_check_updates_error(self, mock_check):
        """_check_updates() appends error message on exception."""
        self.tab._append_output = MagicMock()
        self.tab._check_updates()
        call_args = self.tab._append_output.call_args[0][0]
        self.assertIn("ERROR", call_args)

    # -- _preview_conflicts --

    @patch("utils.update_manager.UpdateManager.preview_conflicts")
    def test_preview_conflicts_found(self, mock_preview):
        """_preview_conflicts() populates list with conflicts."""
        conflict = MagicMock()
        conflict.package = "mesa"
        conflict.conflict_type = "dependency"
        conflict.description = "requires libX11"
        mock_preview.return_value = [conflict]
        self.tab._preview_conflicts()
        self.tab.updates_list.clear.assert_called_once()
        self.tab.updates_list.addItem.assert_called_once()

    @patch("utils.update_manager.UpdateManager.preview_conflicts")
    def test_preview_conflicts_none(self, mock_preview):
        """_preview_conflicts() shows 'No conflicts' when none detected."""
        mock_preview.return_value = []
        self.tab._preview_conflicts()
        self.tab.updates_list.clear.assert_called_once()
        self.tab.updates_list.addItem.assert_called_once()

    @patch(
        "utils.update_manager.UpdateManager.preview_conflicts",
        side_effect=OSError("Parse error"),
    )
    def test_preview_conflicts_error(self, mock_preview):
        """_preview_conflicts() appends error on exception."""
        self.tab._append_output = MagicMock()
        self.tab._preview_conflicts()
        call_args = self.tab._append_output.call_args[0][0]
        self.assertIn("ERROR", call_args)

    # -- _schedule_update --

    @patch("utils.update_manager.UpdateManager.get_schedule_commands")
    @patch("utils.update_manager.UpdateManager.schedule_update")
    def test_schedule_update_success(self, mock_schedule, mock_cmds):
        """_schedule_update() runs schedule commands on success."""
        mock_schedule.return_value = MagicMock()
        mock_cmds.return_value = [
            ("pkexec", ["systemctl", "enable", "test.timer"], "Enabling timer"),
        ]
        self.tab._append_output = MagicMock()
        self.tab._schedule_update()
        self.tab.runner.run_command.assert_called_once_with("pkexec", ["systemctl", "enable", "test.timer"])

    @patch("utils.update_manager.UpdateManager.get_schedule_commands")
    @patch("utils.update_manager.UpdateManager.schedule_update")
    def test_schedule_update_multiple_commands(self, mock_schedule, mock_cmds):
        """_schedule_update() runs all returned commands."""
        mock_schedule.return_value = MagicMock()
        mock_cmds.return_value = [
            ("pkexec", ["cmd1"], "Step 1"),
            ("pkexec", ["cmd2"], "Step 2"),
        ]
        self.tab._append_output = MagicMock()
        self.tab._schedule_update()
        self.assertEqual(self.tab.runner.run_command.call_count, 2)

    @patch(
        "utils.update_manager.UpdateManager.schedule_update",
        side_effect=OSError("Schedule failed"),
    )
    def test_schedule_update_error(self, mock_schedule):
        """_schedule_update() appends error on exception."""
        self.tab._append_output = MagicMock()
        self.tab._schedule_update()
        call_args = self.tab._append_output.call_args[0][0]
        self.assertIn("ERROR", call_args)

    # -- _rollback_last --

    @patch("utils.update_manager.UpdateManager.rollback_last")
    def test_rollback_last_success(self, mock_rollback):
        """_rollback_last() runs the rollback command."""
        mock_rollback.return_value = (
            "pkexec",
            ["dnf", "history", "undo", "last", "-y"],
            "Rolling back...",
        )
        self.tab._append_output = MagicMock()
        self.tab._rollback_last()
        self.tab.runner.run_command.assert_called_once_with("pkexec", ["dnf", "history", "undo", "last", "-y"])

    @patch("utils.update_manager.UpdateManager.rollback_last")
    def test_rollback_last_appends_description(self, mock_rollback):
        """_rollback_last() appends the description to output."""
        mock_rollback.return_value = (
            "pkexec",
            ["dnf", "history", "undo", "last", "-y"],
            "Rolling back...",
        )
        self.tab._append_output = MagicMock()
        self.tab._rollback_last()
        desc_call = self.tab._append_output.call_args[0][0]
        self.assertIn("Rolling back", desc_call)

    @patch(
        "utils.update_manager.UpdateManager.rollback_last",
        side_effect=OSError("Rollback failed"),
    )
    def test_rollback_last_error(self, mock_rollback):
        """_rollback_last() appends error on exception."""
        self.tab._append_output = MagicMock()
        self.tab._rollback_last()
        call_args = self.tab._append_output.call_args[0][0]
        self.assertIn("ERROR", call_args)


# ===================================================================
# Test: MaintenanceTab — atomic vs non-atomic sub-tabs
# ===================================================================


class TestMaintenanceTabAtomicDetection(unittest.TestCase):
    """Tests for MaintenanceTab sub-tab construction based on system type."""

    def test_non_atomic_constructs(self):
        """On non-atomic systems, MaintenanceTab constructs without error."""
        _SystemManager.is_atomic = staticmethod(lambda: False)
        tab = _mt.MaintenanceTab()
        self.assertIsNotNone(tab)

    def test_atomic_constructs(self):
        """On atomic systems, MaintenanceTab constructs (incl. Overlays)."""
        original = _SystemManager.is_atomic
        _SystemManager.is_atomic = staticmethod(lambda: True)
        try:
            tab = _mt.MaintenanceTab()
            self.assertIsNotNone(tab)
        finally:
            _SystemManager.is_atomic = original


# ===================================================================
# Test: _UpdatesSubTab — progress bar edge cases
# ===================================================================


class TestUpdatesProgressEdgeCases(unittest.TestCase):
    """Edge-case tests for progress bar updates."""

    def setUp(self):
        self.tab = _mt._UpdatesSubTab()
        self.tab.output_area = MagicMock()
        self.tab.progress_bar = MagicMock()
        self.tab.runner = MagicMock()
        self.tab.btn_dnf = MagicMock()
        self.tab.btn_flatpak = MagicMock()
        self.tab.btn_fw = MagicMock()
        self.tab.btn_update_all = MagicMock()

    def test_update_progress_zero_percent(self):
        """update_progress(0, ...) sets value to 0."""
        self.tab.update_progress(0, "Starting")
        self.tab.progress_bar.setValue.assert_called_with(0)

    def test_update_progress_100_percent(self):
        """update_progress(100, ...) sets value to 100."""
        self.tab.update_progress(100, "Done")
        self.tab.progress_bar.setValue.assert_called_with(100)

    def test_update_progress_indeterminate_at_100(self):
        """update_progress(-1, ...) with bar at 100 enters indeterminate."""
        self.tab.progress_bar.value.return_value = 100
        self.tab.update_progress(-1, "Checking...")
        self.tab.progress_bar.setRange.assert_called_with(0, 0)

    def test_update_progress_indeterminate_at_0(self):
        """update_progress(-1, ...) with bar at 0 enters indeterminate."""
        self.tab.progress_bar.value.return_value = 0
        self.tab.update_progress(-1, "Starting...")
        self.tab.progress_bar.setRange.assert_called_with(0, 0)

    def test_update_progress_indeterminate_midway_skips_range(self):
        """update_progress(-1, ...) with bar at 50 does not reset range."""
        self.tab.progress_bar.value.return_value = 50
        self.tab.update_progress(-1, "Still working...")
        self.tab.progress_bar.setRange.assert_not_called()

    def test_on_command_finished_nonzero_exit_still_re_enables(self):
        """on_command_finished(1) still re-enables buttons when queue ends."""
        self.tab.update_queue = []
        self.tab.current_update_index = 0
        self.tab.append_output = MagicMock()
        self.tab.on_command_finished(1)
        self.tab.btn_dnf.setEnabled.assert_called_with(True)


# ===================================================================
# Test: Source-level sanity checks
# ===================================================================


class TestMaintenanceTabSourceLevel(unittest.TestCase):
    """Source-level checks for critical patterns."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "loofi-fedora-tweaks",
            "ui",
            "maintenance_tab.py",
        )
        with open(path, "r", encoding="utf-8") as fh:
            cls.source = fh.read()

    def test_inherits_base_tab(self):
        """MaintenanceTab inherits from BaseTab."""
        self.assertIn("class MaintenanceTab(BaseTab)", self.source)

    def test_has_metadata(self):
        """MaintenanceTab defines _METADATA."""
        self.assertIn("_METADATA", self.source)
        self.assertIn('"maintenance"', self.source)

    def test_has_updates_subtab(self):
        """Module contains _UpdatesSubTab class."""
        self.assertIn("class _UpdatesSubTab", self.source)

    def test_has_cleanup_subtab(self):
        """Module contains _CleanupSubTab class."""
        self.assertIn("class _CleanupSubTab", self.source)

    def test_has_overlays_subtab(self):
        """Module contains _OverlaysSubTab class."""
        self.assertIn("class _OverlaysSubTab", self.source)

    def test_has_smart_updates_subtab(self):
        """Module contains _SmartUpdatesSubTab class."""
        self.assertIn("class _SmartUpdatesSubTab", self.source)

    def test_uses_command_runner(self):
        """Module uses CommandRunner."""
        self.assertIn("CommandRunner", self.source)

    def test_uses_pkexec_not_sudo(self):
        """Module uses pkexec, never sudo."""
        self.assertIn("pkexec", self.source)
        self.assertNotIn("sudo", self.source)

    def test_uses_system_manager(self):
        """Module uses SystemManager for system detection."""
        self.assertIn("SystemManager", self.source)

    def test_has_update_all_method(self):
        """Module has run_update_all method."""
        self.assertIn("def run_update_all", self.source)


# ===================================================================
# Cleanup stubs on module unload
# ===================================================================


def tearDownModule():
    """Restore original sys.modules entries."""
    sys.modules.pop("ui.maintenance_tab", None)
    _uninstall_stubs()


if __name__ == "__main__":
    unittest.main()
