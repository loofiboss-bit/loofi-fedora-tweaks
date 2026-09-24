"""Task-oriented landing pages for the v29 utility shell.

The landing pages are deliberately presentation-only.  They expose a small
set of stable user goals and ask the owning application shell to navigate to
the existing route that implements each goal.  No page in this module knows
how to mutate the host, starts a worker, or imports an execution service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.catalog_models import CapabilityState
from core.tasks import (
    TaskArea,
    TaskCatalog,
    TaskContext,
    TaskDescriptor,
    TaskEligibility,
    TaskExecutionMode,
)

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from ui.components import (
    Card,
    InlineNotice,
    PageScaffold,
    PrimaryButton,
    SecondaryButton,
    StatusBadge,
)
from ui.components.layout import AdaptiveGrid


@dataclass(frozen=True)
class UtilityTask:
    """One user goal shown on a utility landing page.

    ``route_id`` is intentionally just a navigation target.  The shell
    resolves it through the canonical route policy before any page is loaded.
    """

    id: str
    title: str
    description: str
    route_id: str
    action_label: str
    status: str = "Ready"
    status_kind: str = "neutral"
    risk: str = ""
    descriptor: TaskDescriptor | None = None
    availability: str = "supported"
    enabled: bool = True

    @classmethod
    def from_descriptor(
        cls,
        descriptor: TaskDescriptor,
        *,
        route_id: str,
        action_label: str | None = None,
        eligibility: TaskEligibility | None = None,
    ) -> "UtilityTask":
        """Project one canonical descriptor into a presentation card."""
        availability = (
            eligibility.state
            if eligibility is not None
            else descriptor.capability_state
        )
        availability_value = str(getattr(availability, "value", availability))
        enabled = eligibility.available if eligibility is not None else True
        state_labels = {
            CapabilityState.SUPPORTED.value: ("Ready", "info"),
            CapabilityState.READ_ONLY.value: ("Review", "info"),
            CapabilityState.NATIVE_HANDOFF.value: ("Open settings", "info"),
            CapabilityState.MANUAL_ONLY.value: ("Guidance only", "neutral"),
            CapabilityState.PENDING_REBOOT.value: ("Continue after reboot", "warning"),
            CapabilityState.UNAVAILABLE.value: ("Unavailable", "warning"),
        }
        status, status_kind = state_labels.get(availability_value, ("Unavailable", "warning"))
        if action_label is None:
            action_label = (
                "Open instructions"
                if descriptor.execution_mode is TaskExecutionMode.GUIDANCE
                else "Open system settings"
                if descriptor.execution_mode is TaskExecutionMode.HANDOFF
                else "Open workflow"
            )
        if availability_value == CapabilityState.UNAVAILABLE.value:
            action_label = "Unavailable on this system"
        elif availability_value == CapabilityState.PENDING_REBOOT.value:
            action_label = "Continue after reboot"
        return cls(
            descriptor.id,
            descriptor.title,
            descriptor.description,
            route_id,
            action_label,
            status=status,
            status_kind=status_kind,
            risk=descriptor.risk,
            descriptor=descriptor,
            availability=availability_value,
            enabled=enabled,
        )


class UtilityLandingPage(QWidget):
    """Compact, searchable task launchpad for one primary shell destination."""

    routeRequested = pyqtSignal(str)

    def __init__(
        self,
        destination_id: str,
        title: str,
        description: str,
        tasks: Iterable[UtilityTask],
        *,
        search_placeholder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.destination_id = str(destination_id)
        self.tasks = tuple(tasks)
        self.setObjectName(f"utility{self.destination_id.title()}Page")
        self.setProperty("utilityDestination", self.destination_id)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(title, description)
        root.addWidget(self.scaffold)

        self.intro_card = Card(
            self.tr("Choose what you want to do"),
            self.tr(
                "Each task opens its complete workflow. You can review the scope "
                "and current availability before anything changes."
            ),
        )
        self.intro_card.setObjectName(f"{self.destination_id}TaskIntro")
        self.scaffold.add_widget(self.intro_card)

        self.search_input: QLineEdit | None = None
        if search_placeholder:
            self.search_input = QLineEdit()
            self.search_input.setObjectName(f"{self.destination_id}Search")
            self.search_input.setPlaceholderText(self.tr(search_placeholder))
            self.search_input.setAccessibleName(self.tr("Search tasks"))
            self.search_input.setClearButtonEnabled(True)
            self.search_input.textChanged.connect(self._filter_tasks)
            self.intro_card.add_widget(self.search_input)

        self.state_notice = InlineNotice(
            self.tr("Ready to explore"),
            self.tr("Choose a task to continue."),
            kind="info",
        )
        self.state_notice.setObjectName(f"{self.destination_id}State")
        self.state_notice.setProperty("presentationState", "ready")
        self.intro_card.add_widget(self.state_notice)

        self.task_grid = AdaptiveGrid(
            min_column_width=260,
            column_breakpoints=((0, 1), (640, 2), (960, 3)),
        )
        self.task_grid.setObjectName(f"{self.destination_id}TaskGrid")
        self.scaffold.add_widget(self.task_grid)
        self._task_cards: dict[str, QWidget] = {}
        self._task_buttons: dict[str, QWidget] = {}
        for task in self.tasks:
            self._add_task(task)

        self.scaffold.content_layout.addStretch()

    @property
    def primary_task(self) -> UtilityTask | None:
        """Return the first task, which owns this page's single primary CTA."""
        return self.tasks[0] if self.tasks else None

    @property
    def primary_button(self) -> QWidget | None:
        task = self.primary_task
        return self._task_buttons.get(task.id) if task is not None else None

    def _add_task(self, task: UtilityTask) -> None:
        card = Card(task.title, task.description)
        card.setObjectName(f"{self.destination_id}Task{task.id.title()}")
        card.setProperty("taskId", task.id)
        target_route = task.route_id
        if (
            task.descriptor is not None
            and task.descriptor.execution_mode is TaskExecutionMode.HANDOFF
            and task.descriptor.handoff_route_id
        ):
            target_route = task.descriptor.handoff_route_id
        card.setProperty("taskRoute", target_route)
        card.setProperty("taskAvailability", task.availability)
        status = StatusBadge(
            self.tr(task.status),
            kind=task.status_kind,
            description=(
                self.tr("Risk: %1").replace("%1", task.risk)
                if task.risk
                else self.tr("Task availability")
            ),
        )
        status.setObjectName(f"{self.destination_id}Task{task.id.title()}Status")
        card.add_widget(status)

        is_primary = self.primary_task is not None and task.id == self.primary_task.id
        button_cls = PrimaryButton if is_primary else SecondaryButton
        button = button_cls(
            self.tr(task.action_label),
            description=self.tr(task.description),
        )
        button.setObjectName(
            f"{self.destination_id}{task.id.title()}Cta"
            if is_primary
            else f"{self.destination_id}{task.id.title()}Button"
        )
        button.setProperty("taskId", task.id)
        button.setProperty("taskRoute", task.route_id)
        button.setProperty("ctaState", task.availability)
        button.setEnabled(task.enabled)
        if task.descriptor is not None and task.descriptor.manual_only:
            button.clicked.connect(
                lambda _checked=False, selected=task: self._show_guidance(selected)
            )
        else:
            button.clicked.connect(
                lambda _checked=False, route=target_route: self._request_route(route)
            )
        card.add_widget(button)
        self.task_grid.add_card(card)
        self._task_cards[task.id] = card
        self._task_buttons[task.id] = button

    def _show_guidance(self, task: UtilityTask) -> None:
        """Render manual-only instructions inline without an execution CTA."""
        descriptor = task.descriptor
        guidance = (
            descriptor.manual_guidance
            if descriptor is not None
            else self.tr("Follow the documented system instructions for this task.")
        )
        self.setProperty("lastGuidanceTask", task.id)
        self.state_notice.set_notice(
            "neutral",
            self.tr("Open instructions"),
            self.tr(guidance),
        )
        self.state_notice.setProperty("presentationState", "guidance")

    def _filter_tasks(self, query: str) -> None:
        normalized = " ".join(str(query).casefold().split())
        for task in self.tasks:
            card = self._task_cards.get(task.id)
            if card is None:
                continue
            searchable = " ".join(
                (task.title, task.description, task.action_label, task.status)
            ).casefold()
            card.setVisible(not normalized or normalized in searchable)
        visible = sum(1 for card in self._task_cards.values() if card.isVisible())
        if normalized and visible == 0:
            self.state_notice.set_notice(
                "neutral",
                self.tr("No matching tasks"),
                self.tr("Try a broader search or clear the filter."),
            )
            self.state_notice.setProperty("presentationState", "empty")
        else:
            self.state_notice.set_notice(
                "info",
                self.tr("Ready to explore"),
                self.tr("Choose a task to continue."),
            )
            self.state_notice.setProperty("presentationState", "ready")

    def set_task_state(
        self,
        task_id: str,
        *,
        state: str,
        status: str,
        message: str = "",
        kind: str = "info",
        enabled: bool = True,
    ) -> bool:
        """Update one task's presentation without changing its authority."""
        button = self._task_buttons.get(str(task_id))
        card = self._task_cards.get(str(task_id))
        if button is None or card is None:
            return False
        button.setEnabled(bool(enabled))
        button.setProperty("ctaState", str(state))
        status_badge = card.findChild(StatusBadge)
        if status_badge is not None:
            status_badge.set_status(self.tr(status), kind=kind)
        if message:
            self.state_notice.set_notice(kind, self.tr(status), self.tr(message))
        self.state_notice.setProperty("presentationState", str(state))
        return True

    def focus_task(self, task_id: str) -> bool:
        """Focus a task card after goal-based search navigation.

        This only changes presentation. The owning workflow still performs
        its own preflight and confirmation before any mutation.
        """
        key = str(task_id or "").strip()
        card = self._task_cards.get(key)
        button = self._task_buttons.get(key)
        if card is None or button is None:
            return False
        card.setProperty("focusedFromSearch", True)
        card.setFocus()
        button.setFocus()
        return True

    def _request_route(self, route_id: str) -> None:
        self.setProperty("lastRequestedRoute", str(route_id))
        self.routeRequested.emit(str(route_id))


