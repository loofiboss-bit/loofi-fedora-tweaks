"""Development-only gallery for the v16 shared component contract."""

from __future__ import annotations

from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.components import (
    ActionBar,
    ActionProgress,
    Card,
    ClickableCard,
    DangerButton,
    DefinitionList,
    DetailsDisclosure,
    EmptyState,
    GhostButton,
    InlineNotice,
    LoadingState,
    PageHeader,
    PageScaffold,
    PrimaryButton,
    SecondaryButton,
    SectionItem,
    SectionNavigator,
    StatusBadge,
    UnavailableState,
)


class ComponentGallery(QWidget):
    """Render every Phase 2 component without product routes or domain work."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("v16ComponentGallery")
        self.setAccessibleName(self.tr("Shared component gallery"))
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = PageHeader(self)
        self.header.set_content(
            self.tr("Development preview"),
            self.tr("Shared components"),
            self.tr("Keyboard, accessibility, theme, and font-scale fixture."),
        )
        self.header_action = SecondaryButton(
            self.tr("Header action"),
            description=self.tr("Example caller-owned page action"),
        )
        self.header.add_action(self.header_action, primary=True)
        root.addWidget(self.header)

        self.scaffold = PageScaffold(
            self.tr("Shared component content"),
            self.tr("Development-only presentation fixture"),
            parent=self,
        )
        root.addWidget(self.scaffold, 1)

        self.navigator = SectionNavigator(self)
        self.navigator.set_sections(
            [
                SectionItem(
                    "overview",
                    self.tr("Overview and current system status"),
                    self.tr("Summary of saved Fedora state"),
                    self.tr("Ready"),
                ),
                SectionItem(
                    "actions",
                    self.tr("Actions and maintenance controls"),
                    self.tr("Caller-owned controls only"),
                ),
                SectionItem(
                    "details",
                    self.tr("Technical details and operation history"),
                    self.tr("Read-only technical information"),
                ),
            ]
        )
        self.scaffold.add_widget(self.navigator)

        card_grid = QGridLayout()
        card_grid.setContentsMargins(0, 0, 0, 0)
        card_grid.setHorizontalSpacing(16)
        card_grid.setVerticalSpacing(16)
        self.card = Card(
            self.tr("Current state"),
            self.tr("A bounded surface with concise supporting text."),
        )
        self.card.add_widget(QLabel(self.tr("Fedora state is available.")))
        self.clickable_card = ClickableCard(
            self.tr("Review updates"),
            self.tr("Open the existing update workflow without running an action."),
            "maintenance:updates",
        )
        card_grid.addWidget(self.card, 0, 0)
        card_grid.addWidget(self.clickable_card, 0, 1)
        self.scaffold.add_layout(card_grid)

        self.definition_list = DefinitionList(
            self.tr("System properties"),
            self.tr("Labels stay close to selectable values."),
        )
        self.definition_row = self.definition_list.add_row(
            self.tr("Operating system"),
            self.tr("Fedora Linux"),
            copyable=True,
        )
        self.definition_list.add_row(
            self.tr("Very long translated property label"),
            self.tr("A value that remains readable at increased font scaling"),
        )
        self.scaffold.add_widget(self.definition_list)

        self.action_bar = ActionBar(self)
        self.primary_button = PrimaryButton(
            self.tr("Apply"),
            description=self.tr("Apply the reviewed change"),
        )
        self.secondary_button = SecondaryButton(
            self.tr("Review"),
            description=self.tr("Review details before applying"),
        )
        self.ghost_button = GhostButton(
            self.tr("Cancel"),
            description=self.tr("Leave this workflow unchanged"),
        )
        self.danger_button = DangerButton(
            self.tr("Remove"),
            description=self.tr("Remove the selected item after confirmation"),
        )
        self.action_bar.add_action(self.ghost_button)
        self.action_bar.add_action(self.secondary_button)
        self.action_bar.add_action(self.danger_button, primary=True)
        self.action_bar.add_action(self.primary_button, primary=True)
        self.scaffold.add_widget(self.action_bar)

        badges = QHBoxLayout()
        self.badges = [
            StatusBadge(self.tr("Information"), kind="info"),
            StatusBadge(self.tr("Ready"), kind="success"),
            StatusBadge(self.tr("Needs attention"), kind="warning"),
            StatusBadge(self.tr("Failed"), kind="error"),
        ]
        for badge in self.badges:
            badges.addWidget(badge)
        badges.addStretch()
        self.scaffold.add_layout(badges)

        self.notice = InlineNotice(
            self.tr("Review required"),
            self.tr("Read the saved plan before continuing."),
            kind="warning",
        )
        self.loading = LoadingState(self.tr("Reading saved status"))
        self.empty = EmptyState(
            self.tr("No saved plans"),
            self.tr("Create a plan from the existing Action Center workflow."),
            action_text=self.tr("Open Action Center"),
        )
        self.unavailable = UnavailableState(
            self.tr("Capability unavailable"),
            self.tr("Install the required Fedora component to continue."),
        )
        self.progress = ActionProgress(self.tr("Waiting for caller-owned work"))
        self.disclosure = DetailsDisclosure(
            self.tr("No command has been run."),
            summary=self.tr("Show technical details"),
        )
        for widget in (
            self.notice,
            self.loading,
            self.empty,
            self.unavailable,
            self.progress,
            self.disclosure,
        ):
            self.scaffold.add_widget(widget)
        self.scaffold.content_layout.addStretch()
