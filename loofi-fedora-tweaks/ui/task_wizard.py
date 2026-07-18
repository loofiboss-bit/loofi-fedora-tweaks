from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QProgressBar,
    QFrame, QScrollArea, QCheckBox, QWidget,
)
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from core.actions import ActionCenterOrchestrator
from core.diagnostics.health_registry import HealthRegistry
from core.diagnostics.health_model import HealthResult
from core.executor.action_model import AtlasActionRegistry, SystemAction
from core.executor.action_result import ActionResult
from utils.log import get_logger

logger = get_logger(__name__)


class _AtlasPlanWorker(QObject):
    """Create Action Center plans without blocking the wizard UI thread."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, action_center, requests):
        super().__init__()
        self._action_center = action_center
        self._requests = requests

    def run(self):
        results = []
        try:
            for request in self._requests:
                plan = self._action_center.plan(request["action_id"], request["parameters"], target="44")
                results.append({**request, "plan": plan})
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(results)


class AtlasTaskWizard(QDialog):
    """
    v4.0 "Atlas" Guided Task Wizard.
    Steps:
    0: Diagnostic Scan
    1: Findings & Recommendations
    2: Preview & Execution
    3: Result Summary
    """

    def __init__(self, task_id: str, check_ids: list, action_ids: list, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.check_ids = check_ids
        self.action_ids = action_ids

        self.registry = HealthRegistry()
        self.action_registry = AtlasActionRegistry()
        self.action_center = ActionCenterOrchestrator()

        self.results: list[HealthResult] = []
        self.selected_actions: list[SystemAction] = []
        # Stores {action: SystemAction, result: ActionResult}
        self.repair_results: list[dict] = []
        self._plan_thread = None
        self._plan_worker = None

        self._setup_ui()
        self._set_step(0)

    def _setup_ui(self):
        self.setWindowTitle(
            f"Atlas Assistant - {self.task_id.replace('task-', '').title()}")
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)

        # Header
        self.title_label = QLabel("Assistant is helping you...")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.title_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Stack
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_scan_step())
        self.stack.addWidget(self._build_findings_step())
        self.stack.addWidget(self._build_execution_step())
        self.stack.addWidget(self._build_result_step())

        # Nav Buttons
        nav = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self._go_back)
        nav.addWidget(self.btn_back)

        nav.addStretch()

        self.btn_next = QPushButton("Next")
        self.btn_next.setObjectName("wizardBtnNext")
        self.btn_next.clicked.connect(self._go_next)
        nav.addWidget(self.btn_next)

        layout.addLayout(nav)

    def _build_scan_step(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.scan_label = QLabel("Running system diagnostics...")
        self.scan_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.scan_label)
        layout.addStretch()
        return page

    def _build_findings_step(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Diagnostic Findings:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.findings_container = QWidget()
        self.findings_layout = QVBoxLayout(self.findings_container)
        self.findings_layout.addStretch()
        scroll.setWidget(self.findings_container)
        layout.addWidget(scroll)
        return page

    def _build_execution_step(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Recommended Repairs:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.actions_container = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_container)
        self.actions_layout.addStretch()
        scroll.setWidget(self.actions_container)
        layout.addWidget(scroll)
        return page

    def _build_result_step(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.result_label = QLabel("All tasks completed.")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet(
            "font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(self.result_label)

        layout.addWidget(QLabel("Execution Log:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.log_container = QWidget()
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.addStretch()
        scroll.setWidget(self.log_container)
        layout.addWidget(scroll)

        return page

    def _set_step(self, index: int):
        self.stack.setCurrentIndex(index)
        self.progress_bar.setValue((index + 1) * 25)
        self.btn_back.setVisible(index > 0 and index < 3)

        if index == 0:
            self.title_label.setText("Analyzing System Health")
            self.btn_next.setEnabled(False)
            QTimer.singleShot(1000, self._run_diagnostics)
        elif index == 1:
            self.title_label.setText("Findings & Recommendations")
            self.btn_next.setText("Next")
            self._populate_findings()
        elif index == 2:
            self.title_label.setText("Apply Repairs")
            self.btn_next.setText("Run Repairs")
            self._populate_actions()
        elif index == 3:
            self.title_label.setText("Task Complete")
            self.btn_next.setText("Finish")
            self._populate_log()

    def _populate_log(self):
        while self.log_layout.count() > 1:
            item = self.log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for res_data in self.repair_results:
            action = res_data["action"]
            res = res_data["result"]
            title = res_data["display_title"]

            frame = QFrame()
            frame.setObjectName("dashboardCard")
            fl = QVBoxLayout(frame)

            status_text = "SUCCESS" if res.success else "FAILED"

            header = QLabel(f"{title}: {status_text}")
            header.setObjectName("taskResultHeader")
            header.setProperty("resultKind", "success" if res.success else "error")
            fl.addWidget(header)

            if res.message:
                msg = QLabel(res.message)
                msg.setWordWrap(True)
                msg.setObjectName("taskResultMessage")
                fl.addWidget(msg)

            if action.revert_hint:
                hint = QLabel(f"Rollback hint: {action.revert_hint}")
                hint.setWordWrap(True)
                hint.setObjectName("taskRollbackHint")
                fl.addWidget(hint)

            self.log_layout.insertWidget(self.log_layout.count() - 1, frame)

    def _go_next(self):
        idx = self.stack.currentIndex()
        if idx == 2:
            self._run_repairs()
        elif idx == 3:
            self.accept()
        else:
            self._set_step(idx + 1)

    def _go_back(self):
        idx = self.stack.currentIndex()
        self._set_step(idx - 1)

    def _run_diagnostics(self):
        self.results = []
        for cid in self.check_ids:
            res = self.registry.run_check(cid)
            self.results.append(res)

        self.scan_label.setText(
            f"Scan complete. Found {len([r for r in self.results if r.status != 'healthy'])} issues.")
        self.btn_next.setEnabled(True)

    def _populate_findings(self):
        while self.findings_layout.count() > 1:
            item = self.findings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for res in self.results:
            check = self.registry.get_check(res.check_id)
            frame = QFrame()
            frame.setObjectName("dashboardCard")
            fl = QVBoxLayout(frame)

            title = QLabel(
                f"{check.title if check else res.check_id}: {res.status.upper()}")
            title.setStyleSheet("font-weight: bold;")
            fl.addWidget(title)
            fl.addWidget(QLabel(res.message))

            self.findings_layout.insertWidget(
                self.findings_layout.count() - 1, frame)

    def _populate_actions(self):
        while self.actions_layout.count() > 1:
            item = self.actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.action_checkboxes = []

        for aid in self.action_ids:
            action = self.action_registry.get_action(aid)
            if not action:
                continue

            # Helper to create styled action widget
            def add_action_widget(title, risk, command_preview, dyn_args=[]):
                container = QFrame()
                container.setObjectName("dashboardCard")
                cl = QVBoxLayout(container)
                cl.setContentsMargins(10, 10, 10, 10)

                # Checkbox row
                row = QHBoxLayout()
                cb = QCheckBox(title)
                cb.setChecked(risk in ["info", "low"])
                cb.setProperty("action_id", aid)
                cb.setProperty("dynamic_args", dyn_args)
                row.addWidget(cb, 1)

                # Risk Badge
                risk_lbl = QLabel(risk.upper())
                risk_lbl.setObjectName("taskRiskBadge")
                risk_lbl.setProperty("riskLevel", risk if risk in {"info", "low", "medium", "high"} else "info")
                row.addWidget(risk_lbl)
                cl.addLayout(row)

                # Command Preview (Hidden by default)
                preview_lbl = QLabel(f"<code>{command_preview}</code>")
                preview_lbl.setObjectName("taskCommandPreview")
                preview_lbl.setWordWrap(True)
                preview_lbl.setVisible(False)
                cl.addWidget(preview_lbl)

                # Preview Toggle
                preview_btn = QPushButton("Show Command")
                preview_btn.setFlat(True)
                preview_btn.setObjectName("taskCommandPreviewToggle")
                preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                preview_btn.clicked.connect(
                    lambda: preview_lbl.setVisible(not preview_lbl.isVisible()))
                cl.addWidget(preview_btn)

                self.actions_layout.insertWidget(
                    self.actions_layout.count() - 1, container)
                self.action_checkboxes.append(cb)

            # Dynamic Handling
            if aid == "restart-failed-service":
                service_result = next(
                    (r for r in self.results if r.check_id == "failed-services"), None)
                if service_result and service_result.affected_entities:
                    for svc in service_result.affected_entities:
                        full_cmd = f"{action.command} {' '.join(action.args)} {svc}"
                        add_action_widget(
                            f"Restart {svc}", action.risk_level, full_cmd, [svc])
                    continue

            # Standard Handling
            full_cmd = f"{action.command} {' '.join(action.args)}"
            add_action_widget(action.title, action.risk_level, full_cmd)

    def _run_repairs(self):
        """
        Create reviewed Action Center plans for selected repairs.

        Atlas never executes commands directly in v14. Plans remain bounded by
        Action Center preflight, confirmation, leasing, and verification.
        """
        self.btn_next.setEnabled(False)
        self.btn_back.setEnabled(False)
        self.repair_results = []

        requests = []

        for index, cb in enumerate(self.action_checkboxes):
            if not cb.isChecked():
                continue

            aid = cb.property("action_id")
            action = self.action_registry.get_action(aid)
            if not action:
                continue

            display_title = cb.text()
            # Update UI for current action
            cb.setText(self.tr("Planning: %1...").replace("%1", action.title))
            cb.repaint()
            dyn_args = cb.property("dynamic_args") or []
            parameters = {"service": str(dyn_args[0])} if aid == "restart-failed-service" and dyn_args else {}
            requests.append({
                "index": index,
                "action_id": aid,
                "parameters": parameters,
                "action": action,
                "display_title": display_title,
            })

        if not requests:
            self._accept_plans([])
            return
        self._plan_thread = QThread(self)
        self._plan_worker = _AtlasPlanWorker(self.action_center, requests)
        self._plan_worker.moveToThread(self._plan_thread)
        self._plan_thread.started.connect(self._plan_worker.run)
        self._plan_worker.finished.connect(self._accept_plans)
        self._plan_worker.finished.connect(self._plan_thread.quit)
        self._plan_worker.failed.connect(self._planning_failed)
        self._plan_worker.failed.connect(self._plan_thread.quit)
        self._plan_thread.finished.connect(self._plan_worker.deleteLater)
        self._plan_thread.finished.connect(self._plan_thread.deleteLater)
        self._plan_thread.finished.connect(self._clear_plan_worker)
        self._plan_thread.start()

    def _accept_plans(self, planned):
        planned_count = 0
        blocked_count = 0
        for item in planned:
            plan = item["plan"]
            success = plan.state in {"ready", "needs_review"}
            message = (
                self.tr("Action Center plan %1 is ready for review; no command was run.").replace("%1", plan.plan_id)
                if success
                else self.tr("Action remains manual or blocked: %1").replace("%1", plan.policy_decision.explanation)
            )
            result = ActionResult(
                success=success,
                message=message,
                preview=True,
                action_id=item["action_id"],
                data={"plan": plan.to_dict(), "policy_decision": plan.policy_decision.to_dict()},
            )
            self.repair_results.append({
                "action": item["action"],
                "result": result,
                "display_title": item["display_title"],
            })
            checkbox = self.action_checkboxes[item["index"]]
            if success:
                checkbox.setText(self.tr("Planned: %1").replace("%1", item["display_title"]))
                planned_count += 1
            else:
                checkbox.setText(self.tr("%1 (Manual/Blocked)").replace("%1", item["display_title"]))
                checkbox.setToolTip(message)
                blocked_count += 1
            checkbox.repaint()

        summary = self.tr("Planning finished. %1 Action Center plans created; no commands were run.").replace("%1", str(planned_count))
        if blocked_count > 0:
            summary += self.tr(" %1 actions remain manual or blocked.").replace("%1", str(blocked_count))
        self.result_label.setText(summary)
        self.btn_next.setEnabled(True)
        self._set_step(3)

    def _planning_failed(self, message):
        logger.error("Action planning failed: %s", message)
        self.result_label.setText(self.tr("Action Center planning failed: %1").replace("%1", str(message)))
        self.btn_next.setEnabled(True)
        self.btn_back.setEnabled(True)

    def _clear_plan_worker(self):
        self._plan_thread = None
        self._plan_worker = None
