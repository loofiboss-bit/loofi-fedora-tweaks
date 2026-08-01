"""
Maintenance Action Center sections.
Part of v11.0 "Aurora Update".

Uses a lazy route-owned stack to preserve all features from the
original UpdatesTab, CleanupTab, and OverlaysTab.
The Overlays sub-tab is only shown on Atomic (rpm-ostree) systems.
"""

import typing

# flake8: noqa: F401

from services.system.system import cached_which

from core.plugins.metadata import PluginMetadata
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from services.system import SystemManager
from utils.commands import PrivilegedCommand

from ui.base_tab import BaseTab
from ui.components.layout import PageScaffold
from ui.design import semantic_qcolor
from ui.shared_states import ActionProgress, DetailsDisclosure, ResultBanner
from ui.tooltips import MAINT_CLEANUP, MAINT_JOURNAL, MAINT_ORPHANS

# ---------------------------------------------------------------------------
# Sub-tab: Updates
# ---------------------------------------------------------------------------


class _ActionCenterOperationWorker(QObject):
    """Run Action Center probes and persistence away from the GUI thread."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self: typing.Any, operation: typing.Any) -> None:
        super().__init__()
        self._operation = operation

    def run(self: typing.Any) -> None:
        try:
            self.finished.emit(self._operation())
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            self.failed.emit(str(exc))


ACTION_CENTER_STATE_GROUPS = (
    ("needs_review", "Needs review"),
    ("ready", "Ready"),
    ("running", "Running"),
    ("waiting_restart", "Waiting for restart"),
    ("completed", "Completed"),
    ("failed", "Failed"),
)


def action_center_group_for_state(state: str) -> str:
    """Map plan and run states to the six user-facing work groups."""
    if state in {"planned", "needs_review", "manual_only"}:
        return "needs_review"
    if state == "ready":
        return "ready"
    if state in {"running", "verifying"}:
        return "running"
    if state == "awaiting_reboot":
        return "waiting_restart"
    if state == "succeeded":
        return "completed"
    return "failed"


class _ActionCenterSubTab(BaseTab):
    """Review, asynchronously run, verify, and inspect v17 action plans."""

    systemCheckRequested = pyqtSignal(object)

    _ACTION_ID_ADAPTERS = {
        "readiness-repo-cache-clean": "dnf-clean-all",
    }

    def __init__(self: typing.Any) -> None:
        super().__init__()
        self._target_key = FEDORA_RELEASE_POLICY.stable_target
        self._items: list[typing.Any] = []
        self._visible_records: list[tuple[str, typing.Any]] = []
        self._plans_by_id: dict[str, typing.Any] = {}
        self._orchestrator = None
        self._current_plan = None
        self._current_run = None
        self._prepared_run = None
        self._interrupt_reason = None
        self._output_chunks: list[str] = []
        self._stderr_chunks: list[str] = []
        self._operation_thread = None
        self._operation_worker = None
        self._requested_action_id = ""
        self._requested_parameters: dict[str, typing.Any] = {}
        self._requested_finding_context: dict[str, typing.Any] | None = None

        from core.actions.center import ActionCenterService

        self._service = ActionCenterService()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Action Center"),
            self.tr("Review planned changes and follow each one through verification."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        intro = QLabel(
            self.tr(
                "Choose a work status, select a change, and follow the one available next step. "
                "A change is complete only after verification succeeds."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        lifecycle_row = QHBoxLayout()
        lifecycle_label = QLabel(self.tr("Work status"))
        self.lifecycle_view = QComboBox()
        self.lifecycle_view.setAccessibleName(self.tr("Action Center work status"))
        for group_id, label in ACTION_CENTER_STATE_GROUPS:
            self.lifecycle_view.addItem(self.tr(label), group_id)
        self.lifecycle_view.currentIndexChanged.connect(self._show_lifecycle_view)
        lifecycle_row.addWidget(lifecycle_label)
        lifecycle_row.addWidget(self.lifecycle_view, 1)
        layout.addLayout(lifecycle_row)

        advanced_widget = QWidget()
        advanced_widget.setObjectName("actionCenterControls")
        advanced_layout = QVBoxLayout(advanced_widget)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        target_load_row = QHBoxLayout()
        target_review_row = QHBoxLayout()
        load_stable = QPushButton(self.tr("Reload Fedora %s Actions") % FEDORA_RELEASE_POLICY.stable_release)
        self.load_stable_button = load_stable
        load_stable.clicked.connect(lambda: self._load_target(FEDORA_RELEASE_POLICY.stable_target))
        target_load_row.addWidget(load_stable)

        load_preview = QPushButton(self.tr("Load Fedora %s Preview Actions") % FEDORA_RELEASE_POLICY.preview_release)
        self.load_preview_button = load_preview
        load_preview.clicked.connect(lambda: self._load_target(FEDORA_RELEASE_POLICY.preview_target))
        load_preview.hide()

        preview_button = QPushButton(self.tr("Preview Selected"))
        self.preview_button = preview_button
        preview_button.clicked.connect(self._preview_selected)
        target_load_row.addWidget(preview_button)

        history_button = QPushButton(self.tr("Show History"))
        self.history_button = history_button
        history_button.clicked.connect(self._show_history)
        target_load_row.addWidget(history_button)
        target_load_row.addStretch()

        catalog_row = QHBoxLayout()
        catalog_label = QLabel(self.tr("Available advanced action"))
        self.catalog_selector = QComboBox()
        self.catalog_selector.setAccessibleName(self.tr("Available advanced Action Center action"))
        self.catalog_selector.currentIndexChanged.connect(
            self._select_advanced_candidate
        )
        catalog_row.addWidget(catalog_label)
        catalog_row.addWidget(self.catalog_selector, 1)

        self.target_guidance = QLabel(
            self.tr(
                "Fedora %s preview target choices are available in Upgrade Assistant."
            )
            % FEDORA_RELEASE_POLICY.preview_release
        )
        self.target_guidance.setObjectName("actionCenterTargetGuidance")
        self.target_guidance.setWordWrap(True)
        self.target_guidance.setAccessibleName(self.tr("Release target guidance"))

        review_button = QPushButton(self.tr("Review & Plan"))
        self.review_button = review_button
        review_button.clicked.connect(self._plan_selected)
        target_review_row.addWidget(review_button)

        self.run_button = QPushButton(self.tr("Run Plan"))
        self.run_button.clicked.connect(self._run_current_plan)
        self.run_button.setEnabled(False)
        target_review_row.addWidget(self.run_button)

        self.verify_button = QPushButton(self.tr("Verify Run"))
        self.verify_button.clicked.connect(self._verify_current_run)
        self.verify_button.setEnabled(False)
        target_review_row.addWidget(self.verify_button)

        self.check_again_button = QPushButton(self.tr("Check again"))
        self.check_again_button.setObjectName("actionCenterCheckAgain")
        self.check_again_button.clicked.connect(self._request_follow_up_check)
        self.check_again_button.setEnabled(False)
        self.check_again_button.setVisible(False)
        target_review_row.addWidget(self.check_again_button)

        advanced_layout.addLayout(target_load_row)
        advanced_layout.addLayout(catalog_row)
        advanced_layout.addWidget(self.target_guidance)
        self.advanced_review_tools = DetailsDisclosure(
            summary=self.tr("Show advanced review tools")
        )
        self.advanced_review_tools.setObjectName("actionCenterAdvancedTools")
        self.advanced_review_tools.add_widget(advanced_widget)
        layout.addWidget(self.advanced_review_tools)
        layout.addLayout(target_review_row)
        self._set_lifecycle_primary("review", enabled=False)

        self.presentation_banner = ResultBanner(
            self.tr("Action Center status"),
            self.tr("Loading Action Center candidates…"),
        )
        self.presentation_status = self.presentation_banner.message_label
        self.presentation_status.setAccessibleName(self.tr("Action Center status"))
        layout.addWidget(self.presentation_banner)

        self.action_list = QListWidget()
        self.action_list.setAccessibleName(self.tr("Action Center work list"))
        self.action_list.currentRowChanged.connect(self._selection_changed)
        layout.addWidget(self.action_list, 1)

        self.selected_summary = QLabel(
            self.tr("Select a change to review its outcome and safety details.")
        )
        self.selected_summary.setObjectName("actionCenterSelectedSummary")
        self.selected_summary.setAccessibleName(self.tr("Selected change summary"))
        self.selected_summary.setWordWrap(True)
        layout.addWidget(self.selected_summary)

        self.detail_disclosure = DetailsDisclosure(summary=self.tr("Show technical details"))
        self.detail_area = self.detail_disclosure.details
        self.detail_area.setAccessibleName(self.tr("Selected change technical details"))
        layout.addWidget(self.detail_disclosure, 1)

        self.add_output_disclosure(layout, self.tr("Show Action Center command output"))
        self.runner.output_received.connect(self._capture_output)
        self.runner.stderr_received.connect(self._capture_stderr)

        self._load_target(self._target_key)

    def _orchestrator_instance(self: typing.Any) -> typing.Any:
        if self._orchestrator is None:
            from core.actions import ActionCenterOrchestrator

            self._orchestrator = ActionCenterOrchestrator()
        return self._orchestrator

    def _load_target(self: typing.Any, target_key: str) -> None:
        self._target_key = target_key
        self.lifecycle_view.setCurrentIndex(0)
        self._current_plan = None
        self._current_run = None
        self._set_lifecycle_primary("review", enabled=False)
        self.action_list.clear()
        self.selected_summary.setText(
            self.tr("Loading Action Center candidates…")
        )
        self.detail_area.setPlainText(self.tr("Loading Action Center candidates..."))
        self.presentation_banner.set_result(
            "info",
            self.tr("Loading Action Center"),
            self.tr("Loading Action Center candidates…"),
        )
        self._set_loading(True)
        self._start_operation(
            lambda: self._merged_items(target_key),
            self._accept_loaded_items,
            self.tr("Action Center Failed"),
        )

    def _merged_items(self: typing.Any, target_key: str) -> typing.Any:
        readiness = self._service.candidates_from_readiness(target_key)
        catalog = self._service.catalog_items(target_key)
        catalog_ids = {item.id for item in catalog}
        adapters = {item.id for item in readiness if self._ACTION_ID_ADAPTERS.get(item.id) in catalog_ids}
        return [*catalog, *(item for item in readiness if item.id not in adapters)]

    def _accept_loaded_items(self: typing.Any, items: typing.Any) -> None:
        self._items = list(items)
        self._set_loading(False)
        self.catalog_selector.blockSignals(True)
        self.catalog_selector.clear()
        self.catalog_selector.addItem(self.tr("Choose an advanced action…"), "")
        for item in self._items:
            self.catalog_selector.addItem(item.title, item.id)
        self.catalog_selector.blockSignals(False)
        current_index = self.lifecycle_view.currentIndex()
        self._show_lifecycle_view(current_index if isinstance(current_index, int) else 0)
        selected = self._select_requested_action()
        if self._visible_records:
            self.presentation_banner.set_result(
                "info",
                self.tr("Changes need review"),
                self.tr("%d changes are available. Select one to review its outcome and safety details.")
                % len(self._visible_records),
            )
            if not selected and self.action_list.count():
                self.action_list.setCurrentRow(0)
        else:
            self.presentation_banner.set_result(
                "success",
                self.tr("Nothing needs review"),
                self.tr(
                    "No planned maintenance item needs review right now. "
                    "Available catalog actions remain under advanced review tools."
                ),
            )
            self.detail_area.setPlainText(
                self.tr("No planned Action Center change currently needs review.")
            )
            self.selected_summary.setText(
                self.tr("No planned change needs review right now.")
            )

    def _show_lifecycle_view(self: typing.Any, index: int) -> None:
        """Present one of the six user-facing Action Center work states."""
        if not isinstance(index, int):
            index = 0
        if not 0 <= index < len(ACTION_CENTER_STATE_GROUPS):
            index = 0
        group_id, group_label = ACTION_CENTER_STATE_GROUPS[index]
        review_mode = group_id == "needs_review"
        self.preview_button.setVisible(review_mode)
        self._set_lifecycle_primary(
            "review" if review_mode else "",
            enabled=False,
        )

        from core.actions import ActionPlanStore, ActionRunStore

        try:
            plans = ActionPlanStore().list(limit=25)
            runs = ActionRunStore().list(limit=25)
        except (OSError, RuntimeError, TypeError, ValueError):
            plans = []
            runs = []
        self._plans_by_id = {
            str(plan.plan_id): plan
            for plan in plans
            if getattr(plan, "plan_id", None)
        }

        records: list[tuple[str, typing.Any]] = []
        if group_id == "needs_review":
            records.extend(
                ("plan", plan)
                for plan in plans
                if action_center_group_for_state(str(plan.state)) == group_id
            )
            if self._requested_action_id:
                records.extend(
                    ("candidate", item)
                    for item in self._items
                    if self._ACTION_ID_ADAPTERS.get(item.id, item.id)
                    == self._requested_action_id
                )
        elif group_id == "ready":
            records.extend(
                ("plan", plan)
                for plan in plans
                if action_center_group_for_state(str(plan.state)) == group_id
            )
        else:
            if group_id == "failed":
                records.extend(
                    ("plan", plan)
                    for plan in plans
                    if action_center_group_for_state(str(plan.state)) == group_id
                )
            records.extend(
                ("run", run)
                for run in runs
                if action_center_group_for_state(str(run.state)) == group_id
            )

        self._visible_records = records if review_mode else list(reversed(records))
        self.action_list.clear()
        for kind, record in self._visible_records:
            if kind == "candidate":
                marker = self.tr("Manual guidance") if record.manual_only else self.tr("Create plan")
                self.action_list.addItem(f"{record.title} — {marker}")
            elif kind == "plan":
                resources = ", ".join(record.affected_resources) or self.tr("System")
                self.action_list.addItem(
                    f"{self._action_title(record.action_id)} — {resources}"
                )
            else:
                state = self.tr(str(record.state).replace("_", " ").title())
                self.action_list.addItem(
                    f"{self._action_title(record.action_id)} — {state}"
                )

        if self._visible_records:
            if not self._requested_action_id:
                self.action_list.setCurrentRow(0)
            return
        self.detail_area.setPlainText(
            self.tr("No changes are in %1.").replace("%1", self.tr(group_label).lower())
        )
        self.selected_summary.setText(
            self.tr("No changes are currently in %1.").replace(
                "%1",
                self.tr(group_label).lower(),
            )
        )
        self.presentation_banner.set_result(
            "success",
            self.tr("%1 is clear").replace("%1", self.tr(group_label)),
            self.tr("No changes are currently in this work state."),
        )

    def _action_title(self, action_id: str) -> str:
        """Return user-facing catalog copy without exposing a definition id."""
        for item in self._items:
            candidate_id = self._ACTION_ID_ADAPTERS.get(item.id, item.id)
            if candidate_id == action_id:
                return str(item.title)
        return str(self.tr(str(action_id).replace("-", " ").title()))

    def _privilege_label(self, privilege: typing.Any) -> str:
        """Translate stored privilege metadata into plain user-facing copy."""
        value = str(privilege or "none").strip().lower()
        if value in {"pkexec", "root", "administrator"}:
            return str(self.tr("Administrator approval (pkexec)"))
        if value in {"", "none", "user"}:
            return str(self.tr("None"))
        return str(self.tr(value.replace("_", " ").title()))

    def _restart_label(self, reboot_policy: typing.Any, *, required: bool = False) -> str:
        """Translate the closed reboot policy without exposing stored values."""
        if required:
            return str(self.tr("Required"))
        return str({
            "none": self.tr("Not required"),
            "may_require": self.tr("May be required"),
            "required": self.tr("Required"),
        }.get(str(reboot_policy), self.tr("Shown after plan creation")))

    def _select_advanced_candidate(self, index: int) -> None:
        """Move one explicitly chosen catalog definition into review."""
        if index <= 0:
            return
        action_id = str(self.catalog_selector.itemData(index) or "")
        if not action_id:
            return
        self._requested_action_id = self._ACTION_ID_ADAPTERS.get(
            action_id,
            action_id,
        )
        self.lifecycle_view.setCurrentIndex(0)
        self._show_lifecycle_view(0)
        self._select_requested_action()

    def preselect_action(
        self: typing.Any,
        action_id: str,
        parameters: typing.Any = None,
        *,
        finding_context: typing.Any = None,
    ) -> bool:
        """Preselect a candidate without creating a plan or running anything."""
        self._requested_action_id = self._ACTION_ID_ADAPTERS.get(str(action_id or ""), str(action_id or ""))
        self._requested_parameters = dict(parameters or {})
        self._requested_finding_context = (
            dict(finding_context)
            if isinstance(finding_context, dict)
            else None
        )
        if not self._requested_action_id:
            return False
        if self._items:
            self.lifecycle_view.setCurrentIndex(0)
            self._show_lifecycle_view(0)
        return self._select_requested_action() or not bool(self._items)

    def _set_loading(self: typing.Any, loading: bool) -> None:
        for button in (
            self.load_stable_button,
            self.load_preview_button,
            self.preview_button,
            self.history_button,
        ):
            button.setEnabled(not loading)
        if loading:
            for button in (
                self.review_button,
                self.run_button,
                self.verify_button,
                self.check_again_button,
            ):
                button.setEnabled(False)

    def _set_lifecycle_primary(
        self,
        stage: str,
        *,
        enabled: bool,
    ) -> None:
        """Expose exactly one next lifecycle action without changing behavior."""
        buttons = {
            "review": self.review_button,
            "run": self.run_button,
            "verify": self.verify_button,
            "check_again": self.check_again_button,
        }
        for candidate_stage, button in buttons.items():
            button.setVisible(candidate_stage == stage)
            button.setEnabled(enabled if candidate_stage == stage else False)
            button.setObjectName(
                "primaryAction" if candidate_stage == stage else "componentButton"
            )

    def _selection_changed(self: typing.Any, row: int) -> None:
        if 0 <= row < len(self._visible_records):
            kind, record = self._visible_records[row]
            if kind == "plan":
                self._current_plan = record
                self._current_run = None
                self._show_plan(record)
                if record.state in {"ready", "needs_review"}:
                    self._set_lifecycle_primary("run", enabled=True)
                else:
                    self._set_lifecycle_primary("", enabled=False)
                return
            if kind == "run":
                self._current_run = record
                self._current_plan = None
                self._show_run(record)
                return
            item = record
            candidate_id = self._ACTION_ID_ADAPTERS.get(item.id, item.id)
            if (
                self._requested_finding_context is not None
                and candidate_id != self._requested_action_id
            ):
                self._requested_finding_context = None
                self._requested_parameters = {}
            self._show_item(item)

    def _select_requested_action(self: typing.Any) -> bool:
        if not self._requested_action_id:
            return False
        if self.lifecycle_view.currentData() != "needs_review":
            self.lifecycle_view.setCurrentIndex(0)
        for index, (kind, item) in enumerate(self._visible_records):
            if kind != "candidate":
                continue
            candidate_id = self._ACTION_ID_ADAPTERS.get(item.id, item.id)
            if candidate_id == self._requested_action_id:
                self.action_list.setCurrentRow(index)
                self._show_item(item)
                return True
        return False

    def _start_operation(self: typing.Any, operation: typing.Any, on_success: typing.Any, failure_title: str) -> None:
        if self._operation_thread is not None:
            QMessageBox.warning(self, self.tr("Action Center Busy"), self.tr("Wait for the current Action Center operation to finish."))
            return
        thread = QThread(self)
        worker = _ActionCenterOperationWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_success)
        worker.finished.connect(thread.quit)
        worker.failed.connect(lambda message: QMessageBox.warning(self, failure_title, message))
        worker.failed.connect(lambda _message: self._set_loading(False))
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_operation_worker)
        self._operation_thread = thread
        self._operation_worker = worker
        thread.start()

    def _clear_operation_worker(self: typing.Any) -> None:
        self._operation_thread = None
        self._operation_worker = None

    def _selected_item(self: typing.Any) -> typing.Any:
        row = self.action_list.currentRow()
        if not isinstance(row, int) or row < 0:
            return None
        if row < len(self._visible_records):
            kind, record = self._visible_records[row]
            return record if kind == "candidate" else None
        if row < len(self._items):
            return self._items[row]
        return None

    def _show_item(self: typing.Any, item: typing.Any) -> None:
        self._set_lifecycle_primary("review", enabled=not item.manual_only)
        if item.manual_only:
            self.presentation_status.setText(self.tr("Manual-only recommendation: review the guidance; Action Center will not execute it."))
        command = " ".join(item.command_preview) if item.command_preview else self.tr("Manual-only")
        verification_command = " ".join(item.verification_command)
        verification = (
            self.tr("Required after execution")
            if verification_command
            else self.tr("Manual verification guidance")
        )
        resources = ", ".join(item.metadata.get("affected_resources", ())) or self.tr("Shown after plan creation")
        reboot = self._restart_label(item.metadata.get("reboot_policy"))
        self._set_selected_details(
            [
                f"{self.tr('Intended outcome')}: {item.title}",
                item.description,
                f"{self.tr('Affected components')}: {resources}",
                f"{self.tr('Privilege required')}: {self._privilege_label(item.privilege)}",
                f"{self.tr('Restart requirement')}: {reboot}",
                f"{self.tr('Verification')}: {verification}",
                f"{self.tr('Recovery guidance')}: {item.rollback_hint}",
            ],
            [
                f"{self.tr('Technical source')}: {item.source}",
                f"{self.tr('Definition')}: {item.id}",
                f"{self.tr('Risk')}: {item.risk_level}",
                f"{self.tr('Command preview')}: {command}",
                f"{self.tr('Verification command')}: {verification_command or self.tr('None')}",
            ],
        )

    def _set_selected_details(
        self,
        summary_lines: list[str],
        technical_lines: list[str],
    ) -> None:
        """Keep user outcome and safety facts visible above technical metadata."""
        self.selected_summary.setText("\n".join(summary_lines))
        self.detail_area.setPlainText("\n".join(technical_lines))

    def _preview_selected(self: typing.Any) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, self.tr("No Action Selected"), self.tr("Select an Action Center item first."))
            return

        if item.source == "catalog:v18":
            self.selected_summary.setText(
                "\n".join(
                    [
                        f"{self.tr('Preview')}: {item.title}",
                        self.tr(
                            "Create a plan to run fresh preflight and generate the exact command."
                        ),
                        f"{self.tr('Recovery guidance')}: {item.rollback_hint}",
                    ]
                )
            )
            self.detail_area.setPlainText(
                "\n".join(
                    [
                        f"{self.tr('Preview')}: {item.title}",
                        self.tr("Create a plan to run fresh preflight and generate the exact command."),
                        f"{self.tr('Risk')}: {item.risk_level}",
                        f"{self.tr('Recovery')}: {item.rollback_hint}",
                    ]
                )
            )
            return

        result = self._service.preview(item)
        self.selected_summary.setText(
            "\n".join(
                [
                    f"{self.tr('Preview')}: {item.title}",
                    f"{self.tr('Result')}: {result.message}",
                    f"{self.tr('Recovery guidance')}: {item.rollback_hint}",
                ]
            )
        )
        self.detail_area.setPlainText(
            "\n".join(
                [
                    f"{self.tr('Preview')}: {item.title}",
                    f"{self.tr('Result')}: {result.message}",
                    f"{self.tr('Risk')}: {item.risk_level}",
                    f"{self.tr('Rollback')}: {item.rollback_hint}",
                    f"{self.tr('Command')}: {' '.join(item.command_preview) if item.command_preview else self.tr('Manual-only')}",
                ]
            )
        )

    def _plan_selected(self: typing.Any) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, self.tr("No Action Selected"), self.tr("Select an Action Center item first."))
            return

        action_id = self._ACTION_ID_ADAPTERS.get(item.id, item.id)
        parameters = dict(self._requested_parameters)
        if action_id == "restart-failed-service":
            service = str(parameters.get("service", ""))
            if not service:
                service = str(item.metadata.get("service", "")) if isinstance(item.metadata, dict) else ""
            if not service and item.command_preview:
                service = str(item.command_preview[-1])
            if not service:
                service, accepted = QInputDialog.getText(
                    self,
                    self.tr("Failed Service"),
                    self.tr("Enter the exact failed systemd unit (for example, example.service):"),
                )
                if not accepted:
                    return
            if service:
                parameters["service"] = service

        orchestrator = self._orchestrator_instance()
        context = self._requested_finding_context
        def operation():
            if context is not None:
                return orchestrator.plan_from_finding(
                    check_result_id=str(context.get("check_result_id", "")),
                    finding_fingerprint=str(
                        context.get("finding_fingerprint", "")
                    ),
                    origin_route=str(context.get("origin_route", "")),
                    expected_action_id=action_id,
                    target=self._target_key,
                )
            return orchestrator.plan(
                action_id,
                parameters,
                target=self._target_key,
            )
        self._start_operation(
            operation,
            self._accept_plan,
            self.tr("Action Plan Failed"),
        )

    def _accept_plan(self: typing.Any, plan: typing.Any) -> None:
        self._current_plan = plan
        self._current_run = None
        self._plans_by_id[str(plan.plan_id)] = plan
        self._set_lifecycle_primary(
            "run",
            enabled=plan.state in {"ready", "needs_review"},
        )
        self._show_plan(plan)

    def _show_plan(self: typing.Any, plan: typing.Any) -> None:
        title = self._action_title(str(plan.action_id))
        context = getattr(plan, "finding_context", None)
        context_line = (
            f"{self.tr('System Check')}: {context.check_result_id} / "
            f"{context.finding_fingerprint[:12]}"
            if context is not None
            else f"{self.tr('System Check')}: {self.tr('not linked')}"
        )
        self._set_selected_details(
            [
                f"{self.tr('Intended outcome')}: {title}",
                f"{self.tr('Affected components')}: {', '.join(plan.affected_resources) or self.tr('System')}",
                f"{self.tr('Privilege required')}: {self._privilege_label('pkexec' if plan.privileged else 'none')}",
                f"{self.tr('Restart requirement')}: {self._restart_label(plan.reboot_policy)}",
                f"{self.tr('Verification')}: {self.tr('Required after execution')}",
                f"{self.tr('Recovery guidance')}: {plan.recovery_guidance}",
            ],
            [
                f"{self.tr('Plan')}: {plan.plan_id}",
                f"{self.tr('Definition')}: {plan.action_id}",
                context_line,
                f"{self.tr('State')}: {plan.state}",
                f"{self.tr('Risk')}: {plan.risk_level}",
                f"{self.tr('Preflight')}: {plan.policy_decision.reason_code} — {plan.policy_decision.explanation}",
                f"{self.tr('Command preview')}: {' '.join(plan.preview) if plan.preview else self.tr('Manual-only')}",
                f"{self.tr('Expires')}: {plan.expires_at}",
            ],
        )

    def _run_current_plan(self: typing.Any) -> None:
        plan = self._current_plan
        if plan is None:
            QMessageBox.warning(self, self.tr("No Plan"), self.tr("Review and create a plan first."))
            return

        answer = QMessageBox.question(
            self,
            self.tr("Confirm Action"),
            self.tr("Run the reviewed command now? The preflight will be checked again."),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        accept_no_rollback = False
        if plan.risk_level in {"medium", "high"} and not plan.rollback_supported:
            answer = QMessageBox.question(
                self,
                self.tr("No Automatic Rollback"),
                self.tr("This action has no supported rollback. Accept the recovery guidance and continue?"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            accept_no_rollback = True

        try:
            orchestrator = self._orchestrator_instance()
            prepared = orchestrator.prepare_run(
                plan.plan_id,
                confirmed=True,
                accept_no_rollback=accept_no_rollback,
            )
            vector = orchestrator.facade.asynchronous_execution_vector(
                prepared.command,
                privileged=prepared.privileged,
                action_id=prepared.action_id,
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, self.tr("Action Blocked"), str(exc))
            return

        self._prepared_run = prepared
        self._output_chunks = []
        self._stderr_chunks = []
        self._set_lifecycle_primary("run", enabled=False)
        self.output_area.clear()
        self.append_output(self.tr("Running reviewed Action Center plan asynchronously...\n"))
        self.runner.run_command(vector[0], vector[1:], authority="action_center")

    def _capture_output(self: typing.Any, text: str) -> None:
        self._output_chunks.append(str(text))

    def _capture_stderr(self: typing.Any, text: str) -> None:
        self._stderr_chunks.append(str(text))

    def on_command_finished(self: typing.Any, exit_code: typing.Any) -> typing.Any:
        prepared = self._prepared_run
        if prepared is None:
            return
        if self._interrupt_reason is not None:
            self._finalize_interrupted_run(prepared, self._interrupt_reason)
            return
        from core.executor.action_result import ActionResult

        result = ActionResult(
            success=exit_code == 0,
            message=self.tr("Execution finished; separate verification is required.") if exit_code == 0 else self.tr("Execution failed."),
            exit_code=int(exit_code),
            stdout="".join(self._output_chunks),
            stderr="".join(self._stderr_chunks),
            action_id=prepared.action_id,
        )
        self._prepared_run = None
        try:
            run = self._orchestrator_instance().complete_run(prepared.run_id, result)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, self.tr("Run Recording Failed"), str(exc))
            return
        self._current_run = run
        self.append_output(self.tr("\nExecution state: %1\n").replace("%1", run.state))
        self._show_run(run)

    def on_error(self: typing.Any, error_msg: typing.Any) -> typing.Any:
        self.append_output(self.tr("\n[ERROR] %1\n").replace("%1", str(error_msg)))
        prepared = self._prepared_run
        if prepared is None:
            return
        self._interrupt_reason = "command-runner-error"
        # Timeout/error signals may arrive while QProcess is still alive. Keep
        # the cross-process mutation lease until termination is confirmed by
        # the finished signal. Failed-to-start is already safely not running.
        if not self.runner.is_running():
            self._finalize_interrupted_run(prepared, self._interrupt_reason)

    def _cancel_command(self: typing.Any) -> typing.Any:
        prepared = self._prepared_run
        if prepared is not None:
            self._interrupt_reason = "user-cancelled"
        self.runner.stop()
        if prepared is not None and not self.runner.is_running():
            self._finalize_interrupted_run(prepared, self._interrupt_reason or "user-cancelled")

    def _finalize_interrupted_run(self: typing.Any, prepared: typing.Any, reason: str) -> None:
        """Persist interruption only after the command process is not running."""
        self._prepared_run = None
        self._interrupt_reason = None
        try:
            self._current_run = self._orchestrator_instance().interrupt_run(prepared.run_id, reason)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, self.tr("Run Recording Failed"), str(exc))
            return
        self._show_run(self._current_run)

    def _verify_current_run(self: typing.Any) -> None:
        run = self._current_run
        if run is None:
            QMessageBox.warning(self, self.tr("No Run"), self.tr("Run a reviewed plan before verification."))
            return
        self._set_lifecycle_primary("verify", enabled=False)
        orchestrator = self._orchestrator_instance()
        self._start_operation(
            lambda: orchestrator.verify(run.run_id),
            self._accept_verification,
            self.tr("Verification Failed"),
        )

    def _accept_verification(self: typing.Any, verified: typing.Any) -> None:
        self._current_run = verified
        self._show_run(verified)

    def _request_follow_up_check(self: typing.Any) -> None:
        run = self._current_run
        context = getattr(run, "finding_context", None) if run is not None else None
        if (
            run is None
            or context is None
            or str(getattr(run, "state", "")) != "succeeded"
        ):
            return
        self.systemCheckRequested.emit(
            {
                "run_id": str(run.run_id),
                "check_result_id": context.check_result_id,
                "finding_fingerprint": context.finding_fingerprint,
                "affected_resources": list(context.affected_resources),
            }
        )

    def _show_run(self: typing.Any, run: typing.Any) -> None:
        verification = run.verification_result or {}
        plan = self._plans_by_id.get(str(run.plan_id))
        privilege = (
            self._privilege_label("pkexec" if plan.privileged else "none")
            if plan is not None
            else self.tr("Recorded in the reviewed plan")
        )
        context = getattr(run, "finding_context", None)
        can_check_again = (
            context is not None
            and str(getattr(run, "state", "")) == "succeeded"
        )
        if can_check_again:
            self._set_lifecycle_primary("check_again", enabled=True)
        elif str(getattr(run, "state", "")) in {"verifying", "awaiting_reboot"}:
            self._set_lifecycle_primary("verify", enabled=True)
        else:
            self._set_lifecycle_primary("", enabled=False)
        self.check_again_button.setToolTip(
            self.tr("Run a later read-only System Check for: %1").replace(
                "%1",
                ", ".join(context.affected_resources)
                if context is not None and context.affected_resources
                else self.tr("the linked finding"),
            )
            if can_check_again
            else self.tr(
                "Finish verification and any required reboot before checking the finding again."
            )
        )
        context_line = (
            f"{self.tr('System Check')}: {context.check_result_id} / "
            f"{context.finding_fingerprint[:12]}"
            if context is not None
            else f"{self.tr('System Check')}: {self.tr('not linked')}"
        )
        self._set_selected_details(
            [
                f"{self.tr('Intended outcome')}: {self._action_title(str(run.action_id))}",
                f"{self.tr('Affected components')}: {', '.join(run.affected_resources) or self.tr('System')}",
                f"{self.tr('Privilege required')}: {privilege}",
                f"{self.tr('Restart requirement')}: {self._restart_label(run.reboot_policy, required=run.reboot_required)}",
                f"{self.tr('Verification')}: {verification.get('message', self.tr('Pending'))}",
                f"{self.tr('Recovery guidance')}: {run.recovery_status}",
            ],
            [
                f"{self.tr('Run')}: {run.run_id}",
                f"{self.tr('Plan')}: {run.plan_id}",
                f"{self.tr('Definition')}: {run.action_id}",
                context_line,
                f"{self.tr('State')}: {run.state}",
                f"{self.tr('Execution')}: {(run.execution_result or {}).get('message', '')}",
                f"{self.tr('Verification attempts')}: {getattr(run, 'verification_attempts', 0)}",
                (
                    self.tr("Finding resolution: requires a later compatible System Check")
                    if context is not None
                    else self.tr("Finding resolution: not linked")
                ),
            ],
        )

    def _show_history(self: typing.Any) -> None:
        from core.actions import ActionPlanStore, ActionRunStore

        history = self._service.recent_history(limit=25)
        plans = ActionPlanStore().list(limit=25)
        runs = ActionRunStore().list(limit=25)
        if not history and not plans and not runs:
            self.selected_summary.setText(
                self.tr("No Action Center history has been recorded.")
            )
            self.detail_area.setPlainText(self.tr("No Action Center history recorded."))
            return
        lines = []
        for plan in reversed(plans):
            lines.append(f"{plan.plan_id}: {plan.action_id} [{plan.state}]")
        for run in reversed(runs):
            lines.append(f"{run.run_id}: {run.action_id} [{run.state}]")
        for entry in history:
            event = entry.get("event", "event")
            action = entry.get("action", {})
            title = action.get("title", action.get("id", "unknown")) if isinstance(action, dict) else "unknown"
            lines.append(f"{event}: {title}")
        self.selected_summary.setText(
            self.tr("Loaded %d recent Action Center records.") % len(lines)
        )
        self.detail_area.setPlainText("\n".join(lines))
        viable = next((plan for plan in reversed(plans) if plan.state in {"ready", "needs_review"} and not plan.is_expired()), None)
        if viable is not None:
            self._current_plan = viable
            self._set_lifecycle_primary("run", enabled=True)
