"""Presentation-only Install workflow for the v29 utility shell.

The widget owns discovery, filtering, selection, and review presentation. It
never invokes a package manager. ``bundleReviewRequested`` is the hand-off to
the shared operation controller owned by the application shell.
"""

from __future__ import annotations

from typing import Any

from core.tasks import (
    ApplicationCatalog,
    ApplicationContext,
    ApplicationEligibility,
    ApplicationRecord,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QLabel, QListWidget, QListWidgetItem, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.components import Card, InlineNotice, PageScaffold, PrimaryButton, SectionHeader


class InstallWorkflowPage(QWidget):
    """Searchable curated application selection with an explicit review step."""

    bundleReviewRequested = pyqtSignal(object)
    resultUpdated = pyqtSignal(object)
    # Compatibility signal for older route adapters.  It is never rendered as
    # a normal CTA; the visible review button always owns this page's primary
    # action.
    routeRequested = pyqtSignal(str)

    def __init__(
        self,
        *,
        catalog: ApplicationCatalog | None = None,
        context: ApplicationContext | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog or ApplicationCatalog()
        self.context = context
        self._rows: dict[str, tuple[ApplicationRecord, ApplicationEligibility, QListWidgetItem]] = {}
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
        root.addWidget(self.scaffold)

        self.intro = Card(
            self.tr("Curated applications"),
            self.tr("Flatpak is preferred for ordinary GUI applications. Fedora RPM is used for trusted CLI and system tools."),
        )
        self.scaffold.add_widget(self.intro)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("installApplicationSearch")
        self.search_input.setPlaceholderText(self.tr("Search applications…"))
        self.search_input.setAccessibleName(self.tr("Search applications"))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_rows)
        self.intro.add_widget(self.search_input)
        self.category_filter = QComboBox()
        self.category_filter.setObjectName("installCategoryFilter")
        self.category_filter.setAccessibleName(self.tr("Application category"))
        self.category_filter.addItem(self.tr("All categories"), "")
        for category in self.catalog.categories():
            self.category_filter.addItem(category, category)
        self.category_filter.currentIndexChanged.connect(self._refresh_rows)
        self.intro.add_widget(self.category_filter)

        self.state_notice = InlineNotice(
            self.tr("Select applications"),
            self.tr("Choose one or more applications, then review the exact sources and identifiers."),
            kind="info",
        )
        self.state_notice.setObjectName("installWorkflowState")
        self.intro.add_widget(self.state_notice)

        self.application_list = QListWidget()
        self.application_list.setObjectName("installApplicationList")
        self.application_list.setAccessibleName(self.tr("Curated application catalog"))
        self.application_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.application_list.itemChanged.connect(self._on_item_changed)
        self.scaffold.add_widget(SectionHeader(self.tr("Available applications"), self.tr("Selection never starts an operation.")))
        self.scaffold.add_widget(self.application_list, 1)

        self.review_card = Card(
            self.tr("Review selection"),
            self.tr("Every selected application is an independent operation. One failure does not hide the others."),
        )
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
        self.scaffold.add_widget(self.review_card)

        self.results_card = Card(
            self.tr("Results"),
            self.tr("Each application keeps its own terminal result and recovery guidance."),
        )
        self.results_card.setObjectName("installResultsCard")
        self.results_list = QListWidget()
        self.results_list.setObjectName("installResultsList")
        self.results_list.setAccessibleName(self.tr("Application install results"))
        self.results_card.add_widget(self.results_list)
        self.results_card.hide()
        self.scaffold.add_widget(self.results_card)
        self.scaffold.content_layout.addStretch()
        self._refresh_rows()

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
        self._refresh_rows()

    def selected_application_ids(self) -> tuple[str, ...]:
        return tuple(
            application_id
            for application_id, (_record, _eligibility, item) in self._rows.items()
            if item.checkState() is Qt.CheckState.Checked
        )

    def _refresh_rows(self, *_args: Any) -> None:
        previous = set(self.selected_application_ids()) if self._rows else set()
        query = self.search_input.text()
        category = str(self.category_filter.currentData() or "")
        self.application_list.clear()
        self._rows.clear()
        for record, eligibility in self.catalog.search(query, category=category, context=self.context):
            item = QListWidgetItem(self._row_text(record, eligibility), self.application_list)
            item.setData(Qt.ItemDataRole.UserRole, record.id)
            item.setToolTip(eligibility.reason)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if eligibility.selectable:
                item.setCheckState(Qt.CheckState.Checked if record.id in previous else Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._rows[record.id] = (record, eligibility, item)
        self._update_review_summary()

    @staticmethod
    def _row_text(record: ApplicationRecord, eligibility: ApplicationEligibility) -> str:
        state = {
            "available": "Ready",
            "advanced": "Advanced · reboot may be required",
            "installed": "Installed",
            "offline": "Offline",
            "unavailable": "Unavailable",
        }.get(eligibility.state, eligibility.state)
        return f"{record.name} · {record.source_label} · {state}"

    def _update_review_summary(self) -> None:
        selected = self.selected_application_ids()
        if not selected:
            self.review_summary.setText(self.tr("No applications selected."))
            self.review_button.setEnabled(False)
            return
        names = [self._rows[item][0].name for item in selected if item in self._rows]
        self.review_summary.setText(
            self.tr("%1 selected: %2").replace("%1", str(len(names))).replace("%2", ", ".join(names))
        )
        self.review_button.setEnabled(True)

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
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
        self.application_list.setFocus()
        return True

    def review_selection(self) -> object | None:
        """Build and emit a bundle; no package operation is started here."""
        self._update_review_summary()
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
        return selection

    def set_results(self, outcome: object) -> None:
        """Render per-application results from a BundleOutcome projection."""
        self._last_outcome = outcome
        self.results_list.clear()
        items = getattr(outcome, "items", ())
        for item in items:
            label = str(getattr(item, "status", "unknown")).replace("_", " ").title()
            title = str(getattr(item, "action_id", "Application"))
            message = str(getattr(item, "message", ""))
            row = QListWidgetItem(f"{title} · {label}: {message}", self.results_list)
            row.setData(Qt.ItemDataRole.UserRole, str(getattr(item, "item_id", "")))
        self.results_card.setVisible(bool(items))
        self.resultUpdated.emit(outcome)


# Naming aliases used by adapters that call the surface a widget or tab.
InstallWorkflowWidget = InstallWorkflowPage
InstallPage = InstallWorkflowPage


__all__ = ["InstallPage", "InstallWorkflowPage", "InstallWorkflowWidget"]
