"""Care workflow presentation reuses existing navigation and read-only workers."""
from __future__ import annotations

from typing import Any


class CareNavigationMixin:
    def _open_package_sources(self: Any) -> None:
        """Reveal the single source overview on the existing Apps route."""
        self._activate_destination("install")
        entry = self._sidebar_index.get("utility_install")
        if entry is not None:
            page = entry.page_widget
            loader = getattr(page, "ensure_loaded", None)
            if callable(loader):
                loaded = loader()
                if loaded is not None:
                    page = loaded
            focus = getattr(page, "focus_sources", None)
            if callable(focus):
                focus()

    def _open_apps_unused_runtimes(self: Any, preselection: dict) -> bool:
        """Focus existing runtime inspection; never inspect on navigation."""
        from services.software.flatpak_maintenance import INSTALLATION_PATTERN

        if set(preselection) - {"section", "installation"} or preselection.get("section") != "unused-runtimes":
            return False
        installation = preselection.get("installation")
        if installation is not None and (not isinstance(installation, str) or not INSTALLATION_PATTERN.fullmatch(installation)):
            return False
        if not self.switch_to_route("software:apps"):
            return False
        entry = self._sidebar_index.get("utility_install")
        if entry is None:
            return False
        page = self._real_widget_for_entry(entry)
        insights = page.installed_card.insights
        if installation is not None:
            index = insights.installation.findText(installation)
            if index < 0:
                return False
            insights.installation.setCurrentIndex(index)
        installed_index = page.view_filter.findData("installed")
        page.view_filter.setCurrentIndex(installed_index)
        page.body_scroll.ensureWidgetVisible(insights)
        insights.inspect_button.setFocus()
        return True

    def _open_update_diagnosis(self: Any, source: str, run_id: str = "") -> None:
        """Open the exact source/run context; collection requires user activation."""
        if not self.switch_to_route("health"):
            return
        entry = self._sidebar_index.get("utility_fix")
        if entry is not None:
            page = self._real_widget_for_entry(entry)
            page.preselect_update_diagnosis(source, run_id)

    def _restore_saved_updates(self: Any, page: Any) -> None:
        """Hydrate saved observations on a worker without executing a change."""
        from services.software.update_recovery import UpdateRecoveryService

        current = self._utility_operation_adapter
        if current is not None:
            current.stopped.connect(lambda: self._restore_saved_updates(page))
            return
        page.set_notice("info", "Loading saved results", "Reading update observations and saved verification tasks.")
        page.set_loading(True)
        adapter = self._new_utility_operation_adapter()
        adapter.finished.connect(page.restore_saved_state)
        adapter.failed.connect(lambda _message: page.set_notice("error", "Saved results unavailable", "Saved update history could not be read. Review Activity before updating."))
        adapter.stopped.connect(lambda: page.set_loading(False))
        adapter.start(UpdateRecoveryService().load)