def default_utility_tasks(
    context: TaskContext | None = None,
) -> dict[str, tuple[UtilityTask, ...]]:
    """Return the curated v29 task set used by the application shell.

    Targets intentionally point at existing canonical routes.  They remain
    stable while the task catalog grows and can be redirected by the shell's
    compatibility policy without changing this presentation contract.
    """

    catalog = TaskCatalog()
    route_overrides = {
        "install:applications": ("software:apps", "Open app installer"),
        "install:flatpaks": ("software:flatpak", "Manage Flatpaks"),
        "install:repositories": ("software:repos", None),
        "tune:storage-trim": ("storage", "Review storage trim"),
        "tune:package-cache": ("maintenance:cleanup", "Review package cache"),
        "tune:desktop": ("settings:appearance", None),
        "fix:system-slow": ("diagnostics", "Run system check"),
        "fix:updates-failed": ("diagnostics", "Diagnose failed updates"),
        "fix:application-failed": ("diagnostics", "Diagnose an application"),
        "fix:network": ("network", "Inspect connections"),
        "fix:storage": ("storage", "Inspect storage"),
        "update:overview": ("maintenance:updates", "Check for updates"),
        "update:system": ("maintenance:updates", "Update system"),
        "update:flatpaks": ("maintenance:updates", "Update Flatpaks"),
        "update:firmware": ("maintenance:updates", "Update firmware"),
    }
    selected: dict[str, list[UtilityTask]] = {key: [] for key in ("install", "tune", "fix", "update")}
    for task_id, (route_id, label) in route_overrides.items():
        descriptor = catalog.get(task_id)
        if descriptor is None:
            continue
        # This compatibility landing projection retains its historical Tune
        # grouping; the live shell now owns these two tasks on Health.
        area = "tune" if task_id.startswith("tune:") else descriptor.area.value if isinstance(descriptor.area, TaskArea) else str(descriptor.area)
        eligibility = catalog.eligibility(descriptor, context) if context is not None else None
        selected[area].append(
            UtilityTask.from_descriptor(
                descriptor,
                route_id=route_id,
                action_label=label,
                eligibility=eligibility,
            )
        )
    return {area: tuple(tasks) for area, tasks in selected.items()}


__all__ = ["UtilityLandingPage", "UtilityTask", "default_utility_tasks"]
