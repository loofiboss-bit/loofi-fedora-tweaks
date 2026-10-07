"""Presentation-only Install workflow for the v29 utility shell.

The widget owns discovery, filtering, selection, and review presentation. It
never invokes a package manager. ``bundleReviewRequested`` is the hand-off to
the shared operation controller owned by the application shell.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from core.tasks import (
    ApplicationCatalog,
    ApplicationContext,
    ApplicationEligibility,
    ApplicationRecord,
)
from PyQt6.QtCore import QEvent, QObject, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QLineEdit, QPushButton, QScrollArea, QStyleOptionViewItem, QStyledItemDelegate, QVBoxLayout, QWidget

from ui.components import Card, DetailsDisclosure, InlineNotice, PageScaffold, PrimaryButton, StatusBadge
from ui.icon_pack import get_qicon


class ApplicationRowDelegate(QStyledItemDelegate):
    """The rich row checkbox is the only visible selection affordance."""

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator


class InstallWorkflowPage(QWidget):
    """Searchable curated application selection with an explicit review step."""

    bundleReviewRequested = pyqtSignal(object)
    resultUpdated = pyqtSignal(object)
    actionReviewRequested = pyqtSignal(str, object)
    nativeSettingsRequested = pyqtSignal(object)
    stopped = pyqtSignal()
    # Compatibility signal for older route adapters.  It is never rendered as
    # a normal CTA; the visible review button always owns this page's primary
    # action.
    routeRequested = pyqtSignal(str)

    def __init__(
        self,
        *,
        catalog: ApplicationCatalog | None = None,
        context: ApplicationContext | None = None,
        source_status_service: Any | None = None,
        installed_service: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog or ApplicationCatalog()
        self.context = replace(context, unknown_sources=frozenset({"flatpak", "fedora"})) if context is not None and installed_service is not None else context
        self._source_status_service = source_status_service
        self._source_status_adapter: Any | None = None
        self._rows: dict[str, tuple[ApplicationRecord, ApplicationEligibility, QListWidgetItem]] = {}
        self._selected_ids: set[str] = set()
        self._row_checks: dict[str, QCheckBox] = {}
        self._last_bundle: object | None = None
        self._last_outcome: object | None = None
        self._compat_primary_button: QPushButton | None = None
        self.setObjectName("installWorkflowPage")
        self.setAccessibleName(self.tr("Install applications"))
        self.setAccessibleDescription(self.tr("Search the curated application catalog, review a selection, and install it."))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Install"),
            self.tr("Find trusted applications, review their source, and install them together."),
        )
        self.owns_scroll = True
        self.body_scroll = QScrollArea(self)
        self.body_scroll.setObjectName("installBodyScroll")
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.body_scroll.setWidget(self.scaffold)
        self.body_scroll.setMinimumHeight(0)
        root.addWidget(self.body_scroll, 1)

        self.intro = Card()
        self.intro.setProperty("surfaceRole", "toolbar")
        self.intro.body.setContentsMargins(0, 0, 0, 8)
        self.intro.body.setSpacing(8)
        self.scaffold.add_widget(self.intro)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("installApplicationSearch")
        self.search_input.setPlaceholderText(self.tr("Search applications…"))
        self.search_input.setAccessibleName(self.tr("Search applications"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_rows)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(self.search_input, 1)
        self.category_filter = QComboBox()
        self.category_filter.setObjectName("installCategoryFilter")
        self.category_filter.setAccessibleName(self.tr("Application category"))
        self.category_filter.addItem(self.tr("All categories"), "")
        for category in self.catalog.categories():
            self.category_filter.addItem(category, category)
        self.category_filter.currentIndexChanged.connect(self._refresh_rows)
        filter_row.addWidget(self.category_filter)
        self.intro.body.addLayout(filter_row)
        self.view_filter = QComboBox()
        self.view_filter.setAccessibleName(self.tr("Application view"))
        self.view_filter.addItem(self.tr("Catalog"), "catalog")
        self.view_filter.addItem(self.tr("Installed"), "installed")
        self.intro.add_widget(self.view_filter)

        self.flathub_status_card = Card(
            self.tr("App sources"),
            self.tr("Source setup can affect which applications are available."),
        )
        self.flathub_status_card.setObjectName("installFlathubStatus")
        self.flathub_system_status = QLabel(self.tr("System scope: Status not checked yet"))
        self.flathub_system_status.setWordWrap(True)
        self.flathub_system_status.setObjectName("installFlathubSystemStatus")
        self.flathub_system_status.setAccessibleName(self.tr("Flathub system scope status"))
        self.flathub_user_status = QLabel(self.tr("User scope: Status not checked yet"))
        self.flathub_user_status.setWordWrap(True)
        self.flathub_user_status.setObjectName("installFlathubUserStatus")
        self.flathub_user_status.setAccessibleName(self.tr("Flathub user scope status"))
        self.flathub_summary = QLabel(self.tr("Source status has not been checked."))
        self.flathub_summary.setObjectName("installFlathubSummary")
        self.flathub_summary.setWordWrap(True)
        self.flathub_status_card.add_widget(self.flathub_summary)
        self.flathub_details = DetailsDisclosure(summary=self.tr("Show source setup details"))
        self.flathub_details.add_widget(self.flathub_system_status)
        self.flathub_details.add_widget(self.flathub_user_status)
        self.flathub_status_card.add_widget(self.flathub_details)
        self.flathub_refresh_button = QPushButton(self.tr("Refresh Flathub status"))
        self.flathub_refresh_button.setObjectName("installFlathubRefresh")
        self.flathub_refresh_button.setAccessibleName(self.tr("Refresh Flathub source status"))
        self.flathub_refresh_button.clicked.connect(self.refresh_flathub_status)
        self.flathub_status_card.add_widget(self.flathub_refresh_button)
        self.flathub_guidance_button = QPushButton(self.tr("Review Flathub setup guidance"))
        self.flathub_guidance_button.setObjectName("installFlathubGuidance")
        self.flathub_guidance_button.setAccessibleName(self.tr("Review Flathub setup instructions"))
        self.flathub_guidance_button.clicked.connect(lambda: self.routeRequested.emit("software:repos"))
        self.flathub_guidance_button.hide()
        self.flathub_status_card.add_widget(self.flathub_guidance_button)
        self.scaffold.add_widget(self.flathub_status_card)

        self.state_notice = InlineNotice(
            self.tr("Select applications"),
            self.tr("Choose one or more applications, then review the exact sources and identifiers."),
            kind="info",
        )
        self.state_notice.setObjectName("installWorkflowState")
        self.state_notice.hide()
        self.intro.add_widget(self.state_notice)
        self.match_summary = QLabel()
        self.match_summary.setObjectName("installMatchSummary")
        self.intro.add_widget(self.match_summary)

        self.application_list = QListWidget()
        self.application_list.setItemDelegate(ApplicationRowDelegate(self.application_list))
        self.application_list.setObjectName("installApplicationList")
        self.application_list.setAccessibleName(self.tr("Curated application catalog"))
        self.application_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.application_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.application_list.setSizeAdjustPolicy(QListWidget.SizeAdjustPolicy.AdjustToContents)
        self.application_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.application_list.itemChanged.connect(self._on_item_changed)
        viewport = self.application_list.viewport()
        if viewport is not None:
            viewport.installEventFilter(self)

        self.scaffold.add_widget(self.application_list, 1)
        from ui.installed_applications import InstalledApplicationsCard
        self.installed_card = InstalledApplicationsCard(service=installed_service, parent=self)
        self.installed_card.actionReviewRequested.connect(self.actionReviewRequested.emit)
        self.installed_card.nativeSettingsRequested.connect(self.nativeSettingsRequested.emit)
        self.installed_card.inventoryUpdated.connect(self._apply_installed_inventory)
        self.installed_card.stopped.connect(self._notify_stopped)
        self.installed_card.hide()
        self.scaffold.add_widget(self.installed_card)

        self.review_card = Card()
        self.review_card.setObjectName("installReviewCard")
        self.review_summary = QLabel(self.tr("No applications selected."))
        self.review_summary.setObjectName("installReviewSummary")
        self.review_summary.setWordWrap(True)
        self.review_card.add_widget(self.review_summary)
        self.review_button = PrimaryButton(
            self.tr("Review selected applications"),
            description=self.tr("Create a reviewable install bundle without running it."),
        )
        self.review_button.setObjectName("installReviewButton")
        self.review_button.clicked.connect(self.review_selection)
        self.review_card.add_widget(self.review_button)
        root.addWidget(self.review_card)

        self.results_card = Card(
            self.tr("Results"),
            self.tr("Each application keeps its own terminal result and recovery guidance."),
        )
        self.results_card.setObjectName("installResultsCard")
        self.results_list = QListWidget()
        self.results_list.setObjectName("installResultsList")
        self.results_list.setAccessibleName(self.tr("Application install results"))
        self.results_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_card.add_widget(self.results_list)
        self.results_card.hide()
        self.scaffold.add_widget(self.results_card)
        self.scaffold.content_layout.addStretch()
        self.view_filter.currentIndexChanged.connect(self._set_application_view)
        self._refresh_rows()
        if installed_service is not None:
            self.installed_card.refresh()
        if self._source_status_service is not None:
            self.refresh_flathub_status()

    @property
    def busy(self) -> bool:
        return self.installed_card.busy or (self._source_status_adapter is not None and self._source_status_adapter.busy)

    def request_stop(self) -> None:
        self.installed_card.request_stop()
        if self._source_status_adapter is not None:
            self._source_status_adapter.cancel()

    def _notify_stopped(self) -> None:
        if not self.busy:
            self.stopped.emit()

    def cleanup(self, timeout_ms: int = 1000) -> bool:
        self.request_stop()
        installed_stopped = self.installed_card.cleanup(timeout_ms)
        source_stopped = self._source_status_adapter is None or self._source_status_adapter.close(timeout_ms)
        return installed_stopped and source_stopped

    def _set_application_view(self, *_args: Any) -> None:
        installed = self.view_filter.currentData() == "installed"
        self.installed_card.setVisible(installed)
        self.flathub_status_card.setVisible(not installed)
        self.application_list.setVisible(not installed)
        self.review_card.setVisible(not installed)
        self.search_input.setVisible(True)
        self.search_input.setPlaceholderText(self.tr("Search installed applications…") if installed else self.tr("Search applications…"))
        self.category_filter.setVisible(not installed)
        self.match_summary.setVisible(not installed)
        if installed:
            self.installed_card.set_search(self.search_input.text())

    def _apply_installed_inventory(self, inventory: object) -> None:
        if self.context is not None:
            self.context = replace(self.context, installed_ids=getattr(inventory, "installed_ids", frozenset()), unknown_sources=getattr(inventory, "unknown_sources", frozenset()))
            self._refresh_rows()

    def refresh_installed_applications(self) -> None:
        self.installed_card.refresh()

    def refresh_flathub_status(self) -> None:
        """Read local Flathub scopes on a worker and keep failures explicit."""
        if self._source_status_service is None:
            return
        if self._source_status_adapter is None:
            from ui.operation_worker import OperationControllerQtAdapter

            self._source_status_adapter = OperationControllerQtAdapter(parent=self)
            self._source_status_adapter.finished.connect(self._apply_flathub_statuses)
            self._source_status_adapter.failed.connect(self._flathub_status_failed)
            self._source_status_adapter.stopped.connect(lambda: self.flathub_refresh_button.setEnabled(True))
            self._source_status_adapter.stopped.connect(self._notify_stopped)
        if self._source_status_adapter.busy:
            return
        self.flathub_refresh_button.setEnabled(False)
        self.flathub_system_status.setText(self.tr("System scope: Checking…"))
        self.flathub_user_status.setText(self.tr("User scope: Checking…"))
        self.flathub_guidance_button.hide()
        self._source_status_adapter.start(self._source_status_service.snapshot)

    def _apply_flathub_statuses(self, statuses: object) -> None:
        """Render system and user remote state without conflating unknown and disabled."""
        found: dict[str, object] = {}
        for status in statuses if isinstance(statuses, (tuple, list)) else ():
            if getattr(status, "source_id", "") == "flathub":
                found[str(getattr(getattr(status, "scope", None), "value", ""))] = status
        for scope, label in (("system", self.flathub_system_status), ("user", self.flathub_user_status)):
            status = found.get(scope)
            state = str(getattr(getattr(status, "state", None), "value", "unknown"))
            state_text = {
                "enabled": self.tr("Enabled"),
                "disabled": self.tr("Not enabled"),
                "unknown": self.tr("Could not check"),
            }.get(state, self.tr("Could not check"))
            scope_text = self.tr("System scope") if scope == "system" else self.tr("User scope")
            message = f"{scope_text}: {state_text}"
            if state == "unknown":
                reason = getattr(getattr(status, "reason", None), "value", "")
                reason_text = {
                    "tool_unavailable": self.tr("Flatpak is not installed."),
                    "unsupported_backend": self.tr("This Fedora deployment is not supported for this check."),
                    "timeout": self.tr("The source check timed out."),
                    "command_failed": self.tr("The configured sources could not be read."),
                    "invalid_response": self.tr("Flatpak returned an invalid source list."),
                    "probe_failed": self.tr("The source configuration could not be inspected."),
                }.get(str(reason), self.tr("Refresh to check again."))
                message = f"{message} {reason_text}"
            label.setText(message)
            label.setProperty("sourceState", state)
            label.setAccessibleDescription(message)
        system_state = str(getattr(getattr(found.get("system"), "state", None), "value", "unknown"))
        self.flathub_guidance_button.setVisible(system_state != "enabled")
        states = {
            scope: str(getattr(getattr(value, "state", None), "value", "unknown"))
            for scope, value in found.items()
        }
        self.flathub_summary.setText(
            self.tr("System: %1 · User: %2")
            .replace("%1", self._scope_summary(states.get("system", "unknown")))
            .replace("%2", self._scope_summary(states.get("user", "unknown")))
        )

    def _scope_summary(self, state: str) -> str:
        return self.tr({"enabled": "available", "disabled": "not enabled", "unknown": "unknown"}.get(state, "unknown"))

    def _flathub_status_failed(self, _message: str) -> None:
        """Keep an adapter failure distinct from a disabled source."""
        from services.software.source_status import SourceScope, SourceState, SourceStatus, SourceStatusReason

        self._apply_flathub_statuses((
            SourceStatus("flathub", SourceScope.SYSTEM, SourceState.UNKNOWN, SourceStatusReason.PROBE_FAILED),
            SourceStatus("flathub", SourceScope.USER, SourceState.UNKNOWN, SourceStatusReason.PROBE_FAILED),
        ))

    @property
    def last_bundle(self) -> object | None:
        return self._last_bundle

    @property
    def last_outcome(self) -> object | None:
        return self._last_outcome

    @property
    def primary_button(self) -> QPushButton:
        """Return the visible review CTA, with a hidden legacy route shim.

        Older shell integrations used ``primary_button`` to open the native
        application route.  Keeping a hidden, non-primary shim lets those
        integrations migrate without adding a second visible CTA or bypassing
        the curated review surface.
        """
        if self._compat_primary_button is None:
            button = QPushButton(self)
            button.setObjectName("installLegacyPrimaryButton")
            button.setVisible(False)
            button.clicked.connect(lambda: self.routeRequested.emit("software:apps"))
            self._compat_primary_button = button
        return self._compat_primary_button

    def set_context(self, context: ApplicationContext | None) -> None:
        self.context = context
        if self.context is not None and self.installed_card.service is not None:
            inventory = self.installed_card.inventory
            self.context = replace(self.context, installed_ids=inventory.installed_ids, unknown_sources=inventory.unknown_sources)
        self._refresh_rows()

    def selected_application_ids(self) -> tuple[str, ...]:
        return tuple(
            record.id for record in self.catalog.all(context=self.context)
            if record.id in self._selected_ids
        )

    def _refresh_rows(self, *_args: Any) -> None:
        if self.view_filter.currentData() == "installed":
            self.installed_card.set_search(self.search_input.text())
            return
        self._selected_ids.intersection_update(
            record.id for record in self.catalog.all(context=self.context)
            if self.catalog.eligibility(record, self.context).selectable
        )
        query = self.search_input.text()
        category = str(self.category_filter.currentData() or "")
        self.application_list.blockSignals(True)
        self.application_list.clear()
        self._rows.clear()
        self._row_checks.clear()
        for record, eligibility in self.catalog.search(query, category=category, context=self.context):
            item = QListWidgetItem(self._row_text(record, eligibility), self.application_list)
            item.setData(Qt.ItemDataRole.UserRole, record.id)
            item.setToolTip(eligibility.reason)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if eligibility.selectable:
                item.setCheckState(Qt.CheckState.Checked if record.id in self._selected_ids else Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._rows[record.id] = (record, eligibility, item)
            self._add_application_row(record, eligibility, item)
        self.application_list.blockSignals(False)
        count = self.application_list.count()
        self.match_summary.setText(self.tr("%1 applications").replace("%1", str(count)) if count else self.tr("No applications match. Clear the search or change the category."))
        self._resize_application_rows()
        self._update_review_summary()

    def _row_text(self, record: ApplicationRecord, eligibility: ApplicationEligibility) -> str:
        return f"{record.name} · {record.source_label} · {self._state_label(eligibility.state)}"

    def _state_label(self, state: str) -> str:
        return self.tr({
            "available": "Ready to review",
            "advanced": "Advanced · reboot may be required",
            "installed": "Installed",
            "offline": "Offline",
            "unavailable": "Unavailable",
        }.get(state, state))

    def _add_application_row(self, record: ApplicationRecord, eligibility: ApplicationEligibility, item: QListWidgetItem) -> None:
        row = QWidget()
        row.setObjectName("applicationRow")
        row.setAccessibleName(record.name)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        check = QCheckBox()
        check.setAccessibleName(self.tr("Select %1").replace("%1", record.name))
        check.setChecked(record.id in self._selected_ids)
        check.setEnabled(eligibility.selectable)
        check.setToolTip(eligibility.reason)
        check.toggled.connect(lambda checked, selected=item: selected.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked))
        self._row_checks[record.id] = check
        layout.addWidget(check)
        icon = QLabel()
        app_icon = QIcon.fromTheme(record.package_id, QIcon.fromTheme(record.id))
        if app_icon.isNull():
            app_icon = get_qicon("packages-software", size=32)
        icon.setPixmap(app_icon.pixmap(32, 32))
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        copy = QVBoxLayout()
        title = QLabel(record.name)
        title.setObjectName("applicationRowTitle")
        title.setWordWrap(True)
        copy.addWidget(title)
        description = QLabel(self.tr(record.description))
        description.setObjectName("applicationRowDescription")
        description.setWordWrap(True)
        copy.addWidget(description)
        badges = QHBoxLayout()
        source = StatusBadge(self.tr(record.source_label), kind="info")
        source.setObjectName("applicationSourceBadge")
        badges.addWidget(source)
        scope = QLabel(self.tr("Configured Flatpak scope") if record.source == "flatpak" else self.tr("System scope"))
        scope.setObjectName("applicationRowScope")
        scope.setWordWrap(True)
        badges.addWidget(scope)
        status = QLabel(self._state_label(eligibility.state))
        status.setObjectName("applicationStatusLabel")
        status.setWordWrap(True)
        badges.addWidget(status, 1)
        copy.addLayout(badges)
        if not eligibility.selectable:
            reason = QLabel(self.tr(eligibility.reason))
            reason.setWordWrap(True)
            copy.addWidget(reason)
        layout.addLayout(copy, 1)
        # The accessible model retains identity while the widget supplies rich copy.
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        item.setData(Qt.ItemDataRole.DisplayRole, "")
        item.setData(Qt.ItemDataRole.AccessibleTextRole, self._row_text(record, eligibility))
        item.setSizeHint(QSize(0, row.sizeHint().height()))
        self.application_list.setItemWidget(item, row)

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if event is not None and event.type() == QEvent.Type.Resize and watched is self.application_list.viewport():
            self._resize_application_rows()
        return super().eventFilter(watched, event)

    def _resize_application_rows(self) -> None:
        viewport = self.application_list.viewport()
        if viewport is None:
            return
        width = max(1, viewport.width())
        total_height = 0
        for _record, _eligibility, item in self._rows.values():
            row = self.application_list.itemWidget(item)
            layout = row.layout() if row is not None else None
            if row is not None and layout is not None:
                height = layout.totalHeightForWidth(width)
                row_height = max(row.sizeHint().height(), height)
                item.setSizeHint(QSize(0, row_height))
                total_height += row_height
        # Only the body scrolls; the catalog grows to its complete content.
        target_height = max(36, total_height + self.application_list.frameWidth() * 2)
        if self.application_list.minimumHeight() != target_height:
            self.application_list.setFixedHeight(target_height)

    def _update_review_summary(self) -> None:
        selected = self.selected_application_ids()
        if not selected:
            self.review_summary.setText(self.tr("No applications selected."))
            self.review_button.setEnabled(False)
            return
        names = [record.name for item in selected if (record := self.catalog.get(item)) is not None]
        summary_names = ", ".join(names[:3])
        if len(names) > 3:
            summary_names += self.tr(" and %1 more").replace("%1", str(len(names) - 3))
        self.review_summary.setText(self.tr("%1 selected: %2").replace("%1", str(len(names))).replace("%2", summary_names))
        self.review_summary.setToolTip(", ".join(names))
        self.review_button.setEnabled(True)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        application_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if item.checkState() is Qt.CheckState.Checked:
            self._selected_ids.add(application_id)
        else:
            self._selected_ids.discard(application_id)
        check = self._row_checks.get(application_id)
        if check is not None:
            check.blockSignals(True)
            check.setChecked(item.checkState() is Qt.CheckState.Checked)
            check.blockSignals(False)
        self._update_review_summary()

    def focus_task(self, task_id: str) -> bool:
        """Focus one application row after a goal-based search result."""
        key = str(task_id or "").strip()
        row = self._rows.get(key)
        if row is None and key.startswith("install:"):
            # Task search results identify the owning goal rather than a
            # particular application.  Focus the first matching source row so
            # keyboard users still land in a useful, bounded selection.
            if key == "install:flatpaks":
                row = next(
                    (candidate for candidate in self._rows.values() if candidate[0].source == "flatpak"),
                    None,
                )
            elif key == "install:applications":
                row = next(iter(self._rows.values()), None)
        if row is None:
            self.search_input.setFocus()
            return False
        item = row[2]
        self.application_list.setCurrentItem(item)
        widget = self.application_list.itemWidget(item)
        if widget is not None:
            self.body_scroll.ensureWidgetVisible(widget)
        self.application_list.setFocus()
        return True

    def review_selection(self) -> object | None:
        """Build and emit a bundle; no package operation is started here."""
        self._update_review_summary()
        self.state_notice.show()
        selected = self.selected_application_ids()
        if self.context is None:
            self.state_notice.set_notice(
                "warning",
                self.tr("Host verification required"),
                self.tr("Refresh the Fedora profile before reviewing an install."),
            )
            return None
        try:
            selection = self.catalog.build_selection(selected, context=self.context)
        except (KeyError, ValueError) as exc:
            self.state_notice.set_notice("warning", self.tr("Selection needs attention"), str(exc))
            return None
        self._last_bundle = selection.bundle
        self.state_notice.set_notice(
            "info",
            self.tr("Review ready"),
            self.tr("%1 independent operations are ready for confirmation.").replace("%1", str(selection.count)),
        )
        self.bundleReviewRequested.emit(selection)
        return cast(object, selection)

    def set_results(self, outcome: object) -> None:
        """Render per-application results from a BundleOutcome projection."""
        self._last_outcome = outcome
        self.results_list.clear()
        items = getattr(outcome, "items", ())
        for item in items:
            label = str(getattr(item, "status", "unknown")).replace("_", " ").title()
            item_id = str(getattr(item, "item_id", ""))
            record = self.catalog.get(item_id)
            if record is None and self._last_bundle is not None:
                bundle_item = next((candidate for candidate in getattr(self._last_bundle, "items", ()) if candidate.item_id == item_id), None)
                application_id = str(getattr(bundle_item, "metadata", {}).get("application_id", ""))
                record = self.catalog.get(application_id)
            title = record.name if record is not None else str(getattr(item, "action_id", "Application"))
            message = str(getattr(item, "message", ""))
            row = QListWidgetItem(f"{title} · {label}: {message}", self.results_list)
            row.setData(Qt.ItemDataRole.UserRole, str(getattr(item, "item_id", "")))
        self.results_list.setFixedHeight(max(36, sum(self.results_list.sizeHintForRow(index) for index in range(self.results_list.count())) + 4))
        self.results_card.setVisible(bool(items))
        self.resultUpdated.emit(outcome)
        self.refresh_installed_applications()


# Naming aliases used by adapters that call the surface a widget or tab.
InstallWorkflowWidget = InstallWorkflowPage
InstallPage = InstallWorkflowPage


__all__ = ["InstallPage", "InstallWorkflowPage", "InstallWorkflowWidget"]
