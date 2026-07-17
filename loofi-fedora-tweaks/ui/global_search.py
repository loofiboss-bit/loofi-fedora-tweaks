"""Single global route, setting, and action discovery dialog for v15."""

from __future__ import annotations

from collections.abc import Callable

from core.navigation import (
    GlobalSearchModel,
    SearchFilter,
    SearchResult,
    SearchResultKind,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


_MAX_RESULTS = 12


class GlobalSearchDialog(QDialog):
    """Keyboard-first UI backed exclusively by :class:`GlobalSearchModel`."""

    def __init__(
        self,
        model: GlobalSearchModel,
        on_result: Callable[[SearchResult], object],
        *,
        search_filter: SearchFilter = SearchFilter.ALL,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._on_result = on_result
        self._search_filter = search_filter
        self._visible_results: tuple[SearchResult, ...] = ()
        self._setup_ui()
        self._populate_results("")

    def _setup_ui(self) -> None:
        actions_only = self._search_filter is SearchFilter.ACTIONS
        self.setWindowTitle(
            self.tr("Search Actions") if actions_only else self.tr("Search Loofi")
        )
        self.setObjectName("globalSearch")
        self.setMinimumSize(620, 420)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.Popup)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("globalSearchInput")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setAccessibleName(self.tr("Global search"))
        self.search_input.setPlaceholderText(
            self.tr("Search safe action entry points...")
            if actions_only
            else self.tr("Search routes, settings, and actions...")
        )
        self.search_input.textChanged.connect(self._populate_results)
        layout.addWidget(self.search_input)

        self.hint_label = QLabel(self)
        self.hint_label.setObjectName("globalSearchHint")
        layout.addWidget(self.hint_label)

        self.results_list = QListWidget(self)
        self.results_list.setObjectName("globalSearchResults")
        self.results_list.setAccessibleName(self.tr("Search results"))
        self.results_list.itemActivated.connect(self._activate_item)
        self.results_list.itemClicked.connect(self._activate_item)
        layout.addWidget(self.results_list, 1)

        footer = QLabel(self.tr("Up/Down Navigate    Enter Open    Esc Close"), self)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setObjectName("globalSearchFooter")
        layout.addWidget(footer)

    def _populate_results(self, query: str) -> None:
        self.results_list.clear()
        self._visible_results = self._model.search(
            str(query).strip(),
            search_filter=self._search_filter,
            limit=_MAX_RESULTS,
        )
        for result in self._visible_results:
            kind = {
                SearchResultKind.ROUTE: self.tr("Page"),
                SearchResultKind.SETTING: self.tr("Setting"),
                SearchResultKind.ACTION: self.tr("Action"),
            }[result.kind]
            risk = (
                self.tr(" - %1 risk").replace("%1", result.risk)
                if result.risk not in {"", "none"}
                else ""
            )
            pin = self.tr("Pinned - ") if result.pinned else ""
            text = (
                f"{pin}{result.destination_label} > {result.label}\n"
                f"{kind}{risk} - {result.description}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, result)
            item.setToolTip(result.description)
            self.results_list.addItem(item)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)
            self.hint_label.setText(
                self.tr("%1 result(s)").replace("%1", str(len(self._visible_results)))
            )
        else:
            self.hint_label.setText(self.tr("No available results"))

    def _activate_item(self, item: QListWidgetItem) -> None:
        """Navigate through the owner callback; never execute a result directly."""
        result = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(result, SearchResult):
            self._on_result(result)
        self.accept()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # type: ignore[override]
        if event is None:
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current = self.results_list.currentItem()
            if current is not None:
                self._activate_item(current)
            return
        if key == Qt.Key.Key_Down:
            row = self.results_list.currentRow()
            if row < self.results_list.count() - 1:
                self.results_list.setCurrentRow(row + 1)
            return
        if key == Qt.Key.Key_Up:
            row = self.results_list.currentRow()
            if row > 0:
                self.results_list.setCurrentRow(row - 1)
            return
        super().keyPressEvent(event)
