"""Cohesive master and detail presentation panes for Action Center."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from ui.components import (
    ActionCenterWorkItem,
    ConfirmationRiskPanel,
    DetailsDisclosure,
    LocalViewItem,
    LocalViewSwitcher,
    QuietButton,
    SecondaryButton,
    SectionHeader,
)


class ActionCenterMasterPane(QWidget):
    """Review-queue/catalog mode and selectable work list."""

    def __init__(self, state_groups: tuple[tuple[str, str], ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("actionCenterMasterPane")
        self.setAccessibleName(self.tr("Action Center work browser"))
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(10)
        self.body.addWidget(
            SectionHeader(
                self.tr("Work browser"),
                self.tr("Selection shows details only; it never approves or runs a change."),
            )
        )
        self.mode_switcher = LocalViewSwitcher()
        self.mode_switcher.setObjectName("actionCenterModeSwitcher")
        self.mode_switcher.set_views(
            [
                LocalViewItem(
                    "queue",
                    self.tr("Review queue"),
                    self.tr("Work that currently needs attention."),
                ),
                LocalViewItem(
                    "catalog",
                    self.tr("Action catalog"),
                    self.tr("Browse available actions without creating a plan."),
                ),
            ]
        )
        self.body.addWidget(self.mode_switcher)
        self.lifecycle_controls = QWidget()
        lifecycle_layout = QVBoxLayout(self.lifecycle_controls)
        lifecycle_layout.setContentsMargins(0, 0, 0, 0)
        lifecycle_label = QLabel(self.tr("Work status"))
        self.lifecycle_view = QComboBox()
        self.lifecycle_view.setAccessibleName(self.tr("Action Center work status"))
        lifecycle_label.setBuddy(self.lifecycle_view)
        for group_id, label in state_groups:
            self.lifecycle_view.addItem(self.tr(label), group_id)
        lifecycle_layout.addWidget(lifecycle_label)
        lifecycle_layout.addWidget(self.lifecycle_view)
        self.body.addWidget(self.lifecycle_controls)
        self.action_list = QListWidget()
        self.action_list.setObjectName("actionCenterWorkList")
        self.action_list.setAccessibleName(self.tr("Action Center work list"))
        self.body.addWidget(self.action_list, 1)

    def add_work_item(
        self,
        item_id: str,
        title: str,
        summary: str,
        *,
        status: str,
        status_kind: str = "neutral",
    ) -> None:
        item = QListWidgetItem(title)
        widget = ActionCenterWorkItem(
            item_id,
            title,
            summary,
            status=status,
            status_kind=status_kind,
        )
        item.setSizeHint(widget.sizeHint())
        self.action_list.addItem(item)
        self.action_list.setItemWidget(item, widget)
        widget.selected.connect(lambda _item_id, row=item: self.action_list.setCurrentItem(row))

    def populate_catalog(self, items: Iterable[Any]) -> None:
        self.action_list.clear()
        for item in items:
            manual_only = bool(getattr(item, "manual_only", False))
            self.add_work_item(
                str(getattr(item, "id", "")),
                str(getattr(item, "title", "")),
                str(getattr(item, "description", "")),
                status=self.tr("Manual guidance") if manual_only else self.tr("Available"),
                status_kind="warning" if manual_only else "neutral",
            )

    def add_record(
        self,
        kind: str,
        record: Any,
        action_title: Callable[[str], str],
    ) -> None:
        if kind == "candidate":
            manual_only = bool(getattr(record, "manual_only", False))
            self.add_work_item(
                str(record.id),
                str(record.title),
                str(getattr(record, "description", "")),
                status=self.tr("Manual guidance") if manual_only else self.tr("Create plan"),
                status_kind="warning" if manual_only else "neutral",
            )
            return
        state = str(record.state)
        title = action_title(str(record.action_id))
        if kind == "plan":
            self.add_work_item(
                str(record.plan_id),
                title,
                ", ".join(record.affected_resources) or self.tr("System"),
                status=self.tr(state.replace("_", " ").title()),
            )
            return
        self.add_work_item(
            str(record.run_id),
            title,
            self.tr("Recorded Action Center run"),
            status=self.tr(state.replace("_", " ").title()),
            status_kind="success" if state == "succeeded" else "error" if state in {"failed", "cancelled"} else "neutral",
        )


class ActionCenterDetailPane(QWidget):
    """Selected work evidence, risk facts, and progressive technical detail."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("actionCenterDetailPane")
        self.setAccessibleName(self.tr("Selected Action Center work details"))
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(10)
        self.body.addWidget(
            SectionHeader(
                self.tr("Selected item"),
                self.tr("Review scope and safety evidence before preparing or running a plan."),
            )
        )
        self.risk_panel = ConfirmationRiskPanel(
            self.tr("Safety review"),
            self.tr("Risk and validation come from the selected catalog item or persisted plan."),
        )
        self.body.addWidget(self.risk_panel)
        self.selected_summary = QLabel(
            self.tr("Select a change to review its outcome and safety details.")
        )
        self.selected_summary.setObjectName("actionCenterSelectedSummary")
        self.selected_summary.setAccessibleName(self.tr("Selected change summary"))
        self.selected_summary.setWordWrap(True)
        self.body.addWidget(self.selected_summary)
        self.detail_disclosure = DetailsDisclosure(summary=self.tr("Show technical details"))
        self.detail_area = self.detail_disclosure.details
        self.detail_area.setAccessibleName(self.tr("Selected change technical details"))
        self.body.addWidget(self.detail_disclosure, 1)

    def apply_details(self, details: Any) -> None:
        """Apply safety facts, plain summary, and technical disclosure."""
        self.risk_panel.set_review_facts(
            risk=details.risk,
            scope=details.scope,
            requirements=details.requirements,
            validation=details.validation,
            rollback=details.rollback,
        )
        self.set_selected_details(
            list(details.summary_lines),
            list(details.technical_lines),
        )

    def set_selected_details(
        self,
        summary_lines: list[str],
        technical_lines: list[str],
    ) -> None:
        """Keep user outcome and safety facts visible above technical metadata."""
        self.selected_summary.setText("\n".join(summary_lines))
        self.detail_area.setPlainText("\n".join(technical_lines))


