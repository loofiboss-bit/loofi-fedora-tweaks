"""Explicit review and execution handoff for selected catalog applications."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PyQt6.QtWidgets import QWidget


class ApplicationReviewMixin:
    """Review exact package identities and hand accepted bundles to Action Center."""

    _utility_operation_controller: Any | None
    _utility_operation_adapter: Any | None

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
        variant = str(getattr(bundle, "metadata", {}).get("variant", "traditional"))
        for item in getattr(bundle, "items", ()):
            title = str(getattr(item, "title", "") or getattr(item, "action_id", "Operation"))
            parameters = getattr(item, "parameters", {})
            metadata = getattr(item, "metadata", {})
            source = str(parameters.get("source", "")) if isinstance(parameters, Mapping) else ""
            package_id = str(parameters.get("package_id", "")) if isinstance(parameters, Mapping) else ""
            if source == "flatpak":
                installation = str(parameters.get("installation", "system"))
                scope = self.tr("Flatpak installation: %1").replace("%1", installation) if "installation" in parameters else self.tr("System Flatpak installation")
                source_label = str(metadata.get("source_label", "") or self.tr("Flathub")) if isinstance(metadata, Mapping) else self.tr("Flathub")
            elif variant in {"silverblue", "kinoite", "atomic"}:
                scope = self.tr("System deployment via RPM-OSTree")
                source_label = str(metadata.get("source_label", "") or self.tr("Fedora packages")) if isinstance(metadata, Mapping) else self.tr("Fedora packages")
            else:
                scope = self.tr("System package installation via DNF5")
                source_label = str(metadata.get("source_label", "") or self.tr("Fedora packages")) if isinstance(metadata, Mapping) else self.tr("Fedora packages")
            lines.append("\n".join((
                title,
                self.tr("Source: %1").replace("%1", source_label),
                self.tr("Package identifier: %1").replace("%1", package_id or self.tr("Unavailable")),
                self.tr("Installation scope: %1").replace("%1", scope),
            )))
        from PyQt6.QtWidgets import QDialog
        from ui.confirm_dialog import ReviewedActionDialog

        item_count = len(getattr(bundle, "items", ()))
        dialog = ReviewedActionDialog(
            str(getattr(bundle, "title", "Review selected applications")),
            str(getattr(bundle, "description", "Review the exact selected applications before installing.")),
            "\n\n".join(lines) or self.tr("No applications are selected."),
            self.tr("Review installed applications to confirm the result. Remove an application through its package manager if you want to uninstall it."),
            parent=self,
        )
        dialog.setWindowTitle(self.tr("Review selected applications"))
        accept_button = dialog.accept_button
        if accept_button is not None:
            accept_button.setText(self.tr("Review %1 transactions").replace("%1", str(item_count)) if str(getattr(bundle, "kind", "")) == "application_install" else self.tr("Apply %1 changes").replace("%1", str(item_count)))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_utility_notice(page, "neutral", "Review cancelled", "No changes were made.")
            return False
        return bool(self._start_utility_bundle(page, selection))

    def _start_utility_bundle(self: Any, page: QWidget, selection: Any) -> bool:
        """Prepare and review every application transaction before execution."""
        if str(getattr(selection.bundle, "kind", "")) == "application_install":
            if self._utility_operation_adapter is not None:
                self._set_utility_notice(page, "warning", "Operation in progress", "Wait for the current operation to finish.")
                return False
            try:
                selection.bundle.assert_valid()
            except (AttributeError, TypeError, ValueError):
                self._set_utility_notice(page, "error", "Review unavailable", "The selected application bundle is invalid.")
                return False
            self._application_review_state = {"page": page, "bundle": selection.bundle, "remaining": list(selection.bundle.items), "results": [], "current": None}
            return bool(self._continue_application_reviews(page))
        return bool(self._start_legacy_utility_bundle(page, selection))

    def _start_legacy_utility_bundle(self: Any, page: QWidget, selection: Any) -> bool:
        """Retain the established non-application profile workflow."""
        from core.actions.operation_controller import OperationController

        if self._utility_operation_adapter is not None:
            self._set_utility_notice(page, "warning", "Operation in progress", "Wait for the current operation to finish before starting another one.")
            return False
        if self._utility_operation_controller is None:
            self._utility_operation_controller = OperationController()
        adapter = self._new_utility_operation_adapter(
            phase="change", operation_name=self.tr("Installing selected applications")
        )
        self._set_utility_notice(page, "info", "Running", "The reviewed operations are running and will be verified individually.")
        adapter.started.connect(lambda: self._set_utility_notice(
            page, "info", "Running", "The reviewed operations are running and will be verified individually."
        ))
        adapter.finished.connect(lambda outcome: self._utility_bundle_finished(page, outcome))
        adapter.failed.connect(lambda message: self._set_utility_notice(page, "error", "Operation failed", str(message)))
        adapter.cancelled.connect(lambda: self._set_utility_notice(
            page, "warning", "Operation cancelled", "No retry or rollback was started."
        ))
        started = adapter.start(lambda: self._utility_operation_controller.execute_bundle(
            selection.bundle, confirmed=True, accept_no_rollback=True
        ))
        if not started:
            self._utility_operation_adapter = None
            adapter.deleteLater()
            self._set_utility_notice(page, "warning", "Operation in progress", "Wait for the current operation to finish before starting another one.")
        return bool(started)

    def _continue_application_reviews(self: Any, page: QWidget) -> bool:
        state = getattr(self, "_application_review_state", None)
        if not state or state["page"] is not page or state["current"] is not None:
            return False
        if not state["remaining"]:
            return bool(self._finish_application_reviews(page))
        item = state["remaining"].pop(0)
        state["current"] = item
        started = self._review_health_action(page, item.action_id, dict(item.parameters))
        if not started:
            self._cancel_application_reviews(page)
        return bool(started)

    def _application_item_finished(self: Any, page: QWidget, ticket: Any, outcome: Any) -> None:
        from core.actions.bundles import BundleItemResult

        state = getattr(self, "_application_review_state", None)
        if not state or state["page"] is not page:
            return
        item = state["current"]
        if item is None or item.action_id != ticket.plan.action_id or any(ticket.plan.parameters.get(key) != value for key, value in item.parameters.items()):
            return
        state["results"].append(BundleItemResult(
            item_id=item.item_id, action_id=item.action_id, status=str(outcome.status), message=str(outcome.message),
            plan_id=str(outcome.plan_id), run_id=str(outcome.run_id), correlation_id=str(outcome.correlation_id), data=dict(outcome.data),
        ))
        state["current"] = None

    def _cancel_application_reviews(self: Any, page: QWidget) -> None:
        from core.actions.bundles import BundleItemResult

        state = getattr(self, "_application_review_state", None)
        if not state or state["page"] is not page:
            return
        pending = ([state["current"]] if state["current"] is not None else []) + state["remaining"]
        for item in pending:
            state["results"].append(BundleItemResult(item.item_id, item.action_id, "skipped", "No approved transaction was executed.", skipped=True))
        state["remaining"] = []
        state["current"] = None
        self._finish_application_reviews(page)

    def _finish_application_reviews(self: Any, page: QWidget) -> bool:
        from core.actions.bundles import BundleOutcome

        state = getattr(self, "_application_review_state", None)
        if not state or state["page"] is not page:
            return False
        self._application_review_state = None
        bundle = state["bundle"]
        results = tuple(state["results"])
        successes = sum(item.success for item in results)
        status = "succeeded" if successes == len(bundle.items) else "partial_failure" if successes else "failed"
        outcome = BundleOutcome(bundle.bundle_id, bundle.kind, bundle.execution_policy, status,
                                f"{successes}/{len(bundle.items)} application operations completed and verified.", results, bundle.digest)
        self._utility_bundle_finished(page, outcome)
        return True

    def _utility_bundle_finished(self: Any, page: QWidget, outcome: Any) -> None:
        """Project a terminal bundle outcome back onto its owning workflow."""
        setter = getattr(page, "set_results", None)
        if callable(setter):
            setter(outcome)
        status = str(getattr(outcome, "status", "completed")).replace("_", " ").title()
        message = str(getattr(outcome, "message", "The reviewed operations finished."))
        self._set_utility_notice(page, "success" if status == "Succeeded" else "warning", status, message)
