"""Presentation helpers for the closed Health symptom choices."""

from typing import Any

from PyQt6.QtWidgets import QGridLayout

from core.catalog_models import NativeHandoffId
from ui.native_handoff_card import NativeHandoffCard
from ui.components import ClickableCard


class HealthSymptomCardsMixin:
    """Keyboard-accessible cards backed by the existing closed selector."""

    def _build_symptom_cards(self: Any, choose: Any) -> None:
        self.symptom_cards = {}
        self.symptom_grid = QGridLayout()
        self.symptom_grid.setSpacing(8)
        for index, (symptom_id, label, _profile, _limitation) in enumerate(self._SYMPTOMS):
            card = ClickableCard(self.tr(label), "", symptom_id)
            card.setObjectName("healthSymptomCard")
            card.setProperty("symptomId", symptom_id)
            card.setAccessibleDescription(self.tr("Select this symptom to preview its read-only checks."))
            card.activated.connect(self._select_symptom_card)
            self.symptom_cards[symptom_id] = card
            self.symptom_grid.addWidget(card, index // 2, index % 2)
        choose.body.addLayout(self.symptom_grid)

    def _select_symptom_card(self: Any, symptom_id: str) -> None:
        index = self.profile_selector.findData(symptom_id)
        if index >= 0:
            self.profile_selector.setCurrentIndex(index)

    def focus_selected_symptom(self: Any) -> None:
        self.symptom_cards[self._selected_symptom()[0]].setFocus()

    def resizeEvent(self: Any, event: Any) -> None:
        # The mixin delegates QWidget's resize before updating its own layout.
        from PyQt6.QtWidgets import QWidget

        QWidget.resizeEvent(self, event)
        if not hasattr(self, "symptom_grid"):
            return
        columns = 1 if self.width() < 560 else 2
        for index, card in enumerate(self.symptom_cards.values()):
            self.symptom_grid.addWidget(card, index // columns, index % columns)

    def _update_symptom_cards(self: Any) -> None:
        selected = self._selected_symptom()[0]
        for symptom_id, card in self.symptom_cards.items():
            active = symptom_id == selected
            card.setProperty("selected", active)
            card.setAccessibleDescription(
                self.tr("Selected symptom. Preview the checks below.") if active
                else self.tr("Select this symptom to preview its read-only checks.")
            )
            card.style().unpolish(card)
            card.style().polish(card)

    def _build_device_settings(self: Any) -> None:
        self.device_settings_cards = {}
        for profile_id, handoff, title in (
            ("sound_not_working", NativeHandoffId.AUDIO_SETTINGS, "Sound Settings"),
            ("bluetooth_not_working", NativeHandoffId.BLUETOOTH_SETTINGS, "Bluetooth Settings"),
        ):
            card = NativeHandoffCard(
                handoff, title=self.tr(title),
                description=self.tr("Review device settings, test the result yourself, then run this check again."),
                button_text=self.tr("Open settings"), parent=self,
            )
            card.hide()
            self.device_settings_cards[profile_id] = card
            self.scaffold.add_widget(card)

    def _show_device_settings(self: Any, profile_id: str) -> None:
        for candidate, card in self.device_settings_cards.items():
            card.setVisible(candidate == profile_id)
            if candidate == profile_id:
                card.refresh_availability()
