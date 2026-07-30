"""Show concise current-product highlights after a version upgrade."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from utils.log import get_logger
from version import __version__, __version_codename__

logger = get_logger(__name__)


CURRENT_HIGHLIGHTS = (
    "Six focused destinations with lazy-loaded built-in tools",
    "Guided troubleshooting that starts only when you ask",
    "Reviewed Action Center plans for supported system changes",
    "Separate verification and follow-up checks after maintenance",
)


class WhatsNewDialog(QDialog):
    """Dialog showing what's new in the current version."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("What's New in Loofi Fedora Tweaks"))
        self.setMinimumSize(500, 400)
        self._dont_show = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            self.tr('What\'s New in v{version} "{codename}"').format(
                version=__version__, codename=__version_codename__
            )
        )
        header.setObjectName("whatsNewHeader")
        layout.addWidget(header)

        # Current product highlights
        notes_text = QTextEdit()
        notes_text.setReadOnly(True)
        content = "\n".join(f"  - {self.tr(item)}" for item in CURRENT_HIGHLIGHTS)
        notes_text.setPlainText(content)
        layout.addWidget(notes_text)

        # Don't show again checkbox
        self.dont_show_cb = QCheckBox(self.tr("Don't show this again"))
        layout.addWidget(self.dont_show_cb)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton(self.tr("Got it!"))
        close_btn.setObjectName("whatsNewCloseBtn")
        close_btn.clicked.connect(self._on_close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _on_close(self):
        self._dont_show = self.dont_show_cb.isChecked()
        self.accept()

    @property
    def dont_show_again(self) -> bool:
        return bool(self._dont_show)

    @staticmethod
    def should_show() -> bool:
        """Check if the dialog should be shown based on last seen version."""
        try:
            from utils.settings import SettingsManager

            mgr = SettingsManager.instance()
            last_seen = mgr.get("last_seen_version", "0.0.0")
            return bool(last_seen != __version__)
        except (ImportError, RuntimeError, OSError, ValueError, TypeError) as e:
            logger.debug("Failed to check last seen version: %s", e)
            return True

    @staticmethod
    def mark_seen():
        """Mark the current version as seen."""
        try:
            from utils.settings import SettingsManager

            mgr = SettingsManager.instance()
            mgr.set("last_seen_version", __version__)
            mgr.save()
        except (ImportError, RuntimeError, OSError, ValueError, TypeError, AttributeError) as e:
            logger.debug("Failed to save last seen version: %s", e)
