"""Reusable task, filter, risk, application, and review-item presentation."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components.actions import PrimaryButton
from ui.components.cards import Card, DefinitionList
from ui.components.feedback import StatusBadge
from ui.icon_pack import get_semantic_icon


class SearchFilterRow(QFrame):
    """One accessible search field followed by caller-owned filter controls."""

    searchChanged = pyqtSignal(str)

    def __init__(
        self,
        placeholder: str,
        *,
        accessible_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("searchFilterRow")
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(10)
        self.search = QLineEdit()
        self.search.setObjectName("searchFilterInput")
        self.search.setPlaceholderText(placeholder)
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName(accessible_name or self.tr("Search"))
        self.search.setAccessibleDescription(placeholder)
        self.search.setMinimumWidth(220)
        self.search.textChanged.connect(self.searchChanged)
        self.row.addWidget(self.search, 1)
        self.setAccessibleName(self.tr("Search and filters"))

    def add_filter(self, control: QWidget, *, accessible_name: str = "") -> None:
        if accessible_name:
            control.setAccessibleName(accessible_name)
        self.row.addWidget(control)

    def add_choice_filter(
        self,
        accessible_name: str,
        choices: tuple[tuple[str, object], ...],
    ) -> QComboBox:
        control = QComboBox()
        control.setAccessibleName(accessible_name)
        for label, value in choices:
            control.addItem(label, value)
        self.add_filter(control)
        return control


class TaskSummary(Card):
    """Compact task/result summary with named facts and one current status."""

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        status: str = "",
        status_kind: str = "neutral",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, description, parent)
        self.setObjectName("taskSummary")
        self.status_badge = StatusBadge(status, kind=status_kind)
        self.status_badge.setVisible(bool(status))
        self.add_widget(self.status_badge)
        self.facts = DefinitionList("")
        self.facts.setVisible(False)
        self.add_widget(self.facts)

    def add_fact(self, label: str, value: str, description: str = "") -> None:
        self.facts.add_row(label, value, description=description)
        self.facts.setVisible(True)

    def set_status(self, text: str, *, kind: str = "neutral", description: str = "") -> None:
        self.status_badge.set_status(text, kind=kind, description=description)
        self.status_badge.setVisible(bool(text))


class ConfirmationRiskPanel(TaskSummary):
    """Risk, scope, validation, and rollback summary before explicit execution."""

    def __init__(self, title: str, description: str = "", parent: QWidget | None = None) -> None:
        super().__init__(title, description, status=self.tr("Review required"), status_kind="warning", parent=parent)
        self.setObjectName("confirmationRiskPanel")

    def set_review_facts(
        self,
        *,
        risk: str,
        scope: str,
        requirements: str,
        validation: str,
        rollback: str,
    ) -> None:
        while self.facts.body.count() > 2:
            item = self.facts.body.takeAt(2)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.facts.setVisible(False)
        for label, value in (
            (self.tr("Risk"), risk),
            (self.tr("Affected scope"), scope),
            (self.tr("Requirements"), requirements),
            (self.tr("Validation"), validation),
            (self.tr("Rollback"), rollback),
        ):
            self.add_fact(label, value)


class ApplicationRow(QFrame):
    """Application identity, source/status, feedback, and one primary action."""

    actionRequested = pyqtSignal(str)

    def __init__(
        self,
        app_id: str,
        title: str,
        description: str,
        *,
        source: str,
        status: str,
        status_kind: str,
        action_text: str,
        action_id: str,
        icon: QIcon | None = None,
        plan_summary: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_id = app_id
        self.action_id = action_id
        self.setObjectName("applicationRow")
        self.setProperty("applicationId", app_id)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 12, 12, 12)
        row.setSpacing(12)
        icon_label = QLabel()
        icon_label.setObjectName("applicationRowIcon")
        app_icon = icon if icon is not None and not icon.isNull() else get_semantic_icon("application", size=32)
        icon_label.setPixmap(app_icon.pixmap(32, 32))
        row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        copy = QVBoxLayout()
        copy.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("applicationRowTitle")
        self.description_label = QLabel(description)
        self.description_label.setObjectName("applicationRowDescription")
        self.description_label.setWordWrap(True)
        self.plan_label = QLabel(plan_summary)
        self.plan_label.setObjectName("applicationPlanSummary")
        self.plan_label.setWordWrap(True)
        self.plan_label.setVisible(bool(plan_summary))
        copy.addWidget(self.title_label)
        copy.addWidget(self.description_label)
        copy.addWidget(self.plan_label)
        row.addLayout(copy, 1)
        self.source_badge = StatusBadge(
            self.tr("Source: %1").replace("%1", source),
            kind="info",
        )
        self.source_badge.setObjectName("applicationSourceBadge")
        row.addWidget(self.source_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.status_badge = StatusBadge(status, kind=status_kind)
        self.status_badge.setObjectName("applicationStatusBadge")
        row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.action_button = PrimaryButton(action_text, description=self.tr("Review this application action"))
        self.action_button.setVisible(bool(action_text))
        self.action_button.clicked.connect(lambda: self.actionRequested.emit(self.action_id))
        row.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setAccessibleName(title)
        self.setAccessibleDescription(
            self.tr("%1. Source: %2. Status: %3").replace("%1", description).replace("%2", source).replace("%3", status)
        )

    def set_feedback(self, message: str, *, kind: str) -> None:
        self.status_badge.set_status(message, kind=kind, description=message)


class ActionCenterWorkItem(QFrame):
    """Keyboard-selectable master-list item; selection never implies approval."""

    selected = pyqtSignal(str)

    def __init__(
        self,
        item_id: str,
        title: str,
        summary: str,
        *,
        status: str,
        status_kind: str = "neutral",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self.setObjectName("actionCenterWorkItem")
        self.setProperty("selected", False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)
        header = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("workItemTitle")
        header.addWidget(self.title_label, 1)
        self.status_badge = StatusBadge(status, kind=status_kind)
        header.addWidget(self.status_badge)
        layout.addLayout(header)
        self.summary_label = QLabel(summary)
        self.summary_label.setObjectName("workItemSummary")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.setAccessibleName(title)
        self.setAccessibleDescription(self.tr("Select to review details. %1").replace("%1", summary))

    def activate(self) -> None:
        if self.isEnabled():
            self.selected.emit(self.item_id)

    def keyPressEvent(self, event) -> None:
        if event is not None and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            self.activate()
            event.accept()
            return
        super().keyPressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.activate()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", bool(selected))
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
