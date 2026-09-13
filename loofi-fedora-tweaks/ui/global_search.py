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
        self._actions_only = search_filter is SearchFilter.ACTIONS
        self._visible_results: tuple[SearchResult, ...] = ()
        self._setup_ui()
        self._populate_results("")

    def _setup_ui(self) -> None:
        actions_only = self._search_filter is SearchFilter.ACTIONS
        self.setWindowTitle(
            self.tr("Search Actions") if actions_only else self.tr("Search Loofi")
        )
        self.setAccessibleName(self.windowTitle())
        self.setAccessibleDescription(
            self.tr("Search available routes, settings, and safe action entry points")
        )
        self.setObjectName("globalSearch")
        # Keep the discovery surface usable beside narrow or text-scaled
        # windows. The parent window may still enlarge it naturally.
        self.setMinimumSize(520, 360)
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
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.results_list = QListWidget(self)
        self.results_list.setObjectName("globalSearchResults")
        self.results_list.setAccessibleName(self.tr("Search results"))
        self.results_list.itemActivated.connect(self._activate_item)
        # A page may be opened directly from the page search. Action mode is
        # deliberately keyboard/activation driven so a casual click cannot
        # even preselect a privileged workflow.
        if not self._actions_only:
            self.results_list.itemClicked.connect(self._activate_item)
        layout.addWidget(self.results_list, 1)

        footer_text = (
            self.tr("Up/Down Navigate    Enter Review    Esc Close")
            if self._actions_only
            else self.tr("Up/Down Navigate    Enter Open    Esc Close")
        )
        footer = QLabel(footer_text, self)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setObjectName("globalSearchFooter")
        layout.addWidget(footer)

    def _populate_results(self, query: str) -> None:
        self.results_list.clear()
        results = self._model.search(
            str(query).strip(),
            search_filter=self._search_filter,
            # Fetch the complete page/settings set before removing actions;
            # otherwise highly ranked configured actions could crowd out
            # destinations from the ordinary Ctrl+K search.
            limit=None if not self._actions_only else _MAX_RESULTS,
        )
        # Ctrl+K is page discovery. The separate Ctrl+Shift+K action mode
        # keeps system operations out of the normal navigation result list.
        if not self._actions_only:
            results = tuple(
                result
                for result in results
                if result.kind is not SearchResultKind.ACTION
            )
        self._visible_results = tuple(results[:_MAX_RESULTS])
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
            mode = (
                self.tr("Action mode — results open review only")
                if self._actions_only
                else self.tr("Pages and settings — use Ctrl+Shift+K for actions")
            )
            self.hint_label.setText(
                self.tr("%1 · %2 result(s)")
                .replace("%1", mode)
                .replace("%2", str(len(self._visible_results)))
            )
        else:
            self.hint_label.setText(
                self.tr("No available results. Try a different term or scope.")
            )

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
