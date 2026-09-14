"""Direct-action controls backed by the Action Center lifecycle."""

import typing


class DirectActionUiMixin:
    """Keep compact execution interaction out of the main Action Center view."""

    def _add_direct_action_button(self: typing.Any, target_review_row: typing.Any) -> None:
        from ui.components import PrimaryButton

        self.direct_button = PrimaryButton(self.tr("Run action"))
        self.direct_button.setToolTip(
            self.tr(
                "Use the configured direct-action policy with fresh preflight and independent verification."
            )
        )
        self.direct_button.clicked.connect(self._run_direct_selected)
        self.direct_button.setEnabled(False)
        target_review_row.addWidget(self.direct_button)

    def _show_direct_action_for_item(self: typing.Any, item: typing.Any) -> None:
        if self.mode_switcher.active_view_id() == "catalog":
            return
        service = self._direct_service_instance()
        eligibility = service.eligibility_for(
            self._ACTION_ID_ADAPTERS.get(item.id, item.id)
        )
        if (
            eligibility.allowed
            and eligibility.kind in {"direct", "confirmation"}
        ):
            self._set_lifecycle_primary("direct", enabled=True)

    def _direct_service_instance(self: typing.Any) -> typing.Any:
        if self._direct_service is None:
            from core.actions import DirectActionService

            self._direct_service = DirectActionService(
                orchestrator=self._orchestrator_instance(),
            )
        return self._direct_service

    def _direct_parameters(self: typing.Any, item: typing.Any) -> dict[str, typing.Any] | None:
        """Resolve UI-only parameters before handing the request to the core service."""
        action_id = self._ACTION_ID_ADAPTERS.get(item.id, item.id)
        parameters = dict(self._requested_parameters)
        if action_id != "restart-failed-service" or parameters.get("service"):
            return parameters
        service = str(item.metadata.get("service", "")) if isinstance(item.metadata, dict) else ""
        if not service and item.command_preview:
            service = str(item.command_preview[-1])
        if not service:
            from PyQt6.QtWidgets import QInputDialog

            service, accepted = QInputDialog.getText(
                self,
                self.tr("Failed Service"),
                self.tr("Enter the exact failed systemd unit (for example, example.service):"),
            )
            if not accepted:
                return None
        parameters["service"] = service
        return parameters

    def _run_direct_selected(self: typing.Any) -> None:
        from PyQt6.QtWidgets import QMessageBox

        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, self.tr("No Action Selected"), self.tr("Select an Action Center item first."))
            return
        parameters = self._direct_parameters(item)
        if parameters is None:
            return
        action_id = self._ACTION_ID_ADAPTERS.get(item.id, item.id)
        service = self._direct_service_instance()
        self._pending_direct_action = (action_id, parameters)
        self._prepared_direct_result = None
        self._set_lifecycle_primary("direct", enabled=False)
        self.presentation_banner.set_result(
            "info",
            self.tr("Preparing action"),
            self.tr("Fresh preflight is checking the exact scope before any change is applied."),
        )
        context = self._requested_finding_context
        self._start_operation(
            lambda: service.run(
                action_id,
                parameters,
                finding_context=context,
                dry_run=True,
                execution_mode="direct",
                target=self._target_key,
            ),
            self._accept_direct_preview,
            self.tr("Action failed"),
        )

    def _accept_direct_preview(self: typing.Any, result: typing.Any) -> None:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QMessageBox

        from core.actions.direct import DirectActionResult

        if not isinstance(result, DirectActionResult):
            QMessageBox.warning(self, self.tr("Action failed"), self.tr("The direct-action result was invalid."))
            self._set_lifecycle_primary("", enabled=False)
            return
        self._prepared_direct_result = result
        if result.status != "preview" or not result.plan_id:
            self._accept_direct_result(result)
            return
        service = self._direct_service_instance()
        settings = service.settings_store.load()
        needs_confirmation = (
            result.eligibility.kind == "confirmation"
            or (
                (
                    getattr(service.settings_store, "explicit_mode", False)
                    or settings.future_schema
                )
                and settings.effective_mode == "review_first"
            )
        )
        if needs_confirmation:
            preview = " ".join(result.preview) if result.preview else self.tr("Protected Action Center operation")
            reboot = {
                "required": self.tr("Required"),
                "may_require": self.tr("May be required"),
                "none": self.tr("Not normally required"),
            }.get(str(getattr(result, "reboot_policy", "none")), self.tr("Check result"))
            change = next(
                (
                    str(fact.value)
                    for fact in getattr(result.outcome, "expected", ())
                    if getattr(fact, "key", "") == "expected_change"
                ),
                result.message,
            )
            answer = QMessageBox.question(
                self,
                self.tr("Confirm action"),
                self.tr(
                    "Run %1 now?\n\nChange: %2\nAffected resources: %3\nRestart: %4\nPrepared operation: %5"
                ).replace("%1", result.action_id)
                .replace("%2", change)
                .replace("%3", ", ".join(result.outcome.affected_resources) or self.tr("system state"))
                .replace("%4", reboot)
                .replace("%5", preview),
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._prepared_direct_result = None
                self.presentation_banner.set_result(
                    "warning",
                    self.tr("Action cancelled"),
                    self.tr("No change was applied."),
                )
                self._set_lifecycle_primary("", enabled=False)
                return
        QTimer.singleShot(0, self._run_prepared_direct)

    def _run_prepared_direct(self: typing.Any) -> None:
        from PyQt6.QtCore import QTimer

        prepared = getattr(self, "_prepared_direct_result", None)
        if prepared is None:
            return
        if self._operation_thread is not None:
            QTimer.singleShot(10, self._run_prepared_direct)
            return
        service = self._direct_service_instance()
        self.presentation_banner.set_result(
            "info",
            self.tr("Maintenance in progress"),
            self.tr("Action Center is applying the prepared change and verifying the result."),
        )
        self._start_operation(
            lambda: service.run_prepared(
                prepared.plan_id,
                confirmed=True,
                execution_mode="direct",
            ),
            self._accept_direct_result,
            self.tr("Action failed"),
        )

    def _accept_direct_result(self: typing.Any, result: typing.Any) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from core.actions.direct import DirectActionResult

        if not isinstance(result, DirectActionResult):
            QMessageBox.warning(self, self.tr("Action failed"), self.tr("The direct-action result was invalid."))
            return
        self._prepared_direct_result = None
        self._pending_direct_action = None
        service = self._direct_service_instance()
        self._current_run = None
        self._current_plan = None
        self.presentation_banner.set_result(
            "success" if result.status == "completed_verified" else "warning",
            result.display_label,
            result.message,
        )
        if result.plan_id:
            try:
                self._current_plan = service.orchestrator.get_plan(result.plan_id)
                self._plans_by_id[result.plan_id] = self._current_plan
            except (OSError, RuntimeError, ValueError, TypeError):
                self._current_plan = None
        if result.run_id:
            try:
                self._current_run = service.orchestrator.get_run(result.run_id)
            except (OSError, RuntimeError, ValueError, TypeError):
                self._current_run = None
        if self._current_run is not None:
            self._show_run(self._current_run)
        elif self._current_plan is not None:
            self._show_plan(self._current_plan)
        else:
            self._set_selected_details(
                [f"{self.tr('Outcome')}: {result.display_label}", result.message],
                [
                    f"{self.tr('Action')}: {result.action_id}",
                    f"{self.tr('Outcome state')}: {result.outcome.state}",
                    f"{self.tr('Recovery')}: {result.outcome.recovery.status}",
                ],
            )
        if self._current_run is None:
            self._set_lifecycle_primary("", enabled=False)
