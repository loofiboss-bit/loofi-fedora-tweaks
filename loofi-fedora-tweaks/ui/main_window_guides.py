"""Guide navigation and compact shell integration for MainWindow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QToolButton, QWidget

if TYPE_CHECKING:
    from core.tasks.guides import GuideTarget


class GuideNavigationMixin:
    """Connect Overview's optional guides to existing shell destinations."""

    def _setup_guide_controls(self: Any) -> None:
        frame = self._breadcrumb_frame
        parent = frame if isinstance(frame, QWidget) else None
        self._resume_guide_button = QToolButton(parent)
        self._resume_guide_button.setObjectName("resumeGuideButton")
        self._resume_guide_button.setText(self.tr("Guide"))
        popup_mode = getattr(getattr(QToolButton, "ToolButtonPopupMode", None), "InstantPopup", None)
        if popup_mode is not None:
            self._resume_guide_button.setPopupMode(popup_mode)
        self._resume_guide_menu = QMenu(self._resume_guide_button)
        self._continue_guide_action = QAction(self.tr("Open next guide step"), self._resume_guide_menu)
        self._continue_guide_action.triggered.connect(lambda: self._continue_guide_from_shell())
        self._resume_guide_menu.addAction(self._continue_guide_action)
        self._resume_guide_menu.addSeparator()
        self._return_to_guide_action = QAction(self.tr("Return to guide"), self._resume_guide_menu)
        self._return_to_guide_action.triggered.connect(lambda: self._resume_active_guide())
        self._resume_guide_menu.addAction(self._return_to_guide_action)
        self._resume_guide_button.setMenu(self._resume_guide_menu)
        self._resume_guide_button.setAccessibleName(self.tr("Active Fedora guide options"))
        self._resume_guide_button.setToolTip(self.tr("Continue the active guide or return to its saved progress"))
        self._resume_guide_button.hide()
        self._active_guide_id = ""
        frame.actions_layout.addWidget(self._resume_guide_button)

    def _connect_guide_widget(self: Any, widget: Any) -> None:
        guide_changed = getattr(widget, "guideChanged", None)
        if guide_changed is not None and hasattr(guide_changed, "connect"):
            guide_changed.connect(self._set_active_guide)
        guide_target = getattr(widget, "guideTargetRequested", None)
        if guide_target is not None and hasattr(guide_target, "connect"):
            guide_target.connect(self._open_guide_target)
        current_guide = str(getattr(getattr(widget, "guide_panel", None), "active_guide", ""))
        if current_guide:
            self._set_active_guide(current_guide)

    def _set_active_guide(self: Any, guide_id: str) -> None:
        """Keep one compact resume affordance visible across shell routes."""
        from core.tasks.guides import GUIDES_BY_ID

        selected = str(guide_id or "")
        button = getattr(self, "_resume_guide_button", None)
        self._active_guide_id = selected if selected in GUIDES_BY_ID else ""
        if button is None:
            return
        if self._active_guide_id:
            guide = GUIDES_BY_ID[self._active_guide_id]
            title = self.tr(guide.title)
            button.setText(self.tr("Guide: %1").replace("%1", title))
            button.setAccessibleName(self.tr("Active Fedora guide: %1").replace("%1", title))
            next_step = None
            try:
                from core.tasks.guides import GuideProgressStore, guide_evidence_exists

                snapshot = GuideProgressStore().read()
                for step in guide.steps:
                    progress = snapshot.steps.get(step.id)
                    if progress is None or progress.state == "in_progress":
                        next_step = step
                        break
                    if progress.state == "verified" and not guide_evidence_exists(progress.evidence_kind, progress.evidence_id):
                        next_step = step
                        break
                    if progress.state not in {"reviewed", "skipped", "verified"}:
                        next_step = step
                        break
            except (OSError, RuntimeError, TypeError, ValueError):
                next_step = None
            if next_step is None:
                self._continue_guide_action.setText(self.tr("All guide steps have been reviewed"))
                self._continue_guide_action.setData("")
                self._continue_guide_action.setEnabled(False)
                button.setToolTip(self.tr("%1 — return to saved guide progress").replace("%1", title))
            else:
                self._continue_guide_action.setText(self.tr("Open next step: %1").replace("%1", self.tr(next_step.title)))
                self._continue_guide_action.setData(next_step.id)
                self._continue_guide_action.setEnabled(True)
                button.setToolTip(self.tr("%1 — next: %2").replace("%1", title).replace("%2", self.tr(next_step.title)))
            self._return_to_guide_action.setText(self.tr("Return to %1").replace("%1", title))
            button.setVisible(True)
        else:
            button.hide()

    def _resume_active_guide(self: Any) -> None:
        """Return to Overview with the active saved guide selected."""
        from core.tasks.guides import GUIDES_BY_ID

        guide_id = str(getattr(self, "_active_guide_id", ""))
        if guide_id not in GUIDES_BY_ID or not self.switch_to_route("overview"):
            return
        entry = getattr(self, "_sidebar_index", {}).get("overview")
        if entry is not None:
            page = self._real_widget_for_entry(entry)
            open_guide = getattr(page, "open_guide", None)
            if callable(open_guide):
                open_guide(guide_id)

    def _continue_guide_from_shell(self: Any) -> None:
        """Open the next unfinished guide step through Overview's normal path."""
        from core.tasks.guides import GUIDES_BY_ID

        guide_id = str(getattr(self, "_active_guide_id", ""))
        action = getattr(self, "_continue_guide_action", None)
        step_id = str(action.data() or "") if action is not None else ""
        if guide_id not in GUIDES_BY_ID or not step_id or not self.switch_to_route("overview"):
            return
        entry = getattr(self, "_sidebar_index", {}).get("overview")
        if entry is None:
            return
        page = self._real_widget_for_entry(entry)
        guide_panel = getattr(page, "guide_panel", None)
        open_step = getattr(guide_panel, "open_step", None)
        if callable(open_step):
            open_step(guide_id, step_id)

    def _open_guide_target(self: Any, target: GuideTarget) -> bool:
        """Navigate to one validated guide destination without starting work."""
        from core.tasks.guides import GuideTarget

        if not isinstance(target, GuideTarget):
            return False
        context = dict(target.context)
        if context:
            request = getattr(self, "_open_route_request", None)
            if callable(request):
                request(target.route_id, context)
                navigated = True
            else:
                navigated = self.switch_to_route(target.route_id)
        else:
            navigated = self.switch_to_route(target.route_id)
        if not navigated:
            return False
        if target.task_id and not self._focus_utility_task(target.task_id, target.route_id):
            return False
        if target.tweak_id:
            route = self._resolve_shell_route(target.route_id)
            plugin_id = str(getattr(route, "plugin_id", "")) if route is not None else ""
            entry = getattr(self, "_sidebar_index", {}).get(plugin_id)
            if entry is None:
                return False
            page = self._real_widget_for_entry(entry)
            focus = getattr(page, "focus_tweak", None)
            return bool(focus(target.tweak_id)) if callable(focus) else False
        return True
