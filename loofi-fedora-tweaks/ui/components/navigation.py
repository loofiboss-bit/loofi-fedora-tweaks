"""Presentation-only responsive section navigation."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.icon_pack import get_qicon


@dataclass(frozen=True)
class SectionItem:
    """Data-only presentation metadata for one section."""

    section_id: str
    label: str
    description: str = ""
    status: str = ""
    icon: str = ""
    group: str = ""


class SectionNavigator(QFrame):
    """Full-label rail with an accessible narrow selector fallback."""

    sectionActivated = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionNavigator")
        self.setAccessibleName(self.tr("Sections"))
        self._sections: tuple[SectionItem, ...] = ()
        self._suppress_signal = False
        self._compact = False
        self._filtering_enabled = False
        self._visible_section_indexes: tuple[int, ...] = ()
        self._rail_section_indexes: dict[int, int] = {}
        self._group_buttons: list[QPushButton] = []
        self._overview_active = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.filter_panel = QFrame(self)
        self.filter_panel.setObjectName("sectionFilterPanel")
        filter_layout = QVBoxLayout(self.filter_panel)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)
        self.filter_input = QLineEdit(self.filter_panel)
        self.filter_input.setObjectName("sectionFilter")
        self.filter_input.setAccessibleName(self.tr("Filter specialist tools"))
        self.filter_input.setPlaceholderText(self.tr("Filter specialist tools"))
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._rebuild_visible_sections)
        filter_layout.addWidget(self.filter_input)
        self.group_filter = QComboBox(self.filter_panel)
        self.group_filter.setObjectName("sectionGroupFilter")
        self.group_filter.setAccessibleName(self.tr("Specialist tool group"))
        self.group_filter.currentIndexChanged.connect(self._rebuild_visible_sections)
        filter_layout.addWidget(self.group_filter)
        layout.addWidget(self.filter_panel)
        self.filter_panel.hide()

        self.group_overview = QFrame(self)
        self.group_overview.setObjectName("sectionGroupOverview")
        overview_layout = QVBoxLayout(self.group_overview)
        overview_layout.setContentsMargins(16, 16, 16, 16)
        overview_layout.setSpacing(8)
        self.overview_title = QLabel(self.tr("Specialist tool groups"))
        self.overview_title.setObjectName("sectionOverviewTitle")
        self.overview_description = QLabel(
            self.tr("Choose a group below, or search all specialist tools.")
        )
        self.overview_description.setObjectName("sectionOverviewDescription")
        self.overview_description.setWordWrap(True)
        self.group_button_grid = QGridLayout()
        self.group_button_grid.setContentsMargins(0, 4, 0, 0)
        self.group_button_grid.setSpacing(8)
        overview_layout.addWidget(self.overview_title)
        overview_layout.addWidget(self.overview_description)
        overview_layout.addLayout(self.group_button_grid)
        layout.addWidget(self.group_overview)
        self.group_overview.hide()

        self.match_count = QLabel()
        self.match_count.setObjectName("sectionMatchCount")
        self.match_count.setAccessibleName(self.tr("Specialist tool search results"))
        layout.addWidget(self.match_count)
        self.match_count.hide()

        self.no_results = QFrame(self)
        self.no_results.setObjectName("sectionNoResults")
        no_results_layout = QVBoxLayout(self.no_results)
        no_results_layout.setContentsMargins(16, 16, 16, 16)
        self.no_results_title = QLabel(self.tr("No specialist tools found"))
        self.no_results_title.setObjectName("stateTitle")
        self.no_results_message = QLabel(
            self.tr("Try another search term or choose All groups.")
        )
        self.no_results_message.setObjectName("stateMessage")
        self.no_results_message.setWordWrap(True)
        no_results_layout.addWidget(self.no_results_title)
        no_results_layout.addWidget(self.no_results_message)
        layout.addWidget(self.no_results)
        self.no_results.hide()

        self.rail = QListWidget(self)
        self.rail.setObjectName("sectionRail")
        self.rail.setAccessibleName(self.tr("Sections"))
        self.rail.setWordWrap(True)
        self.rail.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.rail.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rail.currentRowChanged.connect(self._on_rail_changed)
        layout.addWidget(self.rail)

        self.selector = QComboBox(self)
        self.selector.setObjectName("sectionSelector")
        self.selector.setAccessibleName(self.tr("Section"))
        self.selector.currentIndexChanged.connect(self._on_selector_changed)
        self.selector.hide()
        layout.addWidget(self.selector)
        self._apply_mode(False)

    def set_sections(self, sections: tuple[SectionItem, ...] | list[SectionItem]) -> None:
        self._suppress_signal = True
        self._sections = tuple(sections)
        self._populate_group_filter()
        self._populate_group_overview()
        self._overview_active = self._filtering_enabled
        self._rebuild_visible_sections()
        self._suppress_signal = False

    def set_filtering_enabled(self, enabled: bool) -> None:
        """Expose local grouping and filtering without changing route identity."""
        enabled = bool(enabled)
        if self._filtering_enabled == enabled:
            return
        self._filtering_enabled = enabled
        self.filter_panel.setVisible(enabled)
        self._overview_active = enabled
        if not enabled:
            self.filter_input.clear()
            self.group_filter.setCurrentIndex(0)
        self._rebuild_visible_sections()

    def filtering_enabled(self) -> bool:
        return self._filtering_enabled

    def filter_text(self) -> str:
        return self.filter_input.text()

    def available_groups(self) -> tuple[str, ...]:
        return tuple(
            str(self.group_filter.itemData(index) or "")
            for index in range(1, self.group_filter.count())
        )

    def visible_section_ids(self) -> tuple[str, ...]:
        return tuple(
            self._sections[index].section_id
            for index in self._visible_section_indexes
        )

    def _populate_group_filter(self) -> None:
        selected = str(self.group_filter.currentData() or "")
        groups = tuple(
            dict.fromkeys(section.group for section in self._sections if section.group)
        )
        self.group_filter.blockSignals(True)
        self.group_filter.clear()
        self.group_filter.addItem(self.tr("All groups"), "")
        for group in groups:
            self.group_filter.addItem(group, group)
        selected_index = self.group_filter.findData(selected)
        self.group_filter.setCurrentIndex(max(0, selected_index))
        self.group_filter.blockSignals(False)

    def _populate_group_overview(self) -> None:
        while self.group_button_grid.count():
            item = self.group_button_grid.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._group_buttons = []
        group_counts: dict[str, int] = {}
        for section in self._sections:
            if section.group:
                group_counts[section.group] = group_counts.get(section.group, 0) + 1
        for index, (group, count) in enumerate(group_counts.items()):
            button = QPushButton(
                self.tr("%1 · %2 tools")
                .replace("%1", group)
                .replace("%2", str(count))
            )
            button.setObjectName("sectionGroupButton")
            button.setAccessibleName(
                self.tr("Show %1 specialist tools").replace("%1", group)
            )
            button.clicked.connect(
                lambda _checked=False, selected=group: self._select_group(selected)
            )
            row, column = divmod(index, 2)
            self.group_button_grid.addWidget(button, row, column)
            self._group_buttons.append(button)

    def _select_group(self, group: str) -> None:
        index = self.group_filter.findData(group)
        if index < 0:
            return
        self._overview_active = False
        self.group_filter.setCurrentIndex(index)
        self._rebuild_visible_sections()

    def _matching_section_indexes(self) -> tuple[int, ...]:
        if not self._filtering_enabled:
            return tuple(range(len(self._sections)))
        query = self.filter_input.text().strip().casefold()
        selected_group = str(self.group_filter.currentData() or "")
        matches: list[int] = []
        for index, section in enumerate(self._sections):
            if selected_group and section.group != selected_group:
                continue
            searchable = " ".join(
                (section.label, section.description, section.status, section.group)
            ).casefold()
            if query and query not in searchable:
                continue
            matches.append(index)
        return tuple(matches)

    def _rebuild_visible_sections(self, *_args) -> None:
        if self._filtering_enabled and (
            self.filter_input.text().strip()
            or str(self.group_filter.currentData() or "")
        ):
            self._overview_active = False
        active_section_id = self.active_section_id()
        previous_suppress = self._suppress_signal
        self._suppress_signal = True
        self._visible_section_indexes = self._matching_section_indexes()
        self._rail_section_indexes = {}
        self.rail.clear()
        self.selector.clear()
        previous_group = ""
        for section_index in self._visible_section_indexes:
            section = self._sections[section_index]
            if self._filtering_enabled and section.group and section.group != previous_group:
                header = QListWidgetItem(section.group)
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                header.setData(Qt.ItemDataRole.AccessibleTextRole, section.group)
                header.setData(
                    Qt.ItemDataRole.AccessibleDescriptionRole,
                    self.tr("Specialist tool group"),
                )
                self.rail.addItem(header)
                previous_group = section.group
            visible_label = (
                self.tr("%1 — %2").replace("%1", section.label).replace("%2", section.status)
                if section.status
                else section.label
            )
            item = QListWidgetItem(visible_label)
            item.setData(Qt.ItemDataRole.UserRole, section.section_id)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, section.label)
            item.setData(
                Qt.ItemDataRole.AccessibleDescriptionRole,
                section.description or section.status,
            )
            item.setToolTip(section.description or section.label)
            if section.icon:
                icon = get_qicon(section.icon, size=20)
                item.setIcon(icon)
            item.setSizeHint(item.sizeHint().expandedTo(self._minimum_row_size(visible_label)))
            self.rail.addItem(item)
            self._rail_section_indexes[self.rail.count() - 1] = section_index
            if section.icon:
                self.selector.addItem(icon, section.label, section.section_id)
            else:
                self.selector.addItem(section.label, section.section_id)
            index = self.selector.count() - 1
            self.selector.setItemData(index, section.description or section.label, Qt.ItemDataRole.ToolTipRole)
            self.selector.setItemData(index, section.label, Qt.ItemDataRole.AccessibleTextRole)
            self.selector.setItemData(
                index,
                section.description or section.status,
                Qt.ItemDataRole.AccessibleDescriptionRole,
            )
        if self._visible_section_indexes:
            selected_index = 0
            for index, section_index in enumerate(self._visible_section_indexes):
                if self._sections[section_index].section_id == active_section_id:
                    selected_index = index
                    break
            self.selector.setCurrentIndex(selected_index)
            self._select_rail_section_index(
                self._visible_section_indexes[selected_index]
            )
        has_matches = bool(self._visible_section_indexes)
        show_overview = self._filtering_enabled and self._overview_active
        self.group_overview.setVisible(show_overview)
        self.no_results.setVisible(self._filtering_enabled and not has_matches)
        self.match_count.setVisible(
            self._filtering_enabled and not show_overview and has_matches
        )
        if self._filtering_enabled:
            self.match_count.setText(
                self.tr("%1 specialist tools")
                .replace("%1", str(len(self._visible_section_indexes)))
            )
        self._apply_mode(self._compact)
        self._suppress_signal = previous_suppress

    def sections(self) -> tuple[SectionItem, ...]:
        return self._sections

    def section_ids(self) -> tuple[str, ...]:
        return tuple(section.section_id for section in self._sections)

    def set_active_section(self, section_id: str, *, reveal: bool = True) -> None:
        for index, section in enumerate(self._sections):
            if section.section_id == section_id:
                if self._filtering_enabled and reveal:
                    self._overview_active = False
                    self.filter_input.blockSignals(True)
                    self.group_filter.blockSignals(True)
                    self.filter_input.clear()
                    group_index = self.group_filter.findData(section.group)
                    self.group_filter.setCurrentIndex(max(0, group_index))
                    self.filter_input.blockSignals(False)
                    self.group_filter.blockSignals(False)
                    self._rebuild_visible_sections()
                if index not in self._visible_section_indexes:
                    self.filter_input.blockSignals(True)
                    self.group_filter.blockSignals(True)
                    self.filter_input.clear()
                    self.group_filter.setCurrentIndex(0)
                    self.filter_input.blockSignals(False)
                    self.group_filter.blockSignals(False)
                    self._rebuild_visible_sections()
                self._suppress_signal = True
                visible_index = self._visible_section_indexes.index(index)
                self._select_rail_section_index(index)
                self.selector.setCurrentIndex(visible_index)
                self._suppress_signal = False
                return

    def active_section_id(self) -> str:
        visible_index = self.selector.currentIndex()
        if 0 <= visible_index < len(self._visible_section_indexes):
            section_index = self._visible_section_indexes[visible_index]
            if 0 <= section_index < len(self._sections):
                return str(self._sections[section_index].section_id)
        return ""

    def set_compact(self, compact: bool) -> None:
        """Select rail or compact mode from shell-owned responsive policy."""
        self._compact = compact
        self._apply_mode(compact)

    def refresh_icons(self) -> None:
        """Rebuild semantic icon tints after a live theme change."""
        for visible_index, section_index in enumerate(self._visible_section_indexes):
            section = self._sections[section_index]
            if not section.icon:
                continue
            icon = get_qicon(section.icon, size=20)
            rail_row = next(
                (
                    row
                    for row, mapped_index in self._rail_section_indexes.items()
                    if mapped_index == section_index
                ),
                -1,
            )
            rail_item = self.rail.item(rail_row)
            if rail_item is not None:
                rail_item.setIcon(icon)
            self.selector.setItemIcon(visible_index, icon)

    def is_compact(self) -> bool:
        return self._compact

    def changeEvent(self, event) -> None:
        if event is not None and event.type() == QEvent.Type.FontChange:
            self._refresh_row_sizes()
        super().changeEvent(event)

    def _minimum_row_size(self, text: str) -> QSize:
        bounds = self.rail.fontMetrics().boundingRect(
            QRect(0, 0, 180, 1000),
            Qt.TextFlag.TextWordWrap,
            text,
        )
        return QSize(208, max(44, bounds.height() + 16))

    def _refresh_row_sizes(self) -> None:
        for row, section_index in self._rail_section_indexes.items():
            item = self.rail.item(row)
            if item is not None:
                item.setSizeHint(
                    self._minimum_row_size(self._sections[section_index].label)
                )

    def _apply_mode(self, compact: bool) -> None:
        self._compact = compact
        self.setMinimumWidth(0 if compact else 208)
        self.setMaximumWidth(16777215 if compact else 224)
        show_sections = not (
            self._filtering_enabled and self._overview_active
        ) and bool(self._visible_section_indexes)
        self.rail.setVisible(show_sections and not compact)
        self.selector.setVisible(show_sections and compact)

    def _on_rail_changed(self, index: int) -> None:
        section_index = self._rail_section_indexes.get(index)
        if self._suppress_signal or section_index is None:
            return
        self._suppress_signal = True
        visible_index = self._visible_section_indexes.index(section_index)
        self.selector.setCurrentIndex(visible_index)
        self._suppress_signal = False
        self.sectionActivated.emit(self._sections[section_index].section_id)

    def _on_selector_changed(self, index: int) -> None:
        if (
            self._suppress_signal
            or index < 0
            or index >= len(self._visible_section_indexes)
        ):
            return
        section_index = self._visible_section_indexes[index]
        self._suppress_signal = True
        self._select_rail_section_index(section_index)
        self._suppress_signal = False
        self.sectionActivated.emit(self._sections[section_index].section_id)

    def _select_rail_section_index(self, section_index: int) -> None:
        for row, mapped_index in self._rail_section_indexes.items():
            if mapped_index == section_index:
                self.rail.setCurrentRow(row)
                return


@dataclass(frozen=True)
class LocalViewItem:
    """Presentation metadata for one peer view inside a single route."""

    view_id: str
    label: str
    description: str = ""


class LocalViewSwitcher(QFrame):
    """Switch between two to five local peer views without route semantics."""

    viewActivated = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("localViewSwitcher")
        self.setAccessibleName(self.tr("Views"))
        self._views: tuple[LocalViewItem, ...] = ()
        self._compact = False
        self._suppress_signal = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.button_row = QWidget(self)
        self.button_layout = QHBoxLayout(self.button_row)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(8)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.idClicked.connect(self._on_button_clicked)
        layout.addWidget(self.button_row)

        self.selector = QComboBox(self)
        self.selector.setAccessibleName(self.tr("View"))
        self.selector.currentIndexChanged.connect(self._on_selector_changed)
        self.selector.hide()
        layout.addWidget(self.selector)

    def set_views(
        self,
        views: tuple[LocalViewItem, ...] | list[LocalViewItem],
    ) -> None:
        """Replace the bounded local view set."""
        normalized = tuple(views)
        if normalized and not 2 <= len(normalized) <= 5:
            raise ValueError("LocalViewSwitcher requires two to five views")
        view_ids = tuple(view.view_id for view in normalized)
        if any(not view_id for view_id in view_ids) or len(set(view_ids)) != len(view_ids):
            raise ValueError("Local view IDs must be non-empty and unique")

        self._suppress_signal = True
        for button in self.button_group.buttons():
            self.button_group.removeButton(button)
            self.button_layout.removeWidget(button)
            button.deleteLater()
        self.selector.clear()
        self._views = normalized
        for index, view in enumerate(self._views):
            button = QPushButton(view.label, self.button_row)
            button.setCheckable(True)
            button.setAccessibleName(view.label)
            button.setAccessibleDescription(view.description)
            button.setToolTip(view.description or view.label)
            self.button_group.addButton(button, index)
            self.button_layout.addWidget(button)
            self.selector.addItem(view.label, view.view_id)
            self.selector.setItemData(
                index,
                view.description or view.label,
                Qt.ItemDataRole.ToolTipRole,
            )
        self.button_layout.addStretch()
        if self._views:
            first = self.button_group.button(0)
            if first is not None:
                first.setChecked(True)
            self.selector.setCurrentIndex(0)
        self._suppress_signal = False

    def view_ids(self) -> tuple[str, ...]:
        return tuple(view.view_id for view in self._views)

    def active_view_id(self) -> str:
        index = self.selector.currentIndex()
        if 0 <= index < len(self._views):
            return self._views[index].view_id
        return ""

    def set_active_view(self, view_id: str) -> None:
        for index, view in enumerate(self._views):
            if view.view_id != view_id:
                continue
            self._suppress_signal = True
            self.selector.setCurrentIndex(index)
            button = self.button_group.button(index)
            if button is not None:
                button.setChecked(True)
            self._suppress_signal = False
            return

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)
        self.button_row.setVisible(not self._compact)
        self.selector.setVisible(self._compact)

    def is_compact(self) -> bool:
        return self._compact

    def _activate_index(self, index: int) -> None:
        if self._suppress_signal or not 0 <= index < len(self._views):
            return
        self._suppress_signal = True
        self.selector.setCurrentIndex(index)
        button = self.button_group.button(index)
        if button is not None:
            button.setChecked(True)
        self._suppress_signal = False
        self.viewActivated.emit(self._views[index].view_id)

    def _on_button_clicked(self, index: int) -> None:
        self._activate_index(index)

    def _on_selector_changed(self, index: int) -> None:
        self._activate_index(index)
