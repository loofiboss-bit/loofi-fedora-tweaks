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
from core.plugins.metadata import PluginMetadata
from PyQt6.QtWidgets import QTreeWidgetItem, QWidget


_UTILITY_ROUTE_ALIASES = {
    "home": "atlas_dashboard",
    "install": "utility:install",
    "apps": "utility:install",
    "tune": "utility:tune",
    "tweaks": "utility:tune",
    "fix": "utility:fix",
    "health": "utility:fix",
    "update": "utility:update",
    "updates": "utility:update",
}

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


class MainWindowUtilityMixin:
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

    def _register_utility_landing_pages(self: Any) -> None:
        """Register lightweight placeholders for the four workflow pages."""
        from ui.lazy_widget import LazyWidget
        from ui.navigation import UTILITY_DESTINATIONS

        self._utility_destinations = tuple(UTILITY_DESTINATIONS)
        destination_by_id = {
            destination.id: destination
            for destination in self._utility_destinations
        }
        for destination_id in ("install", "tune", "fix", "update"):
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
                order={"install": 10, "tune": 20, "fix": 30, "update": 40}[destination_id],
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

            install_page: Any = InstallWorkflowPage(context=application_context)
            install_page.bundleReviewRequested.connect(
                lambda selection, owner=install_page: self._review_utility_bundle(owner, selection)
            )
            install_page.routeRequested.connect(self._open_route_request)
            return cast(QWidget, install_page)
        if destination_id == "tune":
            from ui.tweaks_page import TweaksPage

            tweaks_page: Any = TweaksPage(self._platform_profile)
            tweaks_page.refreshRequested.connect(
                lambda owner=tweaks_page: self._start_tweak_snapshot(owner)
            )
            tweaks_page.changeRequested.connect(
                lambda tweak_id, value, owner=tweaks_page: self._start_tweak_change(owner, tweak_id, value)
            )
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
            return cast(QWidget, update_page)
        raise ValueError(f"Unknown utility workflow destination: {destination_id}")

    def _new_utility_operation_adapter(self: Any) -> Any:
        """Create the single window-owned worker adapter for a reviewed change."""
        from ui.operation_worker import OperationControllerQtAdapter

        adapter = OperationControllerQtAdapter(parent=self)
        adapter.stopped.connect(
            lambda selected=adapter: self._utility_operation_adapter_stopped(selected)
        )
        self._utility_operation_adapter = adapter
        return adapter

    def _start_tweak_snapshot(self: Any, page: Any) -> bool:
        """Read current settings on the window-owned worker, without UI blocking."""
        if self._utility_operation_adapter is not None:
            page.set_error(self.tr("Another operation is in progress. Refresh when it finishes."))
            return False
        from core.actions.catalog import SystemActionRuntime
        from core.executor.command_facade import CommandFacade
        from core.tasks.tweaks import snapshot

        page.set_busy(True, self.tr("Reading current settings…"))
        adapter = self._new_utility_operation_adapter()
        adapter.finished.connect(page.set_states)
        adapter.failed.connect(page.set_error)
        adapter.cancelled.connect(lambda: page.set_error(self.tr("Reading was cancelled.")))
        return bool(adapter.start(lambda: snapshot(page.profile, SystemActionRuntime(CommandFacade()))))

    def _start_tweak_change(self: Any, page: Any, tweak_id: str, value: str) -> bool:
        """Apply one typed setting through the durable operation controller."""
        from core.actions.operation_controller import OperationController
        from core.tasks.tweaks import BY_ID
        from PyQt6.QtWidgets import QMessageBox

        tweak = BY_ID.get(str(tweak_id))
        if tweak is None or self._utility_operation_adapter is not None:
            page.restore_selection(tweak_id)
            page.set_error(self.tr("Another operation is in progress. Try again when it finishes."))
            return False
        if tweak.system_wide:
            answer = QMessageBox.question(
                self,
                self.tr("Change power profile"),
                self.tr("Apply the selected power profile to this computer?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                page.restore_selection(tweak_id)
                return False
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        controller = self._utility_operation_controller
        page.set_busy(True, self.tr("Applying and verifying %1…").replace("%1", self.tr(tweak.title)))
        adapter = self._new_utility_operation_adapter()
        adapter.finished.connect(lambda outcome: page.set_outcome(tweak_id, value, outcome))
        adapter.failed.connect(lambda message: page.set_error(str(message)))
        adapter.cancelled.connect(lambda: page.set_error(self.tr("The operation was cancelled. Refresh to see the current value.")))
        adapter.stopped.connect(lambda: self._start_tweak_snapshot(page))
        return bool(adapter.start(lambda: controller.execute(tweak.action_id, {"value": value}, confirmed=True)))

    def _review_health_action(self: Any, page: Any, action_id: str, parameters: Any) -> bool:
        """Prepare one Health action before asking for explicit user approval."""
        from core.actions.catalog import ActionCatalog
        from core.actions.operation_controller import OperationController

        definition = ActionCatalog().get(str(action_id))
        if definition is None or definition.operation_class == "manual_only":
            guidance = getattr(definition, "recovery_guidance", "") if definition is not None else ""
            page.set_health_notice("warning", self.tr("Manual step"), guidance or self.tr("This repair needs manual guidance; no change was started."))
            return False
        if self._utility_operation_adapter is not None:
            page.set_health_notice("warning", self.tr("Operation in progress"), self.tr("Wait for the current operation to finish."))
            return False
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        controller = self._utility_operation_controller
        page.set_health_notice("info", self.tr("Checking"), self.tr("Preparing the exact scope of this change."))
        adapter = self._new_utility_operation_adapter()
        adapter.finished.connect(lambda ticket: self._show_health_review(page, ticket, adapter))
        adapter.failed.connect(lambda message: page.set_health_notice("error", self.tr("Unavailable"), str(message)))
        return bool(adapter.start(lambda: controller.prepare(str(action_id), dict(parameters or {}))))

    def _review_health_finding(self: Any, page: Any, action_id: str, context: Any) -> bool:
        """Resolve saved System Check evidence before showing a Health review."""
        from core.actions.operation_controller import OperationController, OperationTicket

        if self._utility_operation_adapter is not None:
            page.set_health_notice("warning", self.tr("Operation in progress"), self.tr("Wait for the current operation to finish."))
            return False
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        controller = self._utility_operation_controller
        evidence = dict(context or {})
        page.set_health_notice("info", self.tr("Checking"), self.tr("Rechecking the saved finding before review."))
        adapter = self._new_utility_operation_adapter()
        adapter.finished.connect(lambda plan: self._show_health_review(page, OperationTicket(plan), adapter))
        adapter.failed.connect(lambda message: page.set_health_notice("error", self.tr("Finding unavailable"), str(message)))
        return bool(adapter.start(lambda: controller.orchestrator.plan_from_finding(
            check_result_id=str(evidence.get("check_result_id", "")),
            finding_fingerprint=str(evidence.get("finding_fingerprint", "")),
            origin_route=str(evidence.get("origin_route", "")),
            expected_action_id=str(action_id),
        )))

    def _show_health_review(self: Any, page: Any, ticket: Any, adapter: Any) -> None:
        from PyQt6.QtWidgets import QMessageBox

        if ticket.blocked:
            decision = ticket.plan.policy_decision
            page.set_health_notice("warning", self.tr("Unavailable"), " ".join(part for part in (decision.explanation, decision.alternative) if part))
            return
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(self.tr("Review change"))
        dialog.setText(str(ticket.plan.action_id).replace("-", " ").title())
        dialog.setInformativeText(self.tr("Apply this exact change and verify its result?"))
        dialog.setDetailedText("\n".join([*ticket.preview, ticket.plan.recovery_guidance]))
        dialog.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok)
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if dialog.exec() != QMessageBox.StandardButton.Ok:
            page.set_health_notice("neutral", self.tr("Cancelled"), self.tr("No change was made."))
            return
        adapter.stopped.connect(lambda: self._run_reviewed_health_action(page, ticket))

    def _run_reviewed_health_action(self: Any, page: Any, ticket: Any) -> bool:
        controller = self._utility_operation_controller
        if controller is None or self._utility_operation_adapter is not None:
            page.set_health_notice("warning", self.tr("Operation in progress"), self.tr("Wait for the current operation to finish."))
            return False

        def operation() -> Any:
            prepared = controller.confirm(ticket, confirmed=True, accept_no_rollback=True)
            if prepared.status != "prepared":
                return prepared
            running = controller.run(prepared)
            return controller.verify(running) if running.status == "verifying" else running

        page.set_health_notice("info", self.tr("Running"), self.tr("The change is running and will be checked afterward."))
        adapter = self._new_utility_operation_adapter()
        adapter.finished.connect(
            lambda outcome: page.set_health_notice(
                "success" if outcome.success else "warning",
                self.tr("Verified") if outcome.success else self.tr("Needs attention"),
                " ".join(part for part in (str(outcome.message), str(outcome.recovery_guidance) if not outcome.success else "") if part),
            )
        )
        adapter.failed.connect(lambda message: page.set_health_notice("error", self.tr("Failed"), str(message)))
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

    def _review_utility_bundle(self: Any, page: QWidget, selection: Any) -> bool:
        """Ask for one explicit bundle confirmation, then start the adapter."""
        bundle = getattr(selection, "bundle", None)
        if bundle is None:
            self._set_utility_notice(page, "error", "Review unavailable", "The selected change set is malformed.")
            return False
        adapter = getattr(self, "_utility_operation_adapter", None)
        if adapter is not None:
            self._set_utility_notice(page, "warning", "Operation in progress", "Wait for the current operation to finish before starting another one.")
            return False

        lines: list[str] = []
        for item in getattr(bundle, "items", ()):
            title = str(getattr(item, "title", "") or getattr(item, "action_id", "Operation"))
            parameters = getattr(item, "parameters", {})
            source = str(parameters.get("source", "")) if isinstance(parameters, dict) else ""
            package_id = str(parameters.get("package_id", "")) if isinstance(parameters, dict) else ""
            if source and package_id:
                lines.append(f"{title} — {source}: {package_id}")
            else:
                lines.append(title)
        detail_text = "\n".join(lines) or "No operations selected."

        from PyQt6.QtWidgets import QMessageBox

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle(self.tr("Review selected changes"))
        dialog.setText(str(getattr(bundle, "title", "Review selected changes")))
        dialog.setInformativeText(
            self.tr("Review the exact scope below. Nothing changes until you confirm.")
        )
        dialog.setDetailedText(detail_text)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.Ok)
        if dialog.exec() != QMessageBox.StandardButton.Ok:
            self._set_utility_notice(page, "neutral", "Review cancelled", "No changes were made.")
            return False
        return bool(self._start_utility_bundle(page, selection))

    def _start_utility_bundle(self: Any, page: QWidget, selection: Any) -> bool:
        """Run a confirmed bundle through the shared Qt operation adapter."""
        from core.actions.operation_controller import OperationController

        if self._utility_operation_adapter is not None:
            self._set_utility_notice(page, "warning", "Operation in progress", "Wait for the current operation to finish before starting another one.")
            return False
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        adapter = self._new_utility_operation_adapter()
        self._set_utility_notice(page, "info", "Running", "The reviewed operations are running and will be verified individually.")
        adapter.started.connect(
            lambda: self._set_utility_notice(page, "info", "Running", "The reviewed operations are running and will be verified individually.")
        )
        adapter.finished.connect(
            lambda outcome: self._utility_bundle_finished(page, outcome)
        )
        adapter.failed.connect(
            lambda message: self._set_utility_notice(page, "error", "Operation failed", str(message))
        )
        adapter.cancelled.connect(
            lambda: self._set_utility_notice(page, "warning", "Operation cancelled", "No retry or rollback was started.")
        )
        started = adapter.start(
            lambda: self._utility_operation_controller.execute_bundle(
                selection.bundle,
                confirmed=True,
                accept_no_rollback=True,
            )
        )
        if not started:
            self._utility_operation_adapter = None
            adapter.deleteLater()
            self._set_utility_notice(page, "warning", "Operation in progress", "Wait for the current operation to finish before starting another one.")
        return bool(started)

    def _utility_bundle_finished(self: Any, page: QWidget, outcome: Any) -> None:
        """Project a terminal bundle outcome back onto its owning workflow."""
        setter = getattr(page, "set_results", None)
        if callable(setter):
            setter(outcome)
        status = str(getattr(outcome, "status", "completed")).replace("_", " ").title()
        message = str(getattr(outcome, "message", "The reviewed operations finished."))
        self._set_utility_notice(page, "success" if status == "Succeeded" else "warning", status, message)

    def _handle_update_source_action(self: Any, page: QWidget, source: str, action: str) -> None:
        """Run one compact Update-card action through the shared controller."""
        source = str(source)
        action = str(action)
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
            dialog.setDefaultButton(QMessageBox.StandardButton.Ok)
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
        new_adapter = self._new_utility_operation_adapter()
        new_adapter.started.connect(
            lambda: setter("info", "Running", "The reviewed source operation is running and will be verified.")
            if callable(setter)
            else None
        )
        new_adapter.finished.connect(
            lambda outcome: self._utility_update_finished(page, source, outcome)
        )
        new_adapter.failed.connect(
            lambda message: self._utility_update_failed(page, source, str(message))
        )
        new_adapter.cancelled.connect(
            lambda: self._utility_update_failed(page, source, "The update operation was cancelled before completion.")
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
        apply_outcome = getattr(page, "apply_outcome", None)
        if callable(apply_outcome):
            apply_outcome(source, outcome)

    def _utility_update_failed(self: Any, page: QWidget, source: str, message: str) -> None:
        """Keep failed update state visible and never retry automatically."""
        apply_outcome = getattr(page, "apply_outcome", None)
        if callable(apply_outcome):
            from types import SimpleNamespace

            apply_outcome(source, SimpleNamespace(status="failed", message=message))

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
        if route.id in {"activity", "settings"} or route.plugin_id in {
            "activity",
            "settings",
        }:
            return ""

        placement = placement_for_route(route.id)
        destination_id = placement.destination_id if placement is not None else ""
        if destination_id == "home" or route.plugin_id == "atlas_dashboard":
            return "home"
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
        return True
