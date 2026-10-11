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
                scope = self.tr("System Flatpak installation")
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
            accept_button.setText(self.tr("Apply %1 changes").replace("%1", str(item_count)))
        if dialog.exec() != QDialog.DialogCode.Accepted:
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

    def _utility_bundle_finished(self: Any, page: QWidget, outcome: Any) -> None:
        """Project a terminal bundle outcome back onto its owning workflow."""
        setter = getattr(page, "set_results", None)
        if callable(setter):
            setter(outcome)
        status = str(getattr(outcome, "status", "completed")).replace("_", " ").title()
        message = str(getattr(outcome, "message", "The reviewed operations finished."))
        self._set_utility_notice(page, "success" if status == "Succeeded" else "warning", status, message)
