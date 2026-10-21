"""v29 utility-shell route projection for :class:`MainWindow`.

The utility shell is a presentation layer over the existing route manifest.
Keeping its route aliases, landing pages, and compatibility redirects in a
focused mixin keeps the window assembly readable while preserving one route
authority and the legacy action workflow handoff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from core.navigation import (
    DirectLinkBehavior,
    NavigationDecision,
    NavigationPolicy,
    NavigationRoute,
    get_destination,
    placement_for_route,
    resolve,
)
from core.navigation.routes import (
    LEGACY_ALIASES,
    advanced_shell_route_for,
    all_shell_routes,
    visible_shell_routes,
)
from core.plugins.metadata import PluginMetadata
from PyQt6.QtWidgets import QTreeWidgetItem, QWidget
from ui.application_review import ApplicationReviewMixin
from ui.tweak_profiles import TweakProfilesMixin
from ui.care_navigation import CareNavigationMixin
from ui.kde_appearance import CursorSettingsMixin
from ui.main_window_operation_status import MainWindowOperationStatusMixin


_UTILITY_ROUTE_ALIASES = LEGACY_ALIASES

# These routes are retained as compatibility inputs, but a direct user link
# must open the trusted Activity ledger instead of the retired review screen.
_ACTIVITY_COMPATIBILITY_ROUTES = frozenset(
    {"changes", "maintenance:action-center"}
)


@dataclass
class SidebarEntry:
    """Indexed sidebar tab entry for O(1) lookups by plugin ID."""

    plugin_id: str
    display_name: str
    tree_item: QTreeWidgetItem | None
    page_widget: QWidget
    metadata: PluginMetadata
    status: str = field(default="")
    content_widget: QWidget | None = field(default=None)
    area_id: str = field(default="")
    visible_in_sidebar: bool = field(default=True)


class MainWindowUtilityMixin(ApplicationReviewMixin, MainWindowOperationStatusMixin, CursorSettingsMixin, TweakProfilesMixin, CareNavigationMixin):
    """Own v29 landing pages and compatibility-aware route navigation."""

    _pending_runtime_shutdown: str | None

    def _initialize_utility_state(self: Any) -> None:
        """Initialize state for the five visible utility destinations."""
        self._utility_destinations: tuple[Any, ...] = ()
        self._utility_route_objects: dict[str, NavigationRoute] = {}
        self._utility_shell_ready = False
        self._internal_action_route_navigation = False
        self._utility_operation_controller: Any | None = None
        self._utility_operation_adapter: Any | None = None
        self._pending_runtime_shutdown: str | None = None
        self._operation_origin_route_id = ""
        self._operation_origin_label = ""
        self._operation_name = ""
        self._quit_after_profile_save = False

    def _register_utility_landing_pages(self: Any) -> None:
        """Register lightweight placeholders for the four workflow pages."""
        from ui.lazy_widget import LazyWidget
        self._utility_destinations = all_shell_routes()
        destination_by_id = {
            destination.id: destination
            for destination in self._utility_destinations
        }
        for destination_id in ("tune", "install", "update", "fix"):
            destination = destination_by_id[destination_id]
            plugin_id = f"utility_{destination_id}"
            route_id = destination.default_route_id

            def load_page(selected_id: str = destination_id) -> QWidget:
                return cast(QWidget, self._create_utility_workflow_page(selected_id))

            page = LazyWidget(
                load_page,
                loading_text=self.tr("Loading %1…").replace("%1", destination.label),
            )
            meta = PluginMetadata(
                id=plugin_id,
                name=destination.label,
                description=destination.description,
                category="Utility",
                icon=destination.icon,
                badge="recommended",
                order={"tune": 10, "install": 20, "update": 30, "fix": 40}[destination_id],
            )
            route = NavigationRoute(
                id=route_id,
                label=destination.label,
                plugin_id=plugin_id,
                category="Utility",
                icon=destination.icon,
                description=destination.description,
                aliases=(destination.label,),
                keywords=(destination_id, "fedora", "utility"),
                risk="none",
                visibility="all",
            )
            entry = SidebarEntry(
                plugin_id=plugin_id,
                display_name=destination.label,
                tree_item=None,
                page_widget=page,
                metadata=meta,
                area_id=destination_id,
                visible_in_sidebar=False,
            )
            self._utility_route_objects[route_id] = route
            self._register_in_index(
                plugin_id,
                entry,
                scroll_widget=self._wrap_page_widget(page),
            )
        self._utility_shell_ready = True

    def _create_utility_workflow_page(
        self: Any,
        destination_id: str,
    ) -> QWidget:
        """Create one workflow on its first route visit and connect its signals."""
        from core.tasks import ApplicationContext, TaskContext, UpdateOverviewState

        try:
            task_context = TaskContext.from_platform_profile(self._platform_profile)
        except (AttributeError, TypeError, ValueError):
            task_context = TaskContext.from_navigation_context(self._navigation_context)
        application_context = ApplicationContext.from_task_context(task_context)

        if destination_id == "install":
            from ui.install_workflow import InstallWorkflowPage
            from services.software.source_status import SoftwareSourceStatusService
            from services.software.installed_applications import InstalledApplicationService

            install_page: Any = InstallWorkflowPage(
                context=application_context,
                source_status_service=SoftwareSourceStatusService(),
                installed_service=InstalledApplicationService(),
            )
            install_page.bundleReviewRequested.connect(
                lambda selection, owner=install_page: self._review_utility_bundle(owner, selection)
            )
            install_page.routeRequested.connect(self._open_route_request)
            install_page.contextRouteRequested.connect(self._open_route_request)
            install_page.actionReviewRequested.connect(
                lambda action_id, parameters, owner=install_page: self._review_health_action(owner, action_id, parameters)
            )
            return cast(QWidget, install_page)
        if destination_id == "tune":
            from ui.tweaks_page import TweaksPage

            tweaks_page: Any = TweaksPage(self._platform_profile)
            tweaks_page.refreshRequested.connect(
                lambda owner=tweaks_page: self._start_tweak_snapshot(owner)
            )
            tweaks_page.continueSnapshotRequested.connect(lambda owner=tweaks_page: self._continue_tweak_snapshot(owner))
            tweaks_page.activityRequested.connect(self._open_action_center_run)
            tweaks_page.profileActionRequested.connect(
                lambda operation, entry, owner=tweaks_page: self._handle_tweak_profile_action(owner, operation, entry)
            )
            tweaks_page.profileSaveCopyRequested.connect(
                lambda profile, review_after, return_after, close_after, owner=tweaks_page: self._save_tweak_profile_copy(
                    owner, profile, review_after, return_after, close_after=close_after
                )
            )
            tweaks_page.cancelSnapshotRequested.connect(
                lambda owner=tweaks_page: self._cancel_tweak_snapshot(owner)
            )
            tweaks_page.changeRequested.connect(
                lambda tweak_id, value, owner=tweaks_page: self._start_tweak_change(owner, tweak_id, value)
            )
            tweaks_page.restoreRequested.connect(
                lambda tweak_id, source_id, owner=tweaks_page: self._start_tweak_restore(owner, tweak_id, source_id)
            )
            tweaks_page.saveProfileRequested.connect(lambda owner=tweaks_page: self._start_tweak_profile_export(owner))
            tweaks_page.loadProfileRequested.connect(lambda owner=tweaks_page: self._start_tweak_profile_import(owner))
            tweaks_page.choosePresetRequested.connect(lambda owner=tweaks_page: self._start_tweak_preset(owner))
            tweaks_page.inspectRequested.connect(
                lambda tweak_id, owner=tweaks_page: self._start_tweak_inspection(owner, tweak_id)
            )
            tweaks_page.cursor_settings_requested.connect(lambda owner=tweaks_page: self._open_cursor_settings(owner))
            return cast(QWidget, tweaks_page)
        if destination_id == "fix":
            from ui.fix_workflow import FixWorkflowPage

            fix_page: Any = FixWorkflowPage()
            fix_page.actionCenterRequested.connect(
                lambda action_id, parameters, owner=fix_page: self._review_health_action(owner, action_id, parameters)
            )
            fix_page.maintenanceRequested.connect(
                lambda action_id, owner=fix_page: self._review_health_action(owner, action_id, {})
            )
            fix_page.routeRequested.connect(self._open_route_request)
            return cast(QWidget, fix_page)
        if destination_id == "update":
            from ui.update_workflow import UpdateWorkflowPage

            update_page: Any = UpdateWorkflowPage(state=UpdateOverviewState())
            update_page.sourceActionRequested.connect(
                lambda source, action, owner=update_page: self._handle_update_source_action(owner, source, action)
            )
            update_page.actionReviewRequested.connect(
                lambda action_id, parameters, owner=update_page: self._review_health_action(owner, action_id, parameters)
            )
            update_page.contextRouteRequested.connect(self._open_route_request)
            update_page.diagnosisRequested.connect(self._open_update_diagnosis)
            update_page.sourcesRequested.connect(self._open_package_sources)
            update_page.recordRequested.connect(self._open_action_center_run)
            self._restore_saved_updates(update_page)
            return cast(QWidget, update_page)
        raise ValueError(f"Unknown utility workflow destination: {destination_id}")

    def _start_tweak_snapshot(self: Any, page: Any, *, tweak_ids: tuple[str, ...] | None = None) -> bool:
        """Read current settings on the window-owned worker, without UI blocking."""
        if self._utility_operation_adapter is not None:
            page.set_error(self.tr("Another operation is in progress. Refresh when it finishes."))
            return False
        from core.actions.catalog import SystemActionRuntime
        from core.executor.command_facade import CommandFacade
        from core.tasks.tweaks import snapshot

        adapter = self._new_utility_operation_adapter(
            phase="inspection", operation_name=self.tr("Checking current settings")
        )
        adapter.finished.connect(page.set_states)
        adapter.failed.connect(page.set_error)
        adapter.cancelled.connect(lambda: page.set_busy(False, self.tr("Setting inspection cancelled. Refresh to try again.")))
        if getattr(page, "cursor_settings_buttons", {}):
            adapter.stopped.connect(lambda: self._refresh_cursor_settings_handoff(page))
        controller = self._utility_operation_controller
        runtime = controller.orchestrator.runtime if controller is not None else SystemActionRuntime(CommandFacade())
        page.set_busy(True, self.tr("Reading current settings…"), cancellable=True)
        started = adapter.start(
            lambda: snapshot(
                page.profile,
                runtime,
                tweak_ids=tweak_ids,
                is_cancelled=lambda: adapter.cancel_requested,
                on_progress=lambda completed, total: page.snapshotProgress.emit(completed, total),
            )
        )
        if not started:
            page.set_busy(False, self.tr("Setting inspection could not be started. Refresh to try again."))
        return bool(started)

    def _continue_tweak_snapshot(self: Any, page: Any) -> bool:
        remaining = tuple(page.remaining_inspection_ids())
        return bool(self._start_tweak_snapshot(page, tweak_ids=remaining)) if remaining else False

    def _start_tweak_inspection(self: Any, page: Any, tweak_id: str) -> bool:
        """Refresh one row without replacing the rest of the visible snapshot."""
        from core.actions.operation_controller import OperationController
        from core.tasks.tweaks import inspect_one

        if tweak_id not in page._rows:
            page.set_error(self.tr("The requested setting is unavailable."))
            return False
        if self._utility_operation_adapter is not None:
            page.set_error(self.tr("Another operation is in progress. Check this setting when it finishes."))
            return False
        controller = self._utility_operation_controller
        if controller is None:
            controller = OperationController()
        runtime = controller.orchestrator.runtime
        adapter = self._new_utility_operation_adapter(
            phase="inspection",
            operation_name=self.tr("Checking %1").replace("%1", self.tr(page._tweaks[tweak_id].title)),
        )
        adapter.finished.connect(lambda state: page.set_states((state,)))
        adapter.failed.connect(lambda message: page.set_check_error(tweak_id, str(message)))
        adapter.cancelled.connect(lambda: page.set_check_error(tweak_id, self.tr("Setting inspection cancelled. Its previous value is not current.")))
        page.set_busy(True, self.tr("Checking %1…").replace("%1", self.tr(page._tweaks[tweak_id].title)), cancellable=True)
        started = adapter.start(lambda: inspect_one(tweak_id, page.profile, runtime, is_cancelled=lambda: adapter.cancel_requested))
        if not started:
            page.set_busy(False, self.tr("Setting inspection could not be started."))
        return bool(started)

    def _cancel_tweak_snapshot(self: Any, page: Any) -> bool:
        """Request cooperative cancellation of the active read-only snapshot."""
        adapter = getattr(self, "_utility_operation_adapter", None)
        cancel = getattr(adapter, "cancel", None)
        if callable(cancel) and cancel():
            page.cancel_snapshot_button.setEnabled(False)
            page.status_label.setText(self.tr("Stopping after the current setting check…"))
            return True
        return False

    def _start_tweak_change(self: Any, page: Any, tweak_id: str, value: str) -> bool:
        """Apply one typed setting through the durable operation controller."""
        from core.actions.operation_controller import OperationController
        from core.tasks.tweaks import BY_ID
        from core.actions.tweak_operations import activate_verified_tweak, cursor_notification_parameters, notify_verified_cursor_change
        from PyQt6.QtWidgets import QDialog
        from ui.tweak_review import system_tweak_review

        tweak = BY_ID.get(str(tweak_id))
        if tweak is None:
            page.set_error(self.tr("The requested setting is unavailable."))
            return False
        if self._utility_operation_adapter is not None:
            page.restore_selection(tweak_id)
            page.set_error(self.tr("Another operation is in progress. Try again when it finishes."))
            return False
        accept_no_rollback = False
        if tweak.system_wide:
            current_value = str(page._rows[tweak_id][1].property("currentValue") or "")
            review = system_tweak_review(self, tweak, current_value, value, self.tr)
            if review.exec() != QDialog.DialogCode.Accepted:
                page.restore_selection(tweak_id)
                return False
            accept_no_rollback = review.accepts_no_rollback
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        controller = self._utility_operation_controller
        page.set_busy(True, self.tr("Applying and verifying %1…").replace("%1", self.tr(tweak.title)))
        adapter = self._new_utility_operation_adapter(
            phase="change",
            operation_name=self.tr("Applying %1").replace("%1", self.tr(tweak.title)),
        )
        page.set_pending(tweak_id, value)

        def completed(result: Any) -> None:
            outcome, activation = result
            page.set_outcome(tweak_id, value, outcome)
            if activation.message != outcome.message:
                page.set_activation(tweak_id, activation.message)

        def operation() -> Any:
            outcome = controller.execute(tweak.action_id, {"value": value}, confirmed=True, accept_no_rollback=accept_no_rollback)
            followup = notify_verified_cursor_change(controller, outcome) if cursor_notification_parameters(outcome) else activate_verified_tweak(controller, outcome)
            return outcome, followup

        adapter.finished.connect(completed)
        adapter.failed.connect(lambda message: page.set_error(str(message)))
        adapter.cancelled.connect(lambda: page.set_error(self.tr("The operation was cancelled. Refresh to see the current value.")))
        adapter.stopped.connect(lambda: self._start_tweak_inspection(page, tweak_id))
        return bool(adapter.start(operation))

    def _start_tweak_restore(self: Any, page: Any, tweak_id: str, source_id: str) -> bool:
        """Prepare a source-bound restoration before presenting exact values."""
        from core.actions.operation_controller import OperationController
        from core.tasks.tweaks import BY_ID

        if tweak_id not in BY_ID or self._utility_operation_adapter is not None:
            page.set_error(self.tr("Another operation is in progress or the setting is unavailable. Refresh and try again."))
            return False
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        controller = self._utility_operation_controller
        page.set_busy(True, self.tr("Checking the saved change and current value…"))
        adapter = self._new_utility_operation_adapter(
            phase="review",
            operation_name=self.tr("Preparing restore for %1").replace("%1", self.tr(BY_ID[tweak_id].title)),
        )
        adapter.finished.connect(lambda ticket: self._show_tweak_restore_review(page, tweak_id, ticket, adapter))
        adapter.failed.connect(lambda message: page.set_restore_error(tweak_id, str(message)))
        adapter.cancelled.connect(lambda: page.set_restore_error(tweak_id, self.tr("Restore preparation was cancelled. Refresh to retry.")))
        return bool(adapter.start(lambda: controller.prepare(f"restore-{tweak_id}", {"source_run_id": source_id})))

    def _show_tweak_restore_review(self: Any, page: Any, tweak_id: str, ticket: Any, adapter: Any) -> None:
        from core.tasks.tweaks import BY_ID
        from PyQt6.QtWidgets import QDialog
        from ui.tweak_review import tweak_restore_review

        if ticket.blocked:
            from ui.restore_conflict import restore_conflict_message

            message = restore_conflict_message(ticket.plan.policy_decision, self.tr)
            page.set_restore_error(tweak_id, message)
            adapter.stopped.connect(lambda: self._start_tweak_inspection(page, tweak_id))
            return
        facts = ticket.plan.policy_decision.facts
        tweak = BY_ID[tweak_id]
        review = tweak_restore_review(self, tweak, facts, str(ticket.plan.recovery_guidance), self.tr)
        if review.exec() != QDialog.DialogCode.Accepted:
            page.set_busy(False, self.tr("Restore cancelled. No change was made."))
            self._record_global_operation_result(None, self.tr("Review cancelled. No change was started."))
            return
        adapter.stopped.connect(lambda: self._run_tweak_restore(page, tweak_id, ticket, accept_no_rollback=review.accepts_no_rollback))

    def _run_tweak_restore(self: Any, page: Any, tweak_id: str, ticket: Any, *, accept_no_rollback: bool = False) -> bool:
        from core.actions.tweak_operations import activate_verified_tweak, cursor_notification_parameters, notify_verified_cursor_change

        controller = self._utility_operation_controller
        if controller is None or self._utility_operation_adapter is not None:
            page.set_error(cast(Any, self).tr("Another operation is in progress. Refresh when it finishes."))
            return False

        def operation() -> Any:
            prepared = controller.confirm(ticket, confirmed=True, accept_no_rollback=accept_no_rollback)
            if prepared.status != "prepared":
                return prepared, activate_verified_tweak(controller, prepared)
            running = controller.run(prepared)
            outcome = controller.verify(running) if running.status == "verifying" else running
            followup = notify_verified_cursor_change(controller, outcome) if cursor_notification_parameters(outcome) else activate_verified_tweak(controller, outcome)
            return outcome, followup

        def completed(result: Any) -> None:
            outcome, activation = result
            page.set_outcome(tweak_id, target, outcome, restored=True)
            if activation.message != outcome.message:
                page.set_activation(tweak_id, activation.message)

        target = str(ticket.plan.policy_decision.facts["requested"])
        page.set_busy(True, cast(Any, self).tr("Restoring and verifying the previous value…"))
        adapter = self._new_utility_operation_adapter(
            phase="change", operation_name=cast(Any, self).tr("Restoring and verifying previous value")
        )
        page.set_pending(tweak_id, target)
        adapter.finished.connect(completed)
        adapter.failed.connect(lambda message: page.set_restore_error(tweak_id, str(message)))
        adapter.cancelled.connect(lambda: page.set_restore_error(tweak_id, cast(Any, self).tr("Restoration was cancelled. Refresh to see the current value.")))
        adapter.stopped.connect(lambda: self._start_tweak_inspection(page, tweak_id))
        return bool(adapter.start(operation))

    def _set_review_notice(self: Any, page: Any, kind: str, title: str, message: str) -> None:
        """Present shared reviewed-operation feedback on Health and Apps."""
        setter = getattr(page, "set_health_notice", None) or getattr(page, "set_notice", None)
        if callable(setter):
            setter(kind, title, message)
        else:
            self._set_utility_notice(page, kind, title, message)

    def _review_health_action(self: Any, page: Any, action_id: str, parameters: Any) -> bool:
        """Prepare one Health action before asking for explicit user approval."""
        from core.actions.catalog import ActionCatalog
        from core.actions.operation_controller import OperationController

        definition = ActionCatalog().get(str(action_id))
        if definition is None or definition.operation_class == "manual_only":
            guidance = getattr(definition, "recovery_guidance", "") if definition is not None else ""
            self._set_review_notice(page, "warning", self.tr("Manual step"), guidance or self.tr("This repair needs manual guidance; no change was started."))
            return False
        if self._utility_operation_adapter is not None:
            self._set_review_notice(page, "warning", self.tr("Operation in progress"), self.tr("Wait for the current operation to finish."))
            return False
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        controller = self._utility_operation_controller
        self._set_review_notice(page, "info", self.tr("Checking"), self.tr("Preparing the exact scope of this change."))
        adapter = self._new_utility_operation_adapter(
            phase="review",
            operation_name=self.tr("Reviewing %1").replace("%1", definition.title),
        )
        adapter.finished.connect(lambda ticket: self._show_health_review(page, ticket, adapter))
        adapter.failed.connect(lambda message: self._set_review_notice(page, "error", self.tr("Unavailable"), str(message)))
        adapter.failed.connect(lambda _message: self._cancel_application_reviews(page))
        adapter.cancelled.connect(lambda: self._cancel_application_reviews(page))
        return bool(adapter.start(lambda: controller.prepare(str(action_id), dict(parameters or {}))))

    def _review_health_finding(self: Any, page: Any, action_id: str, context: Any) -> bool:
        """Resolve saved System Check evidence before showing a Health review."""
        from core.actions.operation_controller import OperationController, OperationTicket

        if self._utility_operation_adapter is not None:
            self._set_review_notice(page, "warning", self.tr("Operation in progress"), self.tr("Wait for the current operation to finish."))
            return False
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        controller = self._utility_operation_controller
        evidence = dict(context or {})
        self._set_review_notice(page, "info", self.tr("Checking"), self.tr("Rechecking the saved finding before review."))
        from core.actions.catalog import ActionCatalog

        definition = ActionCatalog().get(str(action_id))
        action_name = definition.title if definition is not None else str(action_id).replace("-", " ").title()
        adapter = self._new_utility_operation_adapter(
            phase="review", operation_name=self.tr("Rechecking %1").replace("%1", action_name)
        )
        adapter.finished.connect(lambda plan: self._show_health_review(page, OperationTicket(plan), adapter))
        adapter.failed.connect(lambda message: self._set_review_notice(page, "error", self.tr("Finding unavailable"), str(message)))
        return bool(adapter.start(lambda: controller.orchestrator.plan_from_finding(
            check_result_id=str(evidence.get("check_result_id", "")),
            finding_fingerprint=str(evidence.get("finding_fingerprint", "")),
            origin_route=str(evidence.get("origin_route", "")),
            expected_action_id=str(action_id),
        )))

    def _show_health_review(self: Any, page: Any, ticket: Any, adapter: Any) -> None:
        from PyQt6.QtWidgets import QDialog
        from core.actions.catalog import ActionCatalog
        from ui.confirm_dialog import ReviewedActionDialog

        if ticket.blocked:
            decision = ticket.plan.policy_decision
            self._set_review_notice(page, "warning", self.tr("Unavailable"), " ".join(part for part in (decision.explanation, decision.alternative) if part))
            self._cancel_application_reviews(page)
            return
        action_id = str(ticket.plan.action_id)
        definition = ActionCatalog().get(action_id)
        title = definition.title if definition is not None else action_id.replace("-", " ").title()
        description = definition.description if definition is not None else self.tr("Apply this exact change and verify its result?")
        scope = "\n".join(str(part) for part in ticket.preview)
        technical: tuple[str, ...] = ()
        facts = ticket.plan.policy_decision.facts
        if "rpm_transaction" in facts:
            from ui.rpm_transaction_review import rpm_review_lines
            scope, technical = rpm_review_lines(facts["rpm_transaction"], self.tr)
        elif "setup_source" in facts:
            from services.software.setup_sources import preview_from_facts
            source = preview_from_facts(facts["setup_source"])
            definition = source.to_dict()["definition"]
            source_lines = (definition["title"], self.tr("Provider: %1").replace("%1", definition["provider"]),
                            self.tr("Scope: %1").replace("%1", source.scope), definition["url"],
                            self.tr("Signing fingerprints: %1").replace("%1", ", ".join(definition["fingerprints"])))
            scope = "\n".join(source_lines)
        if action_id == "update-flatpaks":
            from ui.flatpak_updates import flatpak_review_lines
            summary, technical = flatpak_review_lines(ticket.plan, self.tr)
            if summary:
                scope = "\n".join(summary)
        elif "flatpak_installation" in facts:
            from services.software.flatpak_installation import preview_from_facts as flatpak_install_preview
            snapshot = flatpak_install_preview(facts["flatpak_installation"])
            lines = [self.tr("Flatpak installation: %1").replace("%1", snapshot.installation)]
            for item in snapshot.operations:
                lines.append(self.tr("%1: %2 — source %3 — commit %4").replace("%1", str(item["operation"]))
                             .replace("%2", item["ref"]).replace("%3", item["origin"]).replace("%4", item["expected_commit"]))
            scope = "\n".join(lines)
        dialog = ReviewedActionDialog(
            title,
            description,
            scope,
            str(ticket.plan.recovery_guidance),
            require_no_rollback_acceptance=(
                ticket.plan.risk_level in {"medium", "high"} and not ticket.plan.rollback_supported
            ),
            parent=self,
        )
        if technical:
            dialog.add_technical_details("\n".join(technical))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_review_notice(page, "neutral", self.tr("Cancelled"), self.tr("No change was made."))
            self._record_global_operation_result(None, self.tr("Review cancelled. No change was started."))
            self._cancel_application_reviews(page)
            return
        accept_no_rollback = dialog.accepts_no_rollback
        adapter.stopped.connect(lambda: self._run_reviewed_health_action(page, ticket, accept_no_rollback))

    def _run_reviewed_health_action(self: Any, page: Any, ticket: Any, accept_no_rollback: bool = False) -> bool:
        controller = self._utility_operation_controller
        if controller is None or self._utility_operation_adapter is not None:
            self._set_review_notice(page, "warning", self.tr("Operation in progress"), self.tr("Wait for the current operation to finish."))
            return False

        def operation() -> Any:
            prepared = controller.confirm(ticket, confirmed=True, accept_no_rollback=accept_no_rollback)
            if prepared.status != "prepared":
                return prepared
            running = controller.run(prepared)
            return controller.verify(running) if running.status == "verifying" else running

        self._set_review_notice(page, "info", self.tr("Running"), self.tr("The change is running and will be checked afterward."))
        from core.actions.catalog import ActionCatalog

        definition = ActionCatalog().get(str(ticket.plan.action_id))
        action_name = definition.title if definition is not None else str(ticket.plan.action_id).replace("-", " ").title()
        adapter = self._new_utility_operation_adapter(
            phase="change", operation_name=self.tr("Applying %1").replace("%1", action_name)
        )
        adapter.finished.connect(
            lambda outcome: self._set_review_notice(
                page,
                "success" if outcome.success else "warning",
                self.tr("Verified") if outcome.success else self.tr("Needs attention"),
                " ".join(part for part in (str(outcome.message), str(outcome.recovery_guidance) if not outcome.success else "") if part),
            )
        )
        if ticket.plan.action_id == "update-flatpaks":
            card = getattr(page, "flatpak_updates", None)
            if card is None:
                card = getattr(getattr(page, "installed_card", None), "updates", None)
            if card is not None:
                installation = ticket.plan.parameters.get("installation")
                adapter.finished.connect(lambda outcome, owner=card, scope=installation: owner.set_outcome(outcome, scope))
        adapter.failed.connect(lambda message: self._set_review_notice(page, "error", self.tr("Failed"), str(message)))
        adapter.failed.connect(lambda _message: self._cancel_application_reviews(page))
        adapter.cancelled.connect(lambda: self._cancel_application_reviews(page))
        refresh = getattr(page, "refresh_installed_applications", None)
        if callable(refresh):
            adapter.stopped.connect(refresh)
        if ticket.plan.action_id in {"enable-flathub", "enable-rpm-fusion", "refresh-application-metadata"}:
            refresh_sources = getattr(page, "refresh_flathub_status", None)
            if callable(refresh_sources):
                adapter.stopped.connect(refresh_sources)
            refresh_metadata = getattr(page, "refresh_application_metadata", None)
            if callable(refresh_metadata) and not getattr(getattr(page, "discovery_toggle", None), "isChecked", lambda: False)():
                adapter.stopped.connect(refresh_metadata)
        adapter.finished.connect(lambda outcome: self._application_item_finished(page, ticket, outcome))
        adapter.stopped.connect(lambda: self._continue_application_reviews(page))
        return bool(adapter.start(operation))

    def _utility_operation_adapter_stopped(self: Any, adapter: Any) -> None:
        """Release a worker adapter only after its QThread has finished."""
        if getattr(self, "_utility_operation_adapter", None) is adapter:
            self._utility_operation_adapter = None
        adapter.deleteLater()
        resume_shutdown = getattr(self, "_resume_deferred_runtime_shutdown", None)
        if callable(resume_shutdown):
            resume_shutdown()

    def _set_utility_notice(self: Any, page: QWidget, kind: str, title: str, message: str) -> None:
        """Set a local workflow notice without coupling pages to the shell."""
        notice = getattr(page, "state_notice", None)
        setter = getattr(notice, "set_notice", None)
        if callable(setter):
            setter(kind, title, message)

    def _handle_update_source_action(self: Any, page: QWidget, source: str, action: str) -> None:
        """Run one compact Update-card action through the shared controller."""
        source = str(source)
        action = str(action)
        if action == "recovery":
            source_state = getattr(page, "source_state", lambda _source: None)(source)
            self._last_operation_run_id = str(getattr(source_state, "run_id", "") or "")
            self._open_activity_status_result()
            return
        if action == "check":
            start_check = getattr(page, "start_check", None)
            if callable(start_check) and start_check(source):
                return
            setter = getattr(page, "set_notice", None)
            if callable(setter):
                setter("warning", "Check unavailable", "Wait for the current source check to finish.")
            return
        if action not in {"update", "continue", "verify"}:
            return
        source_state = getattr(page, "source_state", lambda _source: None)(source)
        run_id = str(getattr(source_state, "run_id", "") or "")
        if action in {"continue", "verify"} and not run_id:
            setter = getattr(page, "set_notice", None)
            if callable(setter):
                setter("warning", "Verification unavailable", "No saved run is available for this source.")
            return

        if action in {"continue", "verify"}:
            # Continue is the post-reboot verification hand-off.  It must not
            # re-run the update action or create a second transaction.
            self._start_utility_update(page, source, "verify", run_id=run_id)
            return

        if action == "update":
            from PyQt6.QtWidgets import QMessageBox

            item_count = int(getattr(source_state, "item_count", 0) or 0)
            detail = str(getattr(source_state, "message", "") or f"{item_count} update(s) are ready.")
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setWindowTitle(self.tr("Review update"))
            dialog.setText(self.tr("Review the %1 source before applying changes.").replace("%1", source.title()))
            dialog.setInformativeText(
                self.tr("%1 Nothing will reboot automatically.").replace("%1", detail)
            )
            dialog.setStandardButtons(
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok
            )
            apply_button = dialog.button(QMessageBox.StandardButton.Ok)
            if apply_button is not None:
                apply_button.setText(self.tr("Apply %1 updates").replace("%1", str(item_count)))
            candidates = tuple(getattr(source_state, "details", ()))
            if candidates:
                dialog.setDetailedText("\n".join(candidates))
            detail_parts = [detail, self.tr("Nothing will reboot automatically.")]
            checked_at = str(getattr(cast(Any, source_state), "checked_at", "") or "")
            if checked_at:
                detail_parts.append(self.tr("Observed at %1.").replace("%1", checked_at))
            detail_parts.append(self.tr("The update transaction may differ from this earlier check."))
            dialog.setInformativeText("\n".join(detail_parts))
            dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
            dialog.setEscapeButton(QMessageBox.StandardButton.Cancel)
            if dialog.exec() != QMessageBox.StandardButton.Ok:
                setter = getattr(page, "set_notice", None)
                if callable(setter):
                    setter("neutral", "Review cancelled", "No changes were made.")
                return

        self._start_utility_update(page, source, "update", run_id=run_id)

    def _start_utility_update(
        self: Any,
        page: QWidget,
        source: str,
        action: str,
        *,
        run_id: str = "",
    ) -> bool:
        """Execute or verify one source with the shared Qt adapter."""
        from core.actions.operation_controller import OperationController

        adapter = getattr(self, "_utility_operation_adapter", None)
        if adapter is not None:
            setter = getattr(page, "set_notice", None)
            if callable(setter):
                setter("warning", "Operation in progress", "Wait for the current operation to finish.")
            return False
        controller = getattr(self, "_utility_operation_controller", None)
        if controller is None:
            controller = OperationController()
            self._utility_operation_controller = controller
        action_ids = {
            "system": "update-fedora-system",
            "flatpak": "update-flatpaks",
            "firmware": "update-firmware",
        }
        action_id = action_ids.get(str(source))
        if not action_id and action != "verify":
            return False
        page_any = cast(Any, page)
        set_source = getattr(page, "set_source", None)
        if callable(set_source) and action != "verify":
            current = page_any.source_state(source)
            set_source(
                current.with_status(
                    "preparing",
                    stale=False,
                    message=self.tr("Preparing the reviewed update scope."),
                )
            )
        setter = getattr(page, "set_notice", None)
        if callable(setter):
            setter("info", "Preparing", "The source is being preflighted before execution.")
        source_name = str(source).replace("_", " ").title()
        operation_name = self.tr("Verifying %1 updates").replace("%1", source_name) if action == "verify" else self.tr("Applying %1 updates").replace("%1", source_name)
        new_adapter = self._new_utility_operation_adapter(
            phase="verification" if action == "verify" else "change",
            operation_name=operation_name,
        )
        new_adapter.started.connect(
            lambda: setter("info", "Running", "The reviewed source operation is running and will be verified.")
            if callable(setter)
            else None
        )
        new_adapter.finished.connect(
            lambda outcome: self._utility_update_finished(page, source, outcome)
        )
        new_adapter.failed.connect(
            lambda message: self._utility_update_failed(page, source, str(message), run_id=run_id)
        )
        new_adapter.cancelled.connect(
            lambda: self._utility_update_failed(
                page, source, "The update operation was cancelled before completion.", run_id=run_id
            )
        )
        if action == "verify":
            def operation() -> Any:
                return controller.verify(run_id)
        else:
            resolved_action_id = str(action_id or "")

            def operation() -> Any:
                return controller.execute(
                    resolved_action_id,
                    {},
                    confirmed=True,
                    accept_no_rollback=True,
                )
        started = new_adapter.start(operation)
        if not started:
            self._utility_operation_adapter = None
            new_adapter.deleteLater()
            if callable(setter):
                setter("warning", "Operation in progress", "Wait for the current operation to finish.")
        return bool(started)

    def _utility_update_finished(self: Any, page: QWidget, source: str, outcome: Any) -> None:
        """Render one update outcome without leaving the Update page."""
        run_id = str(getattr(outcome, "run_id", "") or "")
        if run_id:
            self._last_operation_run_id = run_id
        apply_outcome = getattr(page, "apply_outcome", None)
        if callable(apply_outcome):
            apply_outcome(source, outcome)

    def _utility_update_failed(self: Any, page: QWidget, source: str, message: str, *, run_id: str = "") -> None:
        """Keep failed update state visible and never retry automatically."""
        if run_id:
            self._last_operation_run_id = str(run_id)
        apply_outcome = getattr(page, "apply_outcome", None)
        if callable(apply_outcome):
            from types import SimpleNamespace

            apply_outcome(source, SimpleNamespace(status="failed", message=message, run_id=str(run_id)))

    def _cancel_utility_operation(self: Any) -> bool:
        """Cooperatively cancel a running utility operation during shutdown."""
        adapter = getattr(self, "_utility_operation_adapter", None)
        cancel = getattr(adapter, "cancel", None)
        return bool(cancel()) if callable(cancel) else False

    def _utility_destination_for_route(self: Any, route_id: str) -> str:
        """Map canonical deep links to one of the five visible utility jobs."""
        if not getattr(self, "_utility_shell_ready", False):
            return ""
        utility_routes = getattr(self, "_utility_route_objects", {})
        route = resolve(str(route_id))
        normalized_id = str(route_id)
        if normalized_id in utility_routes:
            return normalized_id.removeprefix("utility:")
        if route is None:
            return ""
        if route.plugin_id in {"overview", "activity"}:
            return route.plugin_id
        if route.plugin_id == "settings":
            return ""

        advanced = advanced_shell_route_for(route.id)
        if advanced is not None:
            return advanced.id
        placement = placement_for_route(route.id)
        destination_id = placement.destination_id if placement is not None else ""
        if destination_id == "home" or route.plugin_id == "atlas_dashboard":
            return ""
        if destination_id == "software_updates" or route.plugin_id == "software":
            if route.id.startswith("maintenance"):
                return "update"
            return "install"
        if destination_id == "system" or route.plugin_id in {
            "system_info",
            "monitor",
            "hardware",
            "storage",
            "snapshots",
        }:
            return "fix" if route.plugin_id == "diagnostics" else "tune"
        if destination_id == "network_security" or route.plugin_id in {
            "network",
            "security",
            "backup",
        }:
            return "fix"
        return ""

    def _advanced_tools_enabled(self: Any) -> bool:
        """Return whether the user chose to show advanced tools."""
        if hasattr(self, "_advanced_tools_override"):
            return bool(self._advanced_tools_override)
        from utils.settings import SettingsManager

        try:
            return bool(SettingsManager.instance().get("show_advanced_tools"))
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return False

    def _visible_shell_destinations(self: Any) -> tuple[Any, ...]:
        """Return the sidebar rows for the current simple/advanced mode."""
        return visible_shell_routes(self._advanced_tools_enabled())

    def apply_advanced_tools(self: Any, enabled: bool) -> None:
        """Show or hide the advanced sidebar rows without rebuilding pages."""
        self._advanced_tools_override = bool(enabled)
        from utils.settings import SettingsManager

        try:
            SettingsManager.instance().set("show_advanced_tools", bool(enabled))
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            pass
        active = self._active_route_id
        self.sidebar.set_utility_destinations(visible_shell_routes(bool(enabled)))
        self._active_destination_id = ""
        if active:
            self._sync_destination_shell(active)

    def _remember_tools_expansion(self: Any, enabled: bool) -> None:
        """Persist an explicit Tools disclosure without rebuilding its items."""
        from utils.settings import SettingsManager
        settings = getattr(self, "_navigation_settings", None) or SettingsManager.instance()
        previous = bool(settings.get("show_advanced_tools"))
        settings.set("show_advanced_tools", bool(enabled))
        if not settings.save():
            settings.set("show_advanced_tools", previous)
            self.apply_advanced_tools(previous)
            self._status_label.setText(self.tr("Could not save the Tools preference. The previous view has been restored."))
            self._status_frame.show()
            return
        self._advanced_tools_override = bool(enabled)

    def _remember_active_route(self: Any, route_id: str) -> None:
        """Store successful navigation through the existing settings contract."""
        from utils.settings import SettingsManager
        settings = getattr(self, "_navigation_settings", None) or SettingsManager.instance()
        previous = settings.get("last_route_id")
        if previous == route_id:
            return
        settings.set("last_route_id", route_id)
        if not settings.save():
            settings.set("last_route_id", previous)
            self._status_label.setText(self.tr("Could not save the last page. Your previous startup preference is unchanged."))
            self._status_frame.show()

    def _utility_default_route(self: Any, destination_id: str) -> str:
        """Return the stable landing route for a visible utility destination."""
        destination = next(
            (
                item
                for item in getattr(self, "_utility_destinations", ())
                if item.id == str(destination_id)
            ),
            None,
        )
        return destination.default_route_id if destination is not None else ""

    def _activate_destination(self: Any, destination_id: str) -> None:
        """Open a destination's policy-approved default route."""
        if getattr(self, "_selecting_destination", False):
            return
        utility_default = self._utility_default_route(destination_id)
        if utility_default:
            self.switch_to_route(utility_default)
            return
        destination = get_destination(destination_id)
        if destination is None:
            return
        self.switch_to_route(destination.default_route_id)

    def _resolve_shell_route(self: Any, route_id: str) -> NavigationRoute | None:
        """Resolve v29 landing aliases without changing the core manifest."""
        key = str(route_id or "").strip()
        alias = _UTILITY_ROUTE_ALIASES.get(key.casefold())
        if alias is not None:
            key = alias
        utility_routes = getattr(self, "_utility_route_objects", {})
        if key in utility_routes:
            return cast(NavigationRoute, utility_routes[key])
        return cast(NavigationRoute | None, resolve(key))

    def _switch_to_utility_route(
        self: Any,
        route: NavigationRoute,
        *,
        record_history: bool,
    ) -> bool:
        """Display one synthetic landing page from the v29 presentation layer."""
        entry = self._sidebar_index.get(route.plugin_id)
        if entry is None or entry.content_widget is None:
            return False
        self.content_area.setCurrentWidget(entry.content_widget)
        self._active_route_id = route.id
        self._active_destination_id = route.id.removeprefix("utility:")
        self._set_active_plugin(route.plugin_id)
        self._sync_destination_shell(route.id)
        self._sync_page_header_actions(route)
        self._update_header_for_route(route, entry)
        if record_history:
            self._record_route_history(route.id)
        remember = getattr(self, "_remember_active_route", None)
        if callable(remember):
            remember(route.id)
        return True

    def _switch_to_internal_action_route(self: Any, *, record_history: bool = True) -> bool:
        """Open the legacy action editor only for an internal workflow handoff."""
        self._internal_action_route_navigation = True
        try:
            return bool(
                self.switch_to_route(
                    "maintenance:action-center",
                    record_history=record_history,
                )
            )
        finally:
            self._internal_action_route_navigation = False

    def switch_to_route(self: Any, route_id: str, *, record_history: bool = True) -> bool:
        """Switch through policy to a canonical route ID or compatibility alias."""
        requested_route_id = str(route_id or "").strip()
        if (
            requested_route_id.casefold() in _ACTIVITY_COMPATIBILITY_ROUTES
            and not getattr(self, "_internal_action_route_navigation", False)
            and "activity" in self._sidebar_index
        ):
            requested_route_id = "activity"

        route = self._resolve_shell_route(requested_route_id)
        if not route:
            return False

        utility_routes = getattr(self, "_utility_route_objects", {})
        if route.id in utility_routes:
            return bool(
                self._switch_to_utility_route(
                    route,
                    record_history=record_history,
                )
            )

        if getattr(self, "_shell_uses_destinations", False) is True:
            result = NavigationPolicy.evaluate(route.id, self._navigation_context)
            if result.direct_link_behavior is DirectLinkBehavior.REDIRECT and result.redirect_route_id:
                return bool(
                    self.switch_to_route(
                        result.redirect_route_id,
                        record_history=record_history,
                    )
                )
            if result.decision is not NavigationDecision.VISIBLE:
                self._sync_page_header_actions(None)
                destination = get_destination(result.destination_id)
                if destination is not None:
                    self._selecting_destination = True
                    self.sidebar.select_destination(destination.id)
                    self._selecting_destination = False
                self.destination_host.show_policy_result(result)
                return False

        entry = self._sidebar_index.get(route.plugin_id)
        if not entry:
            return False

        if entry.tree_item is not None:
            self.sidebar.setCurrentItem(entry.tree_item)
        elif entry.content_widget is not None:
            self.content_area.setCurrentWidget(entry.content_widget)
        if getattr(self, "_shell_uses_destinations", False) is True:
            self._sync_destination_shell(route.id)
        self._active_route_id = route.id
        self._set_active_plugin(route.plugin_id)
        activated = self._activate_route_widget(route)
        self._sync_page_header_actions(route)
        if entry.tree_item is not None:
            self._update_breadcrumb(entry.tree_item)
        else:
            self._update_header_for_route(route, entry)
        if not activated:
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.debug(
                    "switch_to_route: plugin selected but subroute did not activate: %s",
                    route.id,
                )
        if record_history:
            self._record_route_history(route.id)
        remember = getattr(self, "_remember_active_route", None)
        if callable(remember):
            remember(route.id)
        return True