class ActionCenterControls(QWidget):
    """Encapsulates advanced reload, preview, history, and catalog controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("actionCenterControls")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        target_load_row = QHBoxLayout()
        self.load_stable_button = SecondaryButton(
            self.tr("Reload Fedora %s Actions") % FEDORA_RELEASE_POLICY.stable_release
        )
        target_load_row.addWidget(self.load_stable_button)

        self.load_preview_button = SecondaryButton(
            self.tr("Load Fedora %s Preview Actions") % FEDORA_RELEASE_POLICY.preview_release
        )
        self.load_preview_button.hide()

        self.preview_button = QuietButton(self.tr("Preview Selected"))
        target_load_row.addWidget(self.preview_button)

        self.history_button = QuietButton(self.tr("Show History"))
        target_load_row.addWidget(self.history_button)
        target_load_row.addStretch()

        catalog_row = QHBoxLayout()
        catalog_label = QLabel(self.tr("Available advanced action"))
        self.catalog_selector = QComboBox()
        self.catalog_selector.setAccessibleName(self.tr("Available advanced Action Center action"))
        catalog_row.addWidget(catalog_label)
        catalog_row.addWidget(self.catalog_selector, 1)

        self.target_guidance = QLabel(
            self.tr("Fedora %s preview target choices are available in Upgrade Assistant.")
            % FEDORA_RELEASE_POLICY.preview_release
        )
        self.target_guidance.setObjectName("actionCenterTargetGuidance")
        self.target_guidance.setWordWrap(True)
        self.target_guidance.setAccessibleName(self.tr("Release target guidance"))

        layout.addLayout(target_load_row)
        layout.addLayout(catalog_row)
        layout.addWidget(self.target_guidance)


__all__ = ["ActionCenterControls", "ActionCenterDetailPane", "ActionCenterMasterPane"]
