from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt
from .base_tab import BaseTab
from core.plugins.metadata import PluginMetadata
from core.diagnostics.task_dashboard import TaskManager, DashboardTask
from core.diagnostics.health_registry import HealthRegistry
from .icon_pack import get_qicon
from .layout_primitives import AdaptiveGrid, RouteCard, make_page_title
from utils.log import get_logger
from version import __version__, __version_codename__

logger = get_logger(__name__)


class TaskCard(QFrame):
    """
    Individual task card for the Atlas dashboard.
    """
    def __init__(self, task: DashboardTask, callback, parent=None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("routeCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Icon and Title
        header = QHBoxLayout()
        icon_label = QLabel()
        try:
            icon_label.setPixmap(get_qicon(task.icon_id, size=32).pixmap(32, 32))
        except (OSError, RuntimeError, TypeError, ValueError):
            logger.debug("Unable to load dashboard icon %s", task.icon_id, exc_info=True)
        header.addWidget(icon_label)

        title = QLabel(task.title)
        title.setObjectName("routeCardTitle")
        title.setWordWrap(True)
        header.addWidget(title, 1)
        layout.addLayout(header)

        # Description
        desc = QLabel(task.description)
        desc.setWordWrap(True)
        desc.setObjectName("routeCardDescription")
        layout.addWidget(desc)

        layout.addStretch()

        # Action Button
        self.btn = QPushButton("View Task")
        self.btn.setObjectName("primaryAction")
        self.btn.clicked.connect(lambda: callback(task.id))
        layout.addWidget(self.btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.btn.click()
        super().mousePressEvent(event)


class AtlasDashboardTab(BaseTab):
    """
    v4.0 "Atlas" Task-Based Home Dashboard.
    Replaces the traditional overview with a goal-oriented interface.
    """
    _METADATA = PluginMetadata(
        id="atlas_dashboard",
        name="Home",
        description="Guided task-based control center for your Fedora system.",
        category="System",
        icon="home",
        badge="recommended",
        order=0,
    )

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window

        # Initialize backend
        self.registry = HealthRegistry()
        self.task_manager = TaskManager(self.registry)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        # Header
        header = make_page_title(f"Loofi Fedora Tweaks v{__version__} \"{__version_codename__}\"")
        layout.addWidget(header)

        subheader = QLabel("Fedora control center for everyday maintenance, safety, and setup tasks.")
        subheader.setObjectName("atlasSubheader")
        subheader.setWordWrap(True)
        layout.addWidget(subheader)

        overview_card = RouteCard(
            "System overview",
            "Open the live dashboard for health, resource graphs, recent actions, and quick actions.",
        )
        overview_card.mousePressEvent = lambda event: self._open_route("dashboard")  # type: ignore[method-assign]
        layout.addWidget(overview_card)

        upgrade_card = RouteCard(
            "Upgrade Assistant",
            "Review Fedora 44 readiness, Fedora 45 preview changes, safe action previews, verification, and support export.",
        )
        upgrade_card.mousePressEvent = lambda event: self._open_route("maintenance:upgrade-assistant")  # type: ignore[method-assign]
        layout.addWidget(upgrade_card)

        # Task Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        grid_container = QWidget()
        self.grid = AdaptiveGrid(min_column_width=300, parent=grid_container)
        grid_layout = QVBoxLayout(grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(self.grid)

        self._refresh_tasks()

        scroll.setWidget(grid_container)
        layout.addWidget(scroll)

        layout.addStretch()

    def _refresh_tasks(self):
        # Clear existing
        for card in list(getattr(self.grid, "_items", [])):
            card.deleteLater()
        self.grid._items.clear()
        self.grid._columns = 0

        tasks = self.task_manager.get_tasks()
        for task in tasks:
            card = TaskCard(task, self._on_task_clicked)
            self.grid.add_card(card)

    def _open_route(self, route_id: str):
        main_window = self.main_window
        if main_window is None:
            main_window = self.window() if hasattr(self, "window") else None
        switch = getattr(main_window, "switch_to_route", None)
        if callable(switch):
            switch(route_id)

    def _on_task_clicked(self, task_id: str):
        logger.info("Task clicked: %s", task_id)

        # Find task details
        task = next((t for t in self.task_manager.get_tasks() if t.id == task_id), None)
        if not task:
            return

        try:
            if task_id == "task-support-bundle":
                from .support_bundle_wizard import SupportBundleWizard
                wizard = SupportBundleWizard(self)
                wizard.exec()
                return

            if task_id in {"task-release-readiness", "task-fedora44-readiness"}:
                from .release_readiness_dialog import ReleaseReadinessDialog
                dialog = ReleaseReadinessDialog("44", self)
                dialog.exec()
                return

            from .task_wizard import AtlasTaskWizard
            task_wizard = AtlasTaskWizard(task.id, task.check_ids, task.action_ids, self)
            task_wizard.exec()
        except (ImportError, RuntimeError, OSError, ValueError) as e:
            logger.error("Failed to launch Atlas Task Wizard: %s", e, exc_info=True)
