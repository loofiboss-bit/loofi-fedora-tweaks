"""Presentation-only Tune profile editor for the v29 utility shell."""

from __future__ import annotations

from typing import Any

from core.catalog_models import CapabilityState
from core.tasks import TaskContext, TuneCatalog, TuneProfile, TuneSelection
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ui.components import Card, InlineNotice, PageScaffold, PrimaryButton, SectionHeader


class TuneWorkflowPage(QWidget):
    """Editable Minimal/Recommended/Power User selection with review output."""

    bundleReviewRequested = pyqtSignal(object)
    resultUpdated = pyqtSignal(object)

    def __init__(
        self,
        *,
        catalog: TuneCatalog | None = None,
        context: TaskContext | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog or TuneCatalog()
        self.context = context
        self._rows: dict[str, tuple[object, object, QListWidgetItem]] = {}
        self._last_selection: TuneSelection | None = None
        self._last_outcome: object | None = None
        self.setObjectName("tuneWorkflowPage")
        self.setAccessibleName(self.tr("Tune Fedora"))
        self.setAccessibleDescription(self.tr("Choose and review a safe Fedora tuning profile."))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Tune"),
            self.tr("Start with a reviewed profile, edit its low-risk operations, and verify the result."),
        )
        root.addWidget(self.scaffold)

        self.profile_card = Card(
            self.tr("Choose a profile"),
            self.tr("Profiles contain only implemented, independently verifiable low-risk operations."),
        )
        self.scaffold.add_widget(self.profile_card)
        self.profile_selector = QComboBox()
        self.profile_selector.setObjectName("tuneProfileSelector")
        self.profile_selector.setAccessibleName(self.tr("Tune profile"))
        for profile in self.catalog.profiles():
            self.profile_selector.addItem(profile.title, profile.id)
        self.profile_selector.currentIndexChanged.connect(self._refresh_rows)
        self.profile_card.add_widget(self.profile_selector)
        self.profile_description = QLabel()
        self.profile_description.setObjectName("tuneProfileDescription")
        self.profile_description.setWordWrap(True)
        self.profile_card.add_widget(self.profile_description)
        self.state_notice = InlineNotice(
            self.tr("Review required"),
            self.tr("Choose the operations you want to apply; nothing starts until you confirm the review."),
            kind="info",
        )
        self.state_notice.setObjectName("tuneWorkflowState")
        self.profile_card.add_widget(self.state_notice)

        self.operation_list = QListWidget()
        self.operation_list.setObjectName("tuneOperationList")
        self.operation_list.setAccessibleName(self.tr("Tune operations"))
        self.operation_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.operation_list.itemChanged.connect(self._on_item_changed)
        self.scaffold.add_widget(SectionHeader(self.tr("Profile operations"), self.tr("Unavailable operations stay visible with an explanation.")))
        self.scaffold.add_widget(self.operation_list, 1)

        self.review_card = Card(
            self.tr("Review profile"),
            self.tr("Tune operations run in order and stop after the first unexpected failure."),
        )
        self.review_card.setObjectName("tuneReviewCard")
        self.review_summary = QLabel()
        self.review_summary.setObjectName("tuneReviewSummary")
        self.review_summary.setWordWrap(True)
        self.review_card.add_widget(self.review_summary)
        self.review_button = PrimaryButton(
            self.tr("Review Tune profile"),
            description=self.tr("Create a stop-on-error bundle without applying changes."),
        )
        self.review_button.setObjectName("tuneReviewButton")
        self.review_button.clicked.connect(self.review_selection)
        self.review_card.add_widget(self.review_button)
        self.scaffold.add_widget(self.review_card)

        self.results_card = Card(
            self.tr("Results"),
            self.tr("Review every operation and follow recovery guidance where needed."),
        )
        self.results_card.setObjectName("tuneResultsCard")
        self.results_list = QListWidget()
        self.results_list.setObjectName("tuneResultsList")
        self.results_card.add_widget(self.results_list)
        self.results_card.hide()
        self.scaffold.add_widget(self.results_card)
        self.scaffold.content_layout.addStretch()
        self._refresh_rows()

    @property
    def profile(self) -> TuneProfile | None:
        return self.catalog.get_profile(str(self.profile_selector.currentData() or ""))

    @property
    def last_selection(self) -> TuneSelection | None:
        return self._last_selection

    def set_context(self, context: TaskContext | None) -> None:
        self.context = context
        self._refresh_rows()

    def selected_task_ids(self) -> tuple[str, ...]:
        return tuple(
            task_id
            for task_id, (_task, _eligibility, item) in self._rows.items()
            if item.checkState() is Qt.CheckState.Checked
        )

    def _refresh_rows(self, *_args: Any) -> None:
        profile = self.profile
        previous = set(self.selected_task_ids()) if self._rows else set()
        self.operation_list.clear()
        self._rows.clear()
        if profile is None:
            self.profile_description.clear()
            self.review_button.setEnabled(False)
            return
        self.profile_description.setText(profile.description)
        context = self.context
        if context is None:
            # A missing context is a discovery state only; execution remains
            # fail-closed until MainWindow supplies a verified TaskContext.
            rows = self.catalog.profile_tasks(profile, context=None)
        else:
            rows = self.catalog.selectable_tasks(profile, context=context)
        for task, eligibility in rows:
            state = str(getattr(eligibility.state, "value", eligibility.state))
            label = {
                CapabilityState.SUPPORTED.value: "Ready",
                CapabilityState.UNAVAILABLE.value: "Unavailable",
                CapabilityState.PENDING_REBOOT.value: "Continue after reboot",
            }.get(state, state.replace("_", " ").title())
            item = QListWidgetItem(f"{task.title} · {label}", self.operation_list)
            item.setData(Qt.ItemDataRole.UserRole, task.id)
            item.setToolTip(eligibility.reason)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            selectable = context is None or eligibility.state is CapabilityState.SUPPORTED
            if selectable:
                item.setCheckState(Qt.CheckState.Checked if task.id in previous else Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._rows[task.id] = (task, eligibility, item)
        self._update_review_summary()

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        self._update_review_summary()

    def focus_task(self, task_id: str) -> bool:
        """Focus one profile operation after a goal-based search result."""
        key = str(task_id or "").strip()
        row = self._rows.get(key)
        if row is None:
            # A task search result can point at the Tune landing goal itself
            # or at a desktop handoff that is intentionally omitted from
            # automatic profiles.  Keep the focus in the profile editor so
            # the user can review the safe choices without a dead end.
            if key in {"tune", "tune:desktop", "tune:storage-trim", "tune:package-cache"}:
                self.profile_selector.setFocus()
                return True
            return False
        self.operation_list.setCurrentItem(row[2])
        self.operation_list.setFocus()
        return True

    def _update_review_summary(self) -> None:
        selected = self.selected_task_ids()
        self.review_summary.setText(
            self.tr("%1 operations selected.").replace("%1", str(len(selected)))
            if selected
            else self.tr("No operations selected.")
        )
        self.review_button.setEnabled(bool(selected) and self.context is not None)

    def review_selection(self) -> TuneSelection | None:
        if self.context is None:
            self.state_notice.set_notice(
                "warning",
                self.tr("Host verification required"),
                self.tr("Refresh the Fedora profile before reviewing a Tune profile."),
            )
            return None
        profile = self.profile
        if profile is None:
            return None
        try:
            selection = self.catalog.build_selection(
                profile,
                context=self.context,
                selected_task_ids=self.selected_task_ids(),
            )
        except (KeyError, ValueError) as exc:
            self.state_notice.set_notice("warning", self.tr("Profile needs attention"), str(exc))
            return None
        self._last_selection = selection
        self.state_notice.set_notice(
            "info",
            self.tr("Review ready"),
            self.tr("%1 ordered operations are ready for confirmation.").replace("%1", str(selection.count)),
        )
        self.bundleReviewRequested.emit(selection)
        return selection

    def set_results(self, outcome: object) -> None:
        self._last_outcome = outcome
        self.results_list.clear()
        for item in getattr(outcome, "items", ()):
            status = str(getattr(item, "status", "unknown")).replace("_", " ").title()
            title = str(getattr(item, "action_id", "Tune operation"))
            message = str(getattr(item, "message", ""))
            QListWidgetItem(f"{title} · {status}: {message}", self.results_list)
        self.results_card.setVisible(bool(getattr(outcome, "items", ())))
        self.resultUpdated.emit(outcome)


TuneWorkflowWidget = TuneWorkflowPage
TunePage = TuneWorkflowPage


__all__ = ["TunePage", "TuneWorkflowPage", "TuneWorkflowWidget"]
