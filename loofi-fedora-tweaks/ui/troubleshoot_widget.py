"""Presentation-only Compass troubleshooting journey."""

from __future__ import annotations

from collections.abc import Callable
import time
from typing import Any, Protocol

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.troubleshooting.models import (
    TroubleshootingComparison,
    TroubleshootingFinding,
    TroubleshootingSession,
)
from core.troubleshooting.profiles import require_profile
from ui.components import (
    ActionBar,
    ActionProgress,
    Card,
    DetailsDisclosure,
    GhostButton,
    InlineNotice,
    LocalViewItem,
    LocalViewSwitcher,
    PageScaffold,
    PrimaryButton,
    SecondaryButton,
)
from ui.components.layout import CurrentPageStack
from ui.health_symptoms import HealthSymptomCardsMixin
from ui.companion_health import CompanionHealthMixin
from ui.operation_worker import OperationControllerQtAdapter
from ui.troubleshoot_results import TroubleshootResultsMixin
from ui.troubleshoot_presentation import (
    SOURCE_LABELS,
    STATE_LABELS,
    SYMPTOMS,
)


class _SessionHistory(Protocol):
    def latest(self) -> tuple[TroubleshootingSession | None, str]:
        ...


class _DefaultSessionHistory:
    """Read the existing bounded store without collecting or writing."""

    def sessions(self) -> tuple[TroubleshootingSession, ...]:
        from core.troubleshooting.inspection import TroubleshootingInspectionService

        return TroubleshootingInspectionService().sessions()

    def latest(self) -> tuple[TroubleshootingSession | None, str]:
        from core.troubleshooting.storage import TroubleshootingSessionStore

        try:
            snapshot = TroubleshootingSessionStore().read()
        except (OSError, RuntimeError, TypeError, ValueError):
            return None, "session-store-unavailable"
        return (
            snapshot.sessions[0] if snapshot.sessions else None,
            snapshot.reason_code,
        )


