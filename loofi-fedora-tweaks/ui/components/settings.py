"""Accessible presentation primitives for application settings."""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QBoxLayout, QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


class SettingRow(QFrame):
    """One setting with nearby description, control, and textual feedback."""

    def __init__(
        self,
        title: str,
        description: str,
        control: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingRow")
        self.setProperty("settingRow", True)
        self._description = description
        self.control = control

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(4)

        self.content_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)
        self.text_panel = QWidget(self)
        self.text_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_layout = QVBoxLayout(self.text_panel)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("settingRowTitle")
        self.title_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)
        self.description_label = QLabel(description, self)
        self.description_label.setObjectName("settingRowDescription")
        self.description_label.setWordWrap(True)
        text_layout.addWidget(self.description_label)
        self.value_label = QLabel(self)
        self.value_label.setObjectName("settingRowValue")
        self.value_label.setWordWrap(True)
        self.value_label.hide()
        text_layout.addWidget(self.value_label)
        self.content_layout.addWidget(self.text_panel, 3)
        self.control_panel = QWidget(self)
        self.control_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.control_layout = QVBoxLayout(self.control_panel)
        self.control_layout.setContentsMargins(0, 0, 0, 0)
        self.control_layout.setSpacing(4)
        self.control_layout.addWidget(control)
        self.content_layout.addWidget(self.control_panel, 2)
        layout.addLayout(self.content_layout)

        self.feedback_label = QLabel(self)
        self.feedback_label.setObjectName("settingRowFeedback")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setAccessibleName(self.tr("%1 status").replace("%1", title))
        self.feedback_label.hide()
        layout.addWidget(self.feedback_label)

        self.setAccessibleName(title)
        self.setAccessibleDescription(description)

    def set_feedback(self, message: str, *, kind: str) -> None:
        """Expose a non-color-only saved, dependency, or error state."""
        prefixes = {
            "saved": self.tr("Saved"),
            "changed": self.tr("Changed"),
            "dependency": self.tr("Unavailable"),
            "error": self.tr("Error"),
            "restart": self.tr("Restart required"),
        }
        prefix = prefixes.get(kind, self.tr("Status"))
        text = (
            self.tr("%1 — %2").replace("%1", prefix).replace("%2", message)
            if message
            else prefix
        )
        self.feedback_label.setProperty("feedbackKind", kind)
        self.feedback_label.setText(text)
        self.feedback_label.setAccessibleDescription(text)
        self.feedback_label.show()
        self.setAccessibleDescription(f"{self._description} {text}".strip())
        style = self.feedback_label.style()
        if style is not None:
            style.unpolish(self.feedback_label)
            style.polish(self.feedback_label)

    def clear_feedback(self) -> None:
        self.feedback_label.clear()
        self.feedback_label.hide()
        self.setAccessibleDescription(self._description)

    def set_dependency(self, message: str, *, blocked: bool) -> None:
        """Update the control and explain why a dependency blocks editing."""
        self.control.setEnabled(not blocked)
        if blocked:
            self.set_feedback(message, kind="dependency")
        elif self.feedback_label.property("feedbackKind") == "dependency":
            self.clear_feedback()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        # Physical font metrics scale with the desktop; avoid a fixed pixel
        # breakpoint that clips controls when users enlarge their text.
        wide = self.width() >= max(640, self.fontMetrics().height() * 40)
        self.content_layout.setDirection(QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom)
        self.control_panel.setMaximumWidth(int(self.width() * 0.48) if wide else 16777215)
        self.setProperty("compact", not wide)
