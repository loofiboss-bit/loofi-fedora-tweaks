"""Action Center review, execution, verification, and history surface."""

import typing

from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui.base_tab import BaseTab
from ui.action_center_presentation import (
    ACTION_CENTER_STATE_GROUPS,
    ActionCenterDetails,
    action_center_group_for_state,
    candidate_details,
    lifecycle_presence_copy,
    plan_details,
    preview_lines,
    privilege_label,
    restart_label,
    run_details,
)
from ui.action_center_views import ActionCenterDetailPane, ActionCenterMasterPane
from ui.action_center_worker import ActionCenterOperationWorker
from ui.components import PrimaryButton, QuietButton, SecondaryButton
from ui.components.layout import PageScaffold
from ui.maintenance_direct import DirectActionUiMixin
from ui.shared_states import DetailsDisclosure, ResultBanner


_ActionCenterOperationWorker = ActionCenterOperationWorker


class _ActionCenterSubTab(DirectActionUiMixin, BaseTab):
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
        self._direct_service = None

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

        self.master_pane = ActionCenterMasterPane(ACTION_CENTER_STATE_GROUPS)
        self.mode_switcher = self.master_pane.mode_switcher
        self.lifecycle_view = self.master_pane.lifecycle_view
        self.action_list = self.master_pane.action_list
        self.mode_switcher.viewActivated.connect(self._show_master_mode)
        self.lifecycle_view.currentIndexChanged.connect(self._show_lifecycle_view)

        advanced_widget = QWidget()
        advanced_widget.setObjectName("actionCenterControls")
        advanced_layout = QVBoxLayout(advanced_widget)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        target_load_row = QHBoxLayout()
        target_review_row = QHBoxLayout()
        load_stable = SecondaryButton(self.tr("Reload Fedora %s Actions") % FEDORA_RELEASE_POLICY.stable_release)
        self.load_stable_button = load_stable
        load_stable.clicked.connect(lambda: self._load_target(FEDORA_RELEASE_POLICY.stable_target))
        target_load_row.addWidget(load_stable)

        load_preview = SecondaryButton(self.tr("Load Fedora %s Preview Actions") % FEDORA_RELEASE_POLICY.preview_release)
        self.load_preview_button = load_preview
        load_preview.clicked.connect(lambda: self._load_target(FEDORA_RELEASE_POLICY.preview_target))
        load_preview.hide()

        preview_button = QuietButton(self.tr("Preview Selected"))
        self.preview_button = preview_button
        preview_button.clicked.connect(self._preview_selected)
        target_load_row.addWidget(preview_button)

        history_button = QuietButton(self.tr("Show History"))
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

        review_button = PrimaryButton(self.tr("Review & Plan"))
        self.review_button = review_button
        review_button.clicked.connect(self._plan_selected)
        target_review_row.addWidget(review_button)

        self.run_button = PrimaryButton(self.tr("Run Plan"))
        self.run_button.clicked.connect(self._run_current_plan)
        self.run_button.setEnabled(False)
        target_review_row.addWidget(self.run_button)

        self._add_direct_action_button(target_review_row)

        self.verify_button = PrimaryButton(self.tr("Verify Run"))
        self.verify_button.clicked.connect(self._verify_current_run)
        self.verify_button.setEnabled(False)
        target_review_row.addWidget(self.verify_button)

        self.check_again_button = PrimaryButton(self.tr("Check again"))
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

        self.presentation_banner = ResultBanner(
            self.tr("Action Center status"),
            self.tr("Loading Action Center candidates…"),
        )
        self.presentation_status = self.presentation_banner.message_label
        self.presentation_status.setAccessibleName(self.tr("Action Center status"))
        layout.addWidget(self.presentation_banner)

        self.detail_pane = ActionCenterDetailPane()
        self.risk_panel = self.detail_pane.risk_panel
        self.selected_summary = self.detail_pane.selected_summary
        self.detail_disclosure = self.detail_pane.detail_disclosure
        self.detail_area = self.detail_pane.detail_area
        self.detail_pane.body.insertLayout(1, target_review_row)
        workspace = QSplitter()
        workspace.setObjectName("actionCenterMasterDetail")
        workspace.setOrientation(Qt.Orientation.Horizontal)
        workspace.setChildrenCollapsible(False)
        workspace.addWidget(self.master_pane)
        workspace.addWidget(self.detail_pane)
        workspace.setStretchFactor(0, 2)
        workspace.setStretchFactor(1, 3)
        layout.addWidget(workspace, 1)

        self.action_list.currentRowChanged.connect(self._selection_changed)
        self.add_output_disclosure(self.detail_pane.body, self.tr("Show Action Center command output"))
        self.runner.output_received.connect(self._capture_output)
        self.runner.stderr_received.connect(self._capture_stderr)

        self._set_lifecycle_primary("review", enabled=False)
        self.mode_switcher.set_active_view("queue")

        self._load_target(self._target_key)

    def _orchestrator_instance(self: typing.Any) -> typing.Any:
        if self._orchestrator is None:
            from core.actions import ActionCenterOrchestrator

            self._orchestrator = ActionCenterOrchestrator()
        return self._orchestrator

    def _load_target(self: typing.Any, target_key: str) -> None:
        self._target_key = target_key
        self.mode_switcher.set_active_view("queue")
        self.master_pane.lifecycle_controls.show()
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

    def _show_master_mode(self, mode_id: str) -> None:
        """Switch the presentation between persisted work and inert catalog browsing."""
        catalog_mode = mode_id == "catalog"
        self.master_pane.lifecycle_controls.setVisible(not catalog_mode)
        if not catalog_mode:
            self._show_lifecycle_view(self.lifecycle_view.currentIndex())
            return
        self._current_plan = None
        self._current_run = None
        self._visible_records = [("candidate", item) for item in self._items]
        self._set_lifecycle_primary("review", enabled=False)
        self.master_pane.populate_catalog(self._items)
        self.presentation_banner.set_result(
            "info",
            self.tr("Browsing the action catalog"),
            self.tr("Select an action to inspect it. A plan is created only with Review & Plan."),
        )
        self.selected_summary.setText(
            self.tr("Select an available action to review its scope and safety evidence.")
        )
        self.detail_area.setPlainText(
            self.tr("Catalog browsing does not approve, prepare, or run an action.")
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
            self.master_pane.add_record(kind, record, self._action_title)

        if self._visible_records:
            title, message = lifecycle_presence_copy(group_label, len(self._visible_records), self.tr)
            self.presentation_banner.set_result("info", title, message)
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
        return privilege_label(privilege, self.tr)

    def _restart_label(self, reboot_policy: typing.Any, *, required: bool = False) -> str:
        """Translate the closed reboot policy without exposing stored values."""
        return restart_label(reboot_policy, self.tr, required=required)

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
        self.mode_switcher.set_active_view("queue")
        self.master_pane.lifecycle_controls.show()
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
                self.direct_button,
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
            "direct": self.direct_button,
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
        self._show_direct_action_for_item(item)
        if item.manual_only:
            self.presentation_status.setText(self.tr("Manual-only recommendation: review the guidance; Action Center will not execute it."))
        self._apply_details(candidate_details(item, self.tr))

    def _apply_details(self, details: ActionCenterDetails) -> None:
        self.risk_panel.set_review_facts(
            risk=details.risk,
            scope=details.scope,
            requirements=details.requirements,
            validation=details.validation,
            rollback=details.rollback,
        )
        self._set_selected_details(
            list(details.summary_lines),
            list(details.technical_lines),
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

        result_message = ""
        if item.source != "catalog:v18":
            result_message = str(self._service.preview(item).message)
        summary, technical = preview_lines(
            item,
            self.tr,
            result_message=result_message,
        )
        self._set_selected_details(list(summary), list(technical))

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
        self._apply_details(plan_details(plan, title, self.tr))

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
        self._apply_details(
            run_details(
                run,
                self._action_title(str(run.action_id)),
                privilege,
                self.tr,
            )
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