class TroubleshootWidget(CompanionHealthMixin, HealthSymptomCardsMixin, TroubleshootResultsMixin, QWidget):
    """One guided surface over the closed Compass profiles."""

    stopped = pyqtSignal()
    actionCenterRequested = pyqtSignal(str, object)
    routeRequested = pyqtSignal(str, object)

    _SOURCE_LABELS = SOURCE_LABELS
    _STATE_LABELS = STATE_LABELS
    _SYMPTOMS = SYMPTOMS

    def __init__(
        self,
        *,
        worker_factory: Callable[[str, dict[str, Any], QWidget], Any] | None = None,
        history: _SessionHistory | None = None,
        application_inventory_service: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.worker_factory = worker_factory
        self.history = history or _DefaultSessionHistory()
        self.application_inventory_service = application_inventory_service
        self._application_inventory: Any | None = None
        self.application_inventory_adapter = OperationControllerQtAdapter(parent=self)
        self.application_inventory_adapter.finished.connect(self._application_inventory_loaded)
        self.application_inventory_adapter.failed.connect(self._application_inventory_failed)
        self.application_inventory_adapter.stopped.connect(self._application_inventory_stopped)
        self._worker: Any | None = None
        self._update_run_id = ""
        self._closing = False
        self._stop_emitted = False
        self._stop_timer: QTimer | None = None
        self._current_session: TroubleshootingSession | None = None
        self._comparison: TroubleshootingComparison | None = None
        self._selected_finding: TroubleshootingFinding | None = None
        self._setup_ui()
        self._load_latest_session()
        self._refresh_saved_sessions()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Health"),
            self.tr("Choose a symptom, review findings, and follow one next step."),
        )
        root.addWidget(self.scaffold)

        self.safety_notice = InlineNotice(
            self.tr("Check before changing"),
            self.tr(
                "Choose a symptom and start a read-only check. Review any suggested "
                "change before applying it."
            ),
            kind="info",
        )
        self.safety_notice.setObjectName("troubleshootSafety")
        self.scaffold.add_widget(self.safety_notice)
        self._build_device_settings()
        view_row = QHBoxLayout()
        self.view_label = QLabel(self.tr("View"))
        self.view_label.setAccessibleName(self.tr("Troubleshoot view"))
        view_row.addWidget(self.view_label)
        self.view_switcher = LocalViewSwitcher()
        self.view_switcher.setObjectName("troubleshootViewSwitcher")
        self.view_switcher.set_views(
            [
                LocalViewItem(
                    "guided",
                    self.tr("Guided check"),
                    self.tr("Choose a problem and review what will be checked."),
                ),
                LocalViewItem(
                    "results",
                    self.tr("Results"),
                    self.tr("Review the current or latest completed session."),
                ),
            ]
        )
        self.view_switcher.viewActivated.connect(self._select_view)
        view_row.addWidget(self.view_switcher, 1)
        self.scaffold.add_layout(view_row)

        self.stack = CurrentPageStack()
        self.stack.setObjectName("troubleshootViewStack")
        self.stack.addWidget(self._guided_page())
        self.stack.addWidget(self._results_page())
        self.scaffold.add_widget(self.stack, 1)

    def _guided_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        choose = Card(
            self.tr("1. Problem"),
            self.tr("Start from the symptom you can observe."),
        )
        choose.setObjectName("troubleshootProfileCard")
        choose.setProperty("surfaceRole", "workflow")
        self.profile_label = QLabel(self.tr("What is going wrong?"))
        self.profile_selector = QComboBox()
        self.profile_selector.setObjectName("troubleshootProfileSelector")
        self.profile_selector.setAccessibleName(self.tr("Troubleshooting symptom"))
        self.profile_label.setBuddy(self.profile_selector)
        choose.add_widget(self.profile_label)
        for symptom_id, label, _profile_id, _limitation in self._SYMPTOMS:
            self.profile_selector.addItem(self.tr(label), symptom_id)
        self.profile_selector.currentIndexChanged.connect(self._profile_changed)
        # Keep the closed selector as the single source for routing and profile IDs.
        self.profile_selector.hide()
        self._build_symptom_cards(choose)
        self.application_selection = QComboBox()
        self.application_selection.setObjectName("troubleshootApplicationSelection")
        self.application_selection.setAccessibleName(self.tr("Select an installed application and exact installation"))
        self.application_selection.addItem(self.tr("Select an installed application (load inventory first)"), None)
        self.application_selection.currentIndexChanged.connect(self._select_inventory_application)
        self.application_selection.hide()
        choose.add_widget(self.application_selection)
        self.application_inventory_refresh = SecondaryButton(self.tr("Load installed applications"))
        self.application_inventory_refresh.setObjectName("troubleshootApplicationInventoryRefresh")
        self.application_inventory_refresh.clicked.connect(self.refresh_application_inventory)
        self.application_inventory_refresh.hide()
        choose.add_widget(self.application_inventory_refresh)
        self.application_inventory_status = QLabel(self.tr("Loading the inventory is optional and will not start an application."))
        self.application_inventory_status.setObjectName("troubleshootApplicationInventoryStatus")
        self.application_inventory_status.setWordWrap(True)
        self.application_inventory_status.hide()
        choose.add_widget(self.application_inventory_status)
        self.application_input = QLineEdit()
        self.application_input.setObjectName("troubleshootApplicationId")
        self.application_input.setAccessibleName(self.tr("Exact RPM package name or full Flatpak ref"))
        self.application_input.setPlaceholderText(self.tr("RPM package name or full app/ID/architecture/branch ref"))
        self.application_input.textEdited.connect(self._manual_application_edited)
        self.application_input.hide()
        choose.add_widget(self.application_input)
        self.application_scope = QComboBox()
        self.application_scope.setObjectName("troubleshootApplicationScope")
        self.application_scope.setAccessibleName(self.tr("Application installation"))
        for scope, label in (("rpm", "RPM package"), ("flatpak-user", "Flatpak user installation"), ("flatpak-system", "Flatpak system installation")):
            self.application_scope.addItem(self.tr(label), scope)
        self.application_scope.hide()
        choose.add_widget(self.application_scope)
        self.application_launch_attempted = QCheckBox(self.tr("I have already tried to start this app"))
        self.application_launch_attempted.setObjectName("troubleshootApplicationLaunchAttempted")
        self.application_launch_attempted.setAccessibleDescription(self.tr("If selected, read a bounded recent log summary. Raw log text is discarded."))
        self.application_launch_attempted.hide()
        choose.add_widget(self.application_launch_attempted)
        self._build_update_choices(choose)
        self.profile_limitation = InlineNotice("", "", kind="warning")
        self.profile_limitation.setObjectName("troubleshootProfileLimitation")
        self.profile_limitation.hide()
        choose.add_widget(self.profile_limitation)
        self.start_button = PrimaryButton(self.tr("Check this problem"), description=self.tr("Run a read-only check for the selected symptom."))
        self.start_button.setObjectName("troubleshootStart")
        self.start_button.clicked.connect(self.start_session)
        choose.add_widget(self.start_button)
        layout.addWidget(choose)

        checks = Card(
            self.tr("2. Checks"),
            self.tr("Review the system areas included in this read-only check."),
        )
        checks.setObjectName("troubleshootChecksCard")
        checks.setProperty("surfaceRole", "workflow")
        self.checks_label = QLabel()
        self.checks_label.setWordWrap(True)
        self.checks_label.setObjectName("troubleshootChecks")
        self.checks_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        checks.add_widget(self.checks_label)
        self._build_runtime_link(checks)
        self.technical_disclosure = DetailsDisclosure(
            summary=self.tr("Show technical details")
        )
        self.technical_disclosure.setObjectName("troubleshootTechnicalDetails")
        self.variant_label = QLabel(
            self.tr("Fedora variant is detected when the session starts.")
        )
        self.variant_label.setWordWrap(True)
        self.variant_label.setObjectName("troubleshootVariantPreview")
        self.technical_budget_label = QLabel()
        self.technical_budget_label.setWordWrap(True)
        self.technical_budget_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.technical_disclosure.add_widget(self.variant_label)
        self.technical_disclosure.add_widget(self.technical_budget_label)
        checks.add_widget(self.technical_disclosure)
        layout.addWidget(checks)

        self.start_notice = InlineNotice("", "", kind="neutral")
        self.start_notice.setObjectName("troubleshootStartNotice")
        self.start_notice.hide()
        layout.addWidget(self.start_notice)

        self.action_bar = ActionBar()
        self.cancel_button = GhostButton(
            self.tr("Cancel"),
            description=self.tr(
                "Stop the running session and keep the previous completed session."
            ),
        )
        self.cancel_button.setObjectName("troubleshootCancel")
        self.cancel_button.clicked.connect(self.cancel_session)
        self.cancel_button.hide()
        self.action_bar.add_action(self.cancel_button)
        layout.addWidget(self.action_bar)

        self.progress = ActionProgress(self.tr("Preparing the selected check…"))
        self.progress.setObjectName("troubleshootProgress")
        self.progress.hide()
        self.progress_source = QLabel()
        self.progress_source.setObjectName("troubleshootProgressSource")
        self.progress_source.setWordWrap(True)
        self.progress.details_layout.addWidget(self.progress_source)
        layout.addWidget(self.progress)
        layout.addStretch()
        self._profile_changed()
        return page

    def _profile_changed(self, *_args: Any) -> None:
        self._update_symptom_cards()
        is_updates = self._selected_symptom()[2] == "updates_failed"
        self.update_source_selector.setVisible(is_updates)
        self.update_run_context.setVisible(is_updates and bool(self._update_run_id))
        profile = require_profile(self.selected_profile_id())
        self._show_device_settings(profile.id)
        self.unused_runtimes_link.setVisible(profile.id == "storage_pressure")
        checked_areas = []
        technical_lines = []
        for budget in profile.source_budgets:
            label = self.tr(self._SOURCE_LABELS.get(budget.source_id, budget.source_id))
            checked_areas.append(self.tr("• %1").replace("%1", label))
            optional = self.tr("optional") if not budget.required else self.tr("required")
            variants = (
                self.tr("Traditional and Atomic")
                if len(budget.variants) == 2
                else self.tr("Atomic")
                if "atomic" in budget.variants
                else self.tr("Traditional")
            )
            technical_lines.append(
                self.tr("• %1 — up to %2 seconds · %3 · %4")
                .replace("%1", label)
                .replace("%2", f"{budget.timeout_seconds:g}")
                .replace("%3", optional)
                .replace("%4", variants)
            )
        self.checks_label.setText("\n".join(checked_areas))
        self.technical_budget_label.setText("\n".join(technical_lines))
        requires_application = dict(profile.parameter_schema).get("application_id") is not None
        self.application_input.setVisible(requires_application)
        self.application_scope.setVisible(requires_application and "application_scope" in dict(profile.parameter_schema))
        self.application_launch_attempted.setVisible(requires_application and "launch_attempted" in dict(profile.parameter_schema))
        self.application_selection.setVisible(requires_application and profile.version >= 2)
        self.application_inventory_refresh.setVisible(requires_application and profile.version >= 2)
        self.application_inventory_status.setVisible(requires_application and profile.version >= 2)
        symptom_limitation = self._selected_symptom()[3]
        if symptom_limitation:
            message = self.tr(symptom_limitation)
        elif profile.availability == "reduced":
            message = {
                "application-journal-collector-unavailable": self.tr(
                    "Application logs are not included in this check."
                ),
                "network-scan-excluded": self.tr(
                    "Network scanning is not included. Only the local connection and DNS settings are checked."
                ),
            }.get(
                profile.limitation_reason_code,
                self.tr("Some checks are not available for this symptom."),
            )
        else:
            message = ""
        if message:
            self.profile_limitation.set_notice(
                "warning",
                self.tr("Some checks are unavailable"),
                message,
            )
            self.profile_limitation.show()
        else:
            self.profile_limitation.hide()

    def start_session(self) -> None:
        """Create the worker only after direct user activation."""
        if self._closing or (self._worker is not None and self._worker.isRunning()):
            return
        profile = require_profile(self.selected_profile_id())
        parameters: dict[str, Any] = {}
        if self._update_run_id and "run_id" in dict(profile.parameter_schema):
            parameters["run_id"] = self._update_run_id
        if dict(profile.parameter_schema).get("application_id") is not None:
            application_id = self.application_input.text().strip()
            if not application_id:
                self.start_notice.set_notice(
                    "warning",
                    self.tr("Application is required"),
                    self.tr("Select an installed application or enter its exact RPM package name or full Flatpak reference."),
                )
                self.start_notice.show()
                self.application_input.setFocus()
                return
            parameters["application_id"] = application_id
            if "application_scope" in dict(profile.parameter_schema):
                parameters["application_scope"] = str(self.application_scope.currentData())
            if "launch_attempted" in dict(profile.parameter_schema):
                parameters["launch_attempted"] = self.application_launch_attempted.isChecked()
            try:
                profile.validate_parameters(parameters)
            except ValueError as exc:
                self.start_notice.set_notice(
                    "warning",
                    self.tr("Application selection needs review"),
                    self.tr("Use a package name for RPM or a full app/ID/architecture/branch reference for Flatpak. %1").replace("%1", str(exc)),
                )
                self.start_notice.show()
                self.application_input.setFocus()
                return

        if self.worker_factory is None:
            from core.workers.troubleshooting_worker import TroubleshootingWorker

            worker = TroubleshootingWorker(
                profile.id,
                parameters=parameters,
                parent=self,
            )
        else:
            worker = self.worker_factory(profile.id, parameters, self)
        self._worker = worker
        self.start_notice.hide()
        self.progress.set_busy(self.tr("Starting the read-only check…"))
        self.progress_source.setText(self.tr("Current source: Preparing"))
        self.progress.show()
        self.start_button.set_loading(True, self.tr("Checking…"))
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        worker.source_progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        worker.start()

    def refresh_application_inventory(self) -> None:
        """Read the existing RPM and Flatpak inventory only after explicit activation."""
        if self.application_inventory_adapter.busy:
            return
        if self.application_inventory_service is None:
            from services.software.installed_applications import InstalledApplicationService

            self.application_inventory_service = InstalledApplicationService()
        self.application_inventory_refresh.setEnabled(False)
        self.application_inventory_status.setText(self.tr("Reading installed RPM and Flatpak application identities…"))
        reader = getattr(self.application_inventory_service, "snapshot_for_troubleshooting", None)
        operation = (lambda: reader(cancelled=lambda: self.application_inventory_adapter.cancel_requested)) if callable(reader) else self.application_inventory_service.snapshot
        if not self.application_inventory_adapter.start(operation):
            self.application_inventory_refresh.setEnabled(True)
            self.application_inventory_status.setText(self.tr("Application inventory could not be started."))

    def _application_inventory_loaded(self, inventory: Any) -> None:
        from services.software.installed_applications import InstalledInventory

        if not isinstance(inventory, InstalledInventory):
            self.application_inventory_status.setText(self.tr("Application inventory returned an unknown result."))
            return
        self._application_inventory = inventory
        self.application_selection.blockSignals(True)
        self.application_selection.clear()
        self.application_selection.addItem(self.tr("Select an installed application"), None)
        applications = sorted(inventory.applications, key=lambda app: (app.name.casefold(), app.installation, app.ref))[:2048]
        for app in applications:
            if app.source == "fedora":
                identifier, scope, source_label = app.app_id, "rpm", self.tr("RPM")
            else:
                identifier = app.ref
                source_label = self.tr("Flatpak")
                scope = f"flatpak-{app.installation}" if app.installation in {"user", "system"} else f"flatpak-installation:{app.installation}"
            label = self.tr("%1 · %2 · %3").replace("%1", app.name).replace("%2", source_label).replace("%3", app.installation)
            self.application_selection.addItem(label, {"identifier": identifier, "scope": scope})
        self.application_selection.blockSignals(False)
        limitations = [self.tr("Some installation sources could not be checked: %1").replace("%1", ", ".join(sorted(inventory.unknown_sources)))] if inventory.unknown_sources else []
        if any("cancelled" in error.casefold() for error in inventory.errors):
            limitations.append(self.tr("The inventory read was cancelled; any displayed installations are partial. No app was started."))
        if len(inventory.applications) > len(applications):
            limitations.append(self.tr("The displayed selection is limited to the first 2,048 inventory entries."))
        if not applications:
            limitations.append(self.tr("No installed application was reported. Enter an exact package name or Flatpak ref to check for a missing installation."))
        if not limitations:
            limitations.append(self.tr("Select one exact installation. This inventory read did not start any app."))
        self.application_inventory_status.setText("\n".join(limitations))

    def _application_inventory_failed(self, _message: str) -> None:
        self._application_inventory = None
        self.application_inventory_status.setText(self.tr("Installed application inventory could not be read. You can still enter an exact package name or Flatpak ref."))

    def _application_inventory_stopped(self) -> None:
        if hasattr(self, "application_inventory_refresh"):
            self.application_inventory_refresh.setEnabled(True)
        self._emit_stopped_if_ready()

    def _select_inventory_application(self, index: int) -> None:
        selection = self.application_selection.itemData(index)
        if not isinstance(selection, dict):
            return
        self.application_input.setText(str(selection.get("identifier", "")))
        scope = str(selection.get("scope", ""))
        scope_index = self.application_scope.findData(scope)
        if scope_index < 0 and scope.startswith("flatpak-installation:"):
            installation = scope.partition(":")[2]
            self.application_scope.addItem(self.tr("Flatpak named installation: %1").replace("%1", installation), scope)
            scope_index = self.application_scope.findData(scope)
        if scope_index >= 0:
            self.application_scope.setCurrentIndex(scope_index)

    def _manual_application_edited(self, _text: str) -> None:
        if self.application_selection.currentIndex() > 0:
            self.application_selection.blockSignals(True)
            self.application_selection.setCurrentIndex(0)
            self.application_selection.blockSignals(False)
            self.application_scope.setCurrentIndex(self.application_scope.findData("rpm"))

    def preselect_profile(self, profile_id: str) -> bool:
        """Select one exact symptom for review without starting collection."""
        symptom = next(
            (item for item in self._SYMPTOMS if item[2] == profile_id),
            None,
        )
        if symptom is None:
            return False
        index = self.profile_selector.findData(symptom[0])
        if index < 0:
            return False
        self.profile_selector.setCurrentIndex(index)
        self.view_switcher.set_active_view("guided")
        self._select_view("guided")
        self.start_button.setFocus()
        return True

    def cancel_session(self) -> None:
        worker = self._worker
        if worker is None or not worker.isRunning():
            return
        self.cancel_button.setEnabled(False)
        self.progress.set_busy(self.tr("Cancelling and preserving the previous session…"))
        worker.cancel()

    @property
    def busy(self) -> bool:
        """Keep the owning window alive while either bounded reader is running."""
        worker = self._worker
        return bool((worker is not None and worker.isRunning()) or self.application_inventory_adapter.busy)

    def request_stop(self) -> None:
        """Cooperatively stop this page's workers during application shutdown."""
        if not self._closing:
            self._stop_emitted = False
        self._closing = True
        self.application_inventory_adapter.request_stop()
        self.cancel_session()
        self._emit_stopped_if_ready()

    def wait_for_stop(self, timeout_ms: int = 5000) -> bool:
        """Share a bounded wait across the troubleshooting and inventory readers."""
        deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000
        worker = self._worker
        if worker is not None and worker.isRunning():
            if not worker.wait(max(0, int((deadline - time.monotonic()) * 1000))):
                return False
        remaining = max(0, int((deadline - time.monotonic()) * 1000))
        stopped = self.application_inventory_adapter.wait_for_stop(remaining)
        self._emit_stopped_if_ready()
        return stopped and not self.busy

    def cleanup(self) -> None:
        """Stop readers without allowing a live QThread to outlive its owner."""
        self.request_stop()
        self.wait_for_stop(1000)

    def _emit_stopped_if_ready(self) -> None:
        if self._closing and not self.busy and not self._stop_emitted:
            self._stop_emitted = True
            self.stopped.emit()

    def _on_progress(self, progress: Any) -> None:
        if self._closing:
            return
        source_id = str(getattr(progress, "source_id", "") or "")
        state = str(getattr(progress, "state", "running") or "running")
        percentage = int(getattr(progress, "percentage", 0) or 0)
        label = self.tr(self._SOURCE_LABELS.get(source_id, source_id or "Finalizing"))
        state_label = self.tr(self._STATE_LABELS.get(state, "Running"))
        self.progress.set_progress(
            percentage,
            self.tr("%1 — %2").replace("%1", label).replace("%2", state_label),
        )
        self.progress_source.setText(
            self.tr("Current source: %1").replace("%1", label)
        )

    def _on_finished(self, outcome: Any) -> None:
        if self._closing:
            self._finish_worker()
            return
        self._current_session = outcome.session
        self._comparison = getattr(outcome, "comparison", None)
        self._finish_worker()
        self._render_session(
            outcome.session,
            self._comparison,
            str(getattr(outcome, "persistence_reason_code", "") or ""),
        )
        self._refresh_saved_sessions()
        self.view_switcher.set_active_view("results")
        self._select_view("results")

    def _on_error(self, _message: str) -> None:
        if self._closing:
            self._finish_worker()
            return
        self._finish_worker()
        self.start_notice.set_notice(
            "error",
            self.tr("Troubleshooting could not finish"),
            self.tr(
                "No result replaced the previous completed session. "
                "Review source availability and try again."
            ),
        )
        self.start_notice.show()

    def _finish_worker(self) -> None:
        worker = self._worker
        self._worker = None
        self.progress.hide()
        self.cancel_button.hide()
        self.start_button.set_loading(False)
        self.start_button.setText(
            self.tr("Check again")
            if self._current_session is not None
            else self.tr("Start read-only check")
        )
        if worker is not None:
            worker.wait(1000)
            worker.deleteLater()
        self._emit_stopped_if_ready()

    def _select_view(self, view_id: str) -> None:
        self.stack.setCurrentIndex(1 if view_id == "results" else 0)
