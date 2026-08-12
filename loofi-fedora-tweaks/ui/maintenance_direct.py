"""Proof direct-action controls for the Action Center surface."""

import typing


class DirectActionUiMixin:
    """Keep Proof-specific presentation and interaction out of the main view."""

    def _add_direct_action_button(self: typing.Any, target_review_row: typing.Any) -> None:
        from ui.components import PrimaryButton

        self.direct_button = PrimaryButton(self.tr("Run with Proof"))
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
        settings = service.settings_store.load()
        if (
            eligibility.allowed
            and eligibility.kind in {"direct", "confirmation"}
            and settings.effective_mode == "direct"
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
        eligibility = service.eligibility_for(action_id)
        settings = service.settings_store.load()
        if eligibility.kind == "confirmation" and settings.confirm_medium_risk:
            answer = QMessageBox.question(
                self,
                self.tr("Confirm medium-risk action"),
                self.tr("Run this medium-risk action once after a fresh preflight and verify the result?"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._set_lifecycle_primary("direct", enabled=False)
        self.presentation_banner.set_result(
            "info",
            self.tr("Proof execution in progress"),
            self.tr("Fresh preflight, one execution, and independent verification are running."),
        )
        context = self._requested_finding_context
        self._start_operation(
            lambda: service.run(
                action_id,
                parameters,
                finding_context=context,
                confirmed=True,
                target=self._target_key,
            ),
            self._accept_direct_result,
            self.tr("Proof Execution Failed"),
        )

    def _accept_direct_result(self: typing.Any, result: typing.Any) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from core.actions.direct import DirectActionResult

        if not isinstance(result, DirectActionResult):
            QMessageBox.warning(self, self.tr("Proof Execution Failed"), self.tr("The direct-action result was invalid."))
            return
        service = self._direct_service_instance()
        self.presentation_banner.set_result(
            "success" if result.status in {"completed_verified", "completed_awaiting_reboot"} else "warning",
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
        self._set_lifecycle_primary("", enabled=False)
