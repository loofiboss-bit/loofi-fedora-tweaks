"""Care workflow presentation reuses existing navigation and read-only workers."""
from __future__ import annotations

from typing import Any


class CareNavigationMixin:
    def _open_route_request(self: Any, route_id: str, _preselection=None) -> None:
        """Navigate through the canonical manifest; metadata remains inert."""
        if route_id == "setup" and isinstance(_preselection, dict) and set(_preselection) == {"add_application"}:
            if self.switch_to_route("setup"):
                entry = self._sidebar_index.get("setup")
                if entry is not None:
                    page = self._real_widget_for_entry(entry)
                    setter = getattr(page, "set_pending_application", None)
                    if callable(setter):
                        setter(_preselection["add_application"])
            return
        if isinstance(_preselection, dict) and _preselection.get("section") in {"flatpak-updates", "installed-app"}:
            self._open_flatpak_context(route_id, _preselection)
            return
        if isinstance(_preselection, dict) and _preselection and not set(_preselection) - {"run_id", "session_id", "update_source", "symptom", "tweak_id"}:
            if any(not isinstance(value, str) for value in _preselection.values()):
                return
            tweak_id = _preselection.get("tweak_id", "")
            if tweak_id and (route_id != "tune" or tweak_id != "kde-tap-to-click"):
                return
            source = _preselection.get("update_source", "")
            run_id = _preselection.get("run_id", "")
            session_id = _preselection.get("session_id", "")
            symptom = _preselection.get("symptom", "")
            if route_id == "health" and session_id:
                if self.switch_to_route("health"):
                    entry = self._sidebar_index.get("utility_fix")
                    if entry is not None:
                        select_session = getattr(self._real_widget_for_entry(entry), "select_saved_session", None)
                        if callable(select_session):
                            select_session(session_id)
                return
            if route_id == "health" and source in {"system", "flatpak", "firmware"}:
                self._open_update_diagnosis(source, run_id)
                return
            if route_id == "changes" and run_id:
                self._open_action_center_run(run_id)
                return
            if route_id == "maintenance:updates" and source in {"system", "flatpak", "firmware"}:
                self._open_update_source_context(source, run_id)
                return
            if route_id == "health" and symptom == "storage_full":
                if self.switch_to_route("health"):
                    entry = self._sidebar_index.get("utility_fix")
                    if entry is not None:
                        focus = getattr(self._real_widget_for_entry(entry), "focus_task", None)
                        if callable(focus):
                            focus(symptom)
                return
            if route_id == "tune" and tweak_id == "kde-tap-to-click":
                if self.switch_to_route("tune"):
                    entry = self._sidebar_index.get("utility_tune")
                    if entry is not None:
                        focus = getattr(self._real_widget_for_entry(entry), "focus_tweak", None)
                        if callable(focus):
                            focus(tweak_id)
                return
        if route_id == "software:apps" and isinstance(_preselection, dict) and _preselection.get("section") == "unused-runtimes":
            self._open_apps_unused_runtimes(_preselection)
            return
        self.switch_to_route(route_id)

    def _open_flatpak_context(self: Any, route_id: str, context: dict) -> bool:
        """Validate and focus exact Flatpak identity without initiating work."""
        from services.software.flatpak_maintenance import INSTALLATION_PATTERN, REF_PATTERN

        if set(context) - {"section", "installation", "refs"}:
            return False
        installation = context.get("installation", "")
        refs = context.get("refs", [])
        if not isinstance(installation, str) or (installation and not INSTALLATION_PATTERN.fullmatch(installation)):
            return False
        if not isinstance(refs, list) or len(refs) > 256 or any(not isinstance(ref, str) or not REF_PATTERN.fullmatch(ref) for ref in refs):
            return False
        if context["section"] == "flatpak-updates" and route_id == "maintenance:updates":
            if not self.switch_to_route(route_id):
                return False
            entry = self._sidebar_index.get("utility_update")
            if entry is None:
                return False
            self._real_widget_for_entry(entry).flatpak_updates.preselect(installation or None, refs)
            return True
        if context["section"] == "installed-app" and route_id == "software:apps" and installation and len(refs) == 1:
            if not self.switch_to_route(route_id):
                return False
            entry = self._sidebar_index.get("utility_install")
            if entry is None:
                return False
            page = self._real_widget_for_entry(entry)
            card = page.installed_card
            page.view_filter.setCurrentIndex(page.view_filter.findData("installed"))
            index = card.installation_filter.findData(installation)
            if index < 0:
                card.installation_filter.addItem(installation, installation)
                index = card.installation_filter.findData(installation)
            card.installation_filter.setCurrentIndex(index)
            page.search_input.setText(refs[0])
            card.updates.show()
            card.updates.preselect(installation, refs)
            page.body_scroll.ensureWidgetVisible(card.updates)
            return True
        return False

    def _open_update_source_context(self: Any, source: str, run_id: str = "") -> None:
        """Select a source and offer the exact saved run without starting work."""
        if self.switch_to_route("maintenance:updates"):
            entry = self._sidebar_index.get("utility_update")
            if entry is not None:
                self._real_widget_for_entry(entry).preselect_source(source, run_id)

    def _open_package_sources(self: Any, source_id: str = "") -> None:
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
                focus(source_id)

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
                insights.installation.addItem(installation)
                index = insights.installation.findText(installation)
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
        adapter = self._new_utility_operation_adapter(
            operation_name=self.tr("Loading saved update results")
        )
        adapter.finished.connect(page.restore_saved_state)
        adapter.failed.connect(lambda _message: page.set_notice("error", "Saved results unavailable", "Saved update history could not be read. Review Activity before updating."))
        adapter.stopped.connect(lambda: page.set_loading(False))
        adapter.start(UpdateRecoveryService().load)
