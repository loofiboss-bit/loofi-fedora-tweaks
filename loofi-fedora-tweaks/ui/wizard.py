"""Responsive, non-mutating first-run welcome surface."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.system.onboarding import collect_welcome_system_summary
from utils.log import get_logger

from ui.icon_pack import get_qicon

logger = get_logger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "loofi-fedora-tweaks"
_FIRST_RUN_SENTINEL = _CONFIG_DIR / "first_run_complete"


def needs_first_run() -> bool:
    """Return whether the established completion sentinel is absent."""
    return not _FIRST_RUN_SENTINEL.exists()


def _mark_first_run_complete() -> None:
    """Create the established sentinel after an explicit welcome action."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _FIRST_RUN_SENTINEL.touch()


class FirstRunWelcome(QDialog):
    """One-page welcome with read-only Fedora and safety information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.requested_route = ""
        self.setWindowTitle(self.tr("Welcome to Loofi Fedora Tweaks"))
        self.setMinimumSize(520, 380)
        self.resize(660, 520)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        root = QVBoxLayout(self)
        spacing = max(10, self.fontMetrics().height() // 2)
        root.setContentsMargins(spacing * 2, spacing * 2, spacing * 2, spacing)
        root.setSpacing(spacing)

        scroll = QScrollArea()
        scroll.setObjectName("welcomeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(spacing)

        title = QLabel(self.tr("Welcome to Loofi Fedora Tweaks"))
        title.setObjectName("welcomeTitle")
        title_font = QFont(self.font())
        if title_font.pointSizeF() > 0:
            title_font.setPointSizeF(title_font.pointSizeF() * 1.35)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setWordWrap(True)
        content_layout.addWidget(title)

        intro = QLabel(self.tr("Loofi uses your Fedora variant to explain how package and recovery workflows behave."))
        intro.setObjectName("welcomeIntro")
        intro.setWordWrap(True)
        content_layout.addWidget(intro)

        summary = collect_welcome_system_summary()
        facts = QFrame()
        facts.setObjectName("welcomeFacts")
        facts_form = QFormLayout(facts)
        self._add_fact(facts_form, self.tr("Fedora:"), summary.fedora_name)
        self._add_fact(facts_form, self.tr("Variant:"), summary.variant)
        self._add_fact(facts_form, self.tr("Package management:"), summary.package_manager)
        self._add_fact(facts_form, self.tr("System mode:"), summary.deployment_mode)
        self._add_fact(facts_form, self.tr("Support status:"), summary.support_status)
        content_layout.addWidget(facts)

        behavior = QLabel(summary.behavior)
        behavior.setObjectName("welcomeBehavior")
        behavior.setWordWrap(True)
        content_layout.addWidget(behavior)

        support = QLabel(summary.support_detail)
        support.setObjectName("welcomeSupport")
        support.setWordWrap(True)
        content_layout.addWidget(support)

        privacy = QLabel(self.tr(
            "Privacy and safety: Loofi does not add telemetry. This welcome performs no package, profile, service, or system changes. "
            "Mutating workflows continue to require their normal preview and confirmation steps."
        ))
        privacy.setObjectName("welcomePrivacy")
        privacy.setWordWrap(True)
        content_layout.addWidget(privacy)
        content_layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        self.details_button = QPushButton(self.tr("&View system details"))
        self.details_button.setAccessibleName(self.tr("View system details"))
        self.details_button.setIcon(get_qicon("info", size=18))
        self.details_button.clicked.connect(self._open_system_details)
        actions.addWidget(self.details_button)

        self.open_button = QPushButton(self.tr("&Open Loofi"))
        self.open_button.setAccessibleName(self.tr("Open Loofi"))
        self.open_button.setIcon(get_qicon("home", size=18))
        self.open_button.setDefault(True)
        self.open_button.setAutoDefault(True)
        self.open_button.clicked.connect(self._open_loofi)
        actions.addWidget(self.open_button)
        root.addLayout(actions)

        self.setTabOrder(self.details_button, self.open_button)
        self.open_button.setFocus()

    def _add_fact(self, form: QFormLayout, label: str, value: str) -> None:
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard | Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(label, value_label)

    def _complete(self, route_id: str = "") -> None:
        _mark_first_run_complete()
        self.requested_route = route_id
        logger.info("First-run welcome completed")
        self.accept()

    def _open_loofi(self) -> None:
        self._complete()

    def _open_system_details(self) -> None:
        self._complete("system_info")


# Import compatibility for older callers; this is the same one-page surface.
FirstRunWizard = FirstRunWelcome
