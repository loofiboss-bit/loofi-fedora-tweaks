"""Window-wide status for operations owned by the existing Qt adapter."""
from __future__ import annotations

from typing import Any

from core.navigation import resolve


class MainWindowOperationStatusMixin:
    """Keep operation identity, origin, and exact results available in the shell."""

    _utility_operation_adapter: Any | None

    def _build_operation_status_controls(self: Any, layout: Any) -> None:
        from PyQt6.QtWidgets import QPushButton

        self._return_to_operation_button = QPushButton(self.tr("Return to work"))
        self._return_to_operation_button.setAccessibleName(
            self.tr("Return to the page where the current operation started")
        )
        self._return_to_operation_button.clicked.connect(self._return_to_operation_origin)
        self._return_to_operation_button.hide()
        layout.addWidget(self._return_to_operation_button)
        self._activity_status_button = QPushButton(self.tr("Open Activity"))
        self._activity_status_button.clicked.connect(self._open_activity_status_result)
        self._activity_status_button.hide()
        layout.addWidget(self._activity_status_button)

    def _profile_editor_close_decision(self: Any) -> str:
        """Return allow, cancel, or saving for an already-open profile editor."""
        entry = getattr(self, "_sidebar_index", {}).get("utility_tune")
        if entry is None:
            return "allow"
        page_widget = getattr(entry, "page_widget", None)
        get_real_widget = getattr(page_widget, "get_real_widget", None)
        page = get_real_widget() if callable(get_real_widget) else page_widget
        request_close = getattr(page, "request_close_for_profile", None)
        return str(request_close()) if callable(request_close) else "allow"

    def _new_utility_operation_adapter(
        self: Any,
        *,
        phase: str = "inspection",
        operation_name: str = "",
    ) -> Any:
        """Create the single window-owned worker adapter for a reviewed change."""
        from ui.operation_worker import OperationControllerQtAdapter

        self._last_operation_run_id = ""
        self._operation_origin_route_id = str(getattr(self, "_active_route_id", "") or "")
        route = resolve(self._operation_origin_route_id) if self._operation_origin_route_id else None
        destination_id = str(getattr(self, "_active_destination_id", "") or "")
        destination = next((item for item in getattr(self, "_utility_destinations", ())
                            if item.id == destination_id or item.default_route_id == self._operation_origin_route_id), None)
        self._operation_origin_label = str(
            getattr(route, "label", "")
            or getattr(destination, "label", "")
            or destination_id
            or self.tr("current page")
        )
        phase_names = {
            "inspection": self.tr("Checking settings"),
            "review": self.tr("Reviewing a change"),
            "verification": self.tr("Verifying the result"),
            "change": self.tr("Applying a reviewed change"),
        }
        self._operation_name = operation_name or phase_names.get(phase, self.tr("Working"))
        adapter = OperationControllerQtAdapter(parent=self)
        adapter.stopped.connect(lambda selected=adapter: self._utility_operation_adapter_stopped(selected))
        self._utility_operation_adapter = adapter
        status = getattr(self, "_status_label", None)
        if status is not None:
            status.setAccessibleName(
                self.tr("%1 from %2").replace("%1", self._operation_name).replace("%2", self._operation_origin_label)
            )
            status.setText(
                self.tr("%1 — %2\nThis operation remains active when you change pages.")
                .replace("%1", self._operation_name)
                .replace("%2", self._operation_origin_label)
            )
            return_button = getattr(self, "_return_to_operation_button", None)
            if return_button is not None:
                return_button.setText(self.tr("Return to %1").replace("%1", self._operation_origin_label))
                return_button.setVisible(bool(self._operation_origin_route_id))
            activity_button = getattr(self, "_activity_status_button", None)
            if activity_button is not None:
                activity_button.hide()
            self._status_frame.show()
            adapter.finished.connect(lambda result: self._record_global_operation_result(result, phase=phase))
            adapter.failed.connect(lambda message: self._record_global_operation_result(None, message, phase=phase))
            adapter.cancelled.connect(lambda: self._record_global_operation_result(
                None,
                self.tr("Operation cancelled. Check current values before continuing.")
                if phase in {"change", "verification"}
                else self.tr("Review or inspection cancelled; no new change was started."),
                phase=phase,
            ))
        return adapter

    def _record_global_operation_result(
        self: Any, result: Any, message: str = "", *, phase: str = "inspection"
    ) -> None:
        """Project existing results into the shell; never infer verification."""
        status = getattr(self, "_status_label", None)
        if status is None:
            return
        outcome = result[0] if isinstance(result, tuple) and result else result
        if phase == "inspection" and not message and getattr(outcome, "success", True) is not False:
            self._clear_utility_operation_status()
            return
        run_id = str(getattr(outcome, "run_id", "") or "")
        if run_id:
            self._last_operation_run_id = run_id
        fallback = self.tr("Inspection finished. No change was started.")
        if phase == "review":
            fallback = self.tr("Review ready. No change was started.")
        elif phase == "change":
            fallback = self.tr("Operation finished. Check its detailed result.")
        elif phase == "verification":
            fallback = self.tr("Verification finished. Check the affected result.")
        detail = message or str(getattr(outcome, "message", "") or fallback)
        status.setAccessibleName(
            self.tr("%1 from %2: %3")
            .replace("%1", self._operation_name)
            .replace("%2", self._operation_origin_label)
            .replace("%3", detail)
        )
        status.setText(f"{self._operation_name} — {self._operation_origin_label}\n{detail}")
        return_button = getattr(self, "_return_to_operation_button", None)
        if return_button is not None:
            return_button.setText(self.tr("Return to %1").replace("%1", self._operation_origin_label))
            return_button.setVisible(bool(self._operation_origin_route_id))
        activity_button = getattr(self, "_activity_status_button", None)
        if activity_button is not None:
            activity_button.setVisible(bool(self._last_operation_run_id))
        self._status_frame.show()

    def _clear_utility_operation_status(self: Any) -> None:
        status = getattr(self, "_status_label", None)
        if status is not None:
            status.clear()
            status.setAccessibleDescription("")
        return_button = getattr(self, "_return_to_operation_button", None)
        if return_button is not None:
            return_button.hide()
        activity_button = getattr(self, "_activity_status_button", None)
        if activity_button is not None:
            activity_button.hide()
        frame = getattr(self, "_status_frame", None)
        if frame is not None and not bool(getattr(getattr(self, "_undo_btn", None), "isVisible", lambda: False)()):
            frame.hide()

    def _return_to_operation_origin(self: Any) -> None:
        route_id = str(getattr(self, "_operation_origin_route_id", "") or "")
        if route_id:
            self.switch_to_route(route_id)
