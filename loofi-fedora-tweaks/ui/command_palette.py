"""
Command Palette - Global fuzzy search across all features.
Part of v11.0 "Aurora Update".

Provides a Ctrl+K searchable overlay that lets users jump to any
feature or tab in the application.  The palette uses simple
case-insensitive substring matching across feature names and keywords.

Integration:
    palette = CommandPalette(on_action=main_window.switch_to_route, parent=main_window)
    palette.exec()
"""

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from utils.log import get_logger

logger = get_logger(__name__)

# Maximum results displayed at once
_MAX_RESULTS = 10


# -----------------------------------------------------------------------
# Feature registry
# -----------------------------------------------------------------------

def _build_feature_registry() -> list[dict]:
    """Return searchable navigation routes and quick commands.

    Each entry has:
        name      - human-readable feature name
        category  - tab / section it belongs to
        keywords  - list of extra search tokens
        action    - route ID passed to the on_action callback
        type      - 'navigate' (default) or 'execute' for quick commands
        execute   - callable for 'execute' type entries
    """
    from core.navigation import routes_for_palette

    features: list[dict] = []
    for route in routes_for_palette():
        features.append(
            {
                "name": route.label,
                "category": route.category,
                "keywords": list(route.keywords) + list(route.aliases),
                "action": route.id,
                "route_id": route.id,
                "type": "navigate",
            }
        )

    # Add quick commands (v47.0)
    try:
        from utils.quick_commands import QuickCommandRegistry
        registry = QuickCommandRegistry.instance()
        # Auto-register builtins if empty
        if not registry.list_all():
            for cmd in QuickCommandRegistry.get_builtin_commands():
                registry.register(cmd)
        for cmd in registry.list_all():
            if cmd.action is not None:
                features.append({
                    "name": f"⚡ {cmd.name}",
                    "category": cmd.category,
                    "keywords": cmd.keywords,
                    "action": "",
                    "type": "execute",
                    "execute": cmd.action,
                })
    except (ImportError, RuntimeError):
        pass

    return features


# -----------------------------------------------------------------------
# Command Palette dialog
# -----------------------------------------------------------------------

class CommandPalette(QDialog):
    """Fast, fuzzy-search command palette triggered via Ctrl+K."""

    def __init__(
        self,
        on_action: Callable[[str], None],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._on_action = on_action
        self._registry = _build_feature_registry()
        self._visible_entries: list[dict] = []

        self._setup_ui()
        self._populate_results("")  # show all initially

    # -- UI setup -------------------------------------------------------

    def _setup_ui(self):
        self.setWindowTitle(self.tr("Command Palette"))
        self.setFixedSize(600, 400)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.setObjectName("commandPalette")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            self.tr("Search features... (Ctrl+K)")
        )
        input_font = QFont()
        input_font.setPointSize(14)
        self._search_input.setFont(input_font)
        self._search_input.setObjectName("paletteSearch")
        self._search_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._search_input)

        # Results count hint
        self._lbl_hint = QLabel()
        self._lbl_hint.setObjectName("paletteHint")
        layout.addWidget(self._lbl_hint)

        # Results list
        self._results_list = QListWidget()
        self._results_list.setObjectName("paletteResults")
        self._results_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._results_list.itemActivated.connect(self._activate_item)
        self._results_list.itemClicked.connect(self._activate_item)
        layout.addWidget(self._results_list, 1)

        # Footer hint
        footer = QLabel(
            self.tr("\u2191\u2193 Navigate    \u23ce Enter    Esc Close")
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setObjectName("paletteFooter")
        layout.addWidget(footer)

        # Center on parent
        if self.parent():
            parent_geom = self.parent().geometry()
            x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
            y = parent_geom.y() + (parent_geom.height() - self.height()) // 3
            self.move(x, y)

    # -- Search / filter ------------------------------------------------

    def _on_text_changed(self, text: str):
        self._populate_results(text.strip())

    def _populate_results(self, query: str):
        """Filter the registry and update the list widget."""
        self._results_list.clear()
        self._visible_entries.clear()

        if not query:
            filtered = self._registry[:_MAX_RESULTS]
        else:
            query_lower = query.lower()
            scored: list[tuple[int, dict]] = []
            for entry in self._registry:
                score = self._match_score(entry, query_lower)
                if score > 0:
                    scored.append((score, entry))
            scored.sort(key=lambda t: t[0], reverse=True)
            filtered = [entry for _, entry in scored[:_MAX_RESULTS]]

        for entry in filtered:
            display_text = f"{entry['category']}  \u203a  {entry['name']}"
            # Show keyword hints as description (v38.0)
            keywords = entry.get("keywords", [])
            if keywords:
                display_text += f"\n  {', '.join(keywords[:4])}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._results_list.addItem(item)
            self._visible_entries.append(entry)

        # Select first result
        if self._results_list.count() > 0:
            self._results_list.setCurrentRow(0)

        # Update hint
        total_matches = len(filtered)
        if not query:
            self._lbl_hint.setText(
                self.tr("Showing {n} of {total} features").format(
                    n=total_matches, total=len(self._registry)
                )
            )
        elif total_matches == 0:
            self._lbl_hint.setText(self.tr("No results found"))
        else:
            self._lbl_hint.setText(
                self.tr("{n} result(s)").format(n=total_matches)
            )

    @staticmethod
    def _match_score(entry: dict, query_lower: str) -> int:
        """Return a relevance score (0 = no match, higher = better).

        Scoring rules:
          - Exact match on name start     -> 100
          - Substring in name             ->  80
          - Exact match on category start ->  60
          - Substring in category         ->  40
          - Substring in any keyword      ->  30
          - No match                      ->   0
        """
        name_lower = entry["name"].lower()
        cat_lower = entry["category"].lower()

        if name_lower.startswith(query_lower):
            return 100
        if query_lower in name_lower:
            return 80
        if cat_lower.startswith(query_lower):
            return 60
        if query_lower in cat_lower:
            return 40
        for kw in entry.get("keywords", []):
            if query_lower in kw.lower():
                return 30
        return 0

    # -- Activation -----------------------------------------------------

    def _activate_item(self, item: QListWidgetItem):
        """Trigger the on_action callback for the selected feature."""
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not entry:
            self.accept()
            return

        entry_type = entry.get("type", "navigate")

        if entry_type == "execute":
            # Quick command: execute the handler directly
            handler = entry.get("execute")
            if callable(handler):
                logger.info(
                    "Command palette: executing '%s'",
                    entry.get("name", ""),
                )
                try:
                    handler()
                except (RuntimeError, OSError, ValueError) as e:
                    logger.debug("Quick command failed: %s", e)
        elif callable(self._on_action):
            route_id = entry.get("route_id") or entry.get("action", "")
            if route_id:
                logger.info(
                    "Command palette: switching to route '%s' (feature: %s)",
                    route_id,
                    entry.get("name", ""),
                )
                self._on_action(route_id)
        self.accept()

    # -- Key handling ---------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent | None):  # type: ignore[override]
        """Handle Up/Down arrows, Enter, and Escape."""
        if event is None:
            return
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self.reject()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current = self._results_list.currentItem()
            if current:
                self._activate_item(current)
            return

        if key == Qt.Key.Key_Down:
            row = self._results_list.currentRow()
            if row < self._results_list.count() - 1:
                self._results_list.setCurrentRow(row + 1)
            return

        if key == Qt.Key.Key_Up:
            row = self._results_list.currentRow()
            if row > 0:
                self._results_list.setCurrentRow(row - 1)
            return

        # Anything else goes to the search input
        super().keyPressEvent(event)
