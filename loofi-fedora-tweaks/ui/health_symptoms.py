"""Presentation helpers for the closed Health symptom choices."""

from typing import Any

from PyQt6.QtWidgets import QComboBox, QGridLayout, QLabel

from core.catalog_models import NativeHandoffId
from ui.native_handoff_card import NativeHandoffCard
from ui.components import ClickableCard, SecondaryButton


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

    def _build_update_choices(self: Any, choose: Any) -> None:
        self.update_source_selector = QComboBox()
        self.update_source_selector.setObjectName("healthUpdateSource")
        self.update_source_selector.setAccessibleName(self.tr("Update source to diagnose"))
        for source, label in (("system", "System"), ("flatpak", "Flatpak"), ("firmware", "Firmware")):
            self.update_source_selector.addItem(self.tr(label), source)
        self.update_source_selector.currentIndexChanged.connect(self._update_source_changed)
        choose.add_widget(self.update_source_selector)
        self.update_run_context = QLabel()
        self.update_run_context.setWordWrap(True)
        choose.add_widget(self.update_run_context)

    def _build_runtime_link(self: Any, checks: Any) -> None:
        self.unused_runtimes_link = SecondaryButton(
            self.tr("Inspect unused Flatpak runtimes"),
            description=self.tr("Open Apps to inspect one installation before reviewing runtime cleanup."),
        )
        self.unused_runtimes_link.setObjectName("healthUnusedRuntimes")
        self.unused_runtimes_link.clicked.connect(
            lambda: self.routeRequested.emit("software:apps", {"section": "unused-runtimes"})
        )
        self.unused_runtimes_link.hide()
        checks.add_widget(self.unused_runtimes_link)

    def _update_source_changed(self: Any, *_args: Any) -> None:
        self._update_run_id = ""
        self._profile_changed()

    def preselect_update_diagnosis(self: Any, source: str, run_id: str = "") -> bool:
        """Prepare one source and exact run without starting a worker."""
        index = self.update_source_selector.findData(source)
        if index < 0:
            return False
        self.profile_selector.setCurrentIndex(self.profile_selector.findData("updates_failed"))
        self.update_source_selector.setCurrentIndex(index)
        self._update_run_id = run_id
        self.update_run_context.setText(self.tr("Recorded run: %1").replace("%1", run_id))
        self._profile_changed()
        self.start_button.setFocus()
        return True

    def selected_profile_id(self: Any) -> str:
        profile_id = str(self._selected_symptom()[2])
        if profile_id == "updates_failed":
            from services.software.update_diagnostics import SOURCE_PROFILES

            return SOURCE_PROFILES[str(self.update_source_selector.currentData() or "system")]
        return profile_id

    def _selected_symptom(self: Any) -> tuple[str, str, str, str]:
        symptoms: tuple[tuple[str, str, str, str], ...] = self._SYMPTOMS
        symptom_id = str(self.profile_selector.currentData() or symptoms[0][0])
        return next(
            (symptom for symptom in symptoms if symptom[0] == symptom_id),
            symptoms[0],
        )
