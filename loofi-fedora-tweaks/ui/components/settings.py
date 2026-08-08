"""Accessible presentation primitives for application settings."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


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
        self._description = description
        self.control = control

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("settingRowTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.description_label = QLabel(description, self)
        self.description_label.setObjectName("settingRowDescription")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        layout.addWidget(control)

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
