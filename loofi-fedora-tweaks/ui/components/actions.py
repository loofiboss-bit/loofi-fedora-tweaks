"""Accessible action controls with stable semantic roles."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QWidget


class _RoleButton(QPushButton):
    """Base button whose visual priority is expressed through properties."""

    _VALID_STATES = frozenset({"default", "loading", "error", "success"})

    def __init__(
        self,
        text: str = "",
        *,
        role: str = "secondary",
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._default_text = text
        self._default_description = description
        self.setObjectName("componentButton")
        self.setProperty("buttonRole", role)
        self.setProperty("interactionState", "default")
        self.setMinimumSize(36, 36)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(text)
        self.setAccessibleDescription(description)

    def setText(self, text: str | None) -> None:  # noqa: N802 - Qt API compatibility
        normalized_text = text or ""
        super().setText(normalized_text)
        if not self.accessibleName() or self.accessibleName() == self._default_text:
            self.setAccessibleName(normalized_text)
        if self.property("interactionState") == "default":
            self._default_text = normalized_text

    def set_state(self, state: str, message: str = "") -> None:
        """Apply a presentation state without owning any async operation."""
        normalized = state if state in self._VALID_STATES else "default"
        self.setProperty("interactionState", normalized)
        if normalized == "default":
            super().setText(self._default_text)
            self.setEnabled(True)
            self.setAccessibleDescription(message or self._default_description)
        else:
            if message:
                super().setText(message)
            self.setEnabled(normalized != "loading")
            state_label = {
                "loading": self.tr("Loading"),
                "error": self.tr("Error"),
                "success": self.tr("Success"),
            }.get(normalized, self.tr("Ready"))
            self.setAccessibleDescription(
                self.tr("%1: %2").replace("%1", state_label).replace(
                    "%2", message or self._default_text
                )
            )
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def set_loading(self, loading: bool, message: str = "") -> None:
        self.set_state("loading" if loading else "default", message)

    def set_error(self, message: str = "") -> None:
        self.set_state("error", message)

    def set_success(self, message: str = "") -> None:
        self.set_state("success", message)

    def reset_state(self) -> None:
        self.set_state("default")


class PrimaryButton(_RoleButton):
    def __init__(self, text: str = "", *, description: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, role="primary", description=description, parent=parent)


class SecondaryButton(_RoleButton):
    def __init__(self, text: str = "", *, description: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, role="secondary", description=description, parent=parent)


class GhostButton(_RoleButton):
    def __init__(self, text: str = "", *, description: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, role="ghost", description=description, parent=parent)


class DangerButton(_RoleButton):
    def __init__(self, text: str = "", *, description: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, role="danger", description=description, parent=parent)


class ActionBar(QWidget):
    """Compact action strip with distinct supporting and primary zones."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("actionBar")
        self.setAccessibleName(self.tr("Actions"))
        self.setAccessibleDescription(self.tr("Available actions for this content"))
        self.row_layout = QHBoxLayout(self)
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setSpacing(8)
        self.row_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._supporting_count = 0
        self._action_owners: dict[QWidget, QWidget | None] = {}
        self.row_layout.addStretch()

    def add_action(self, widget: QWidget, *, primary: bool = False) -> None:
        """Add a caller-owned control without attaching domain behavior."""
        self._action_owners[widget] = widget.parentWidget()
        if primary:
            self.row_layout.addWidget(widget)
        else:
            self.row_layout.insertWidget(self._supporting_count, widget)
            self._supporting_count += 1
        widget.show()

    def clear_actions(self) -> None:
        """Detach caller-owned controls and restore the supporting/primary split."""
        for widget, owner in tuple(self._action_owners.items()):
            self.row_layout.removeWidget(widget)
            widget.hide()
            widget.setParent(owner)
        self._action_owners.clear()
        self._supporting_count = 0
