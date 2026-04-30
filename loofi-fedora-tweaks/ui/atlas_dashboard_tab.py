from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt
from .base_tab import BaseTab
from core.plugins.metadata import PluginMetadata
from core.diagnostics.task_dashboard import TaskManager, DashboardTask
from core.diagnostics.health_registry import HealthRegistry
from .icon_pack import get_qicon
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
        self.setObjectName("dashboardCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Icon and Title
        header = QHBoxLayout()
        icon_label = QLabel()
        try:
            icon_label.setPixmap(get_qicon(task.icon_id, size=32).pixmap(32, 32))
        except (OSError, RuntimeError, ValueError):
            logger.debug("Unable to load dashboard icon %s", task.icon_id, exc_info=True)
        header.addWidget(icon_label)

        title = QLabel(task.title)
        title.setObjectName("healthTitle")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title, 1)
        layout.addLayout(header)

        # Description
        desc = QLabel(task.description)
        desc.setWordWrap(True)
        desc.setObjectName("healthRecs")
        layout.addWidget(desc)

        layout.addStretch()

        # Action Button
        self.btn = QPushButton("View Task")
        self.btn.setObjectName("quickActionButton")
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
        name="Atlas Home",
        description="Guided task-based control center for your Fedora system.",
        category="System",
        icon="home",
        badge="new",
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
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        header = QLabel(f"Loofi Fedora Tweaks v{__version__} \"{__version_codename__}\"")
        header.setObjectName("header")
        layout.addWidget(header)

        subheader = QLabel("Guided Fedora Control Center — What would you like to do today?")
        subheader.setStyleSheet("font-size: 14px; color: #6c7086;")
        layout.addWidget(subheader)

        # Task Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        grid_container = QWidget()
        self.grid = QGridLayout(grid_container)
        self.grid.setSpacing(20)

        self._refresh_tasks()

        scroll.setWidget(grid_container)
        layout.addWidget(scroll)

        layout.addStretch()

    def _refresh_tasks(self):
        # Clear existing
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tasks = self.task_manager.get_tasks()
        for i, task in enumerate(tasks):
            row, col = divmod(i, 2)
            card = TaskCard(task, self._on_task_clicked)
            self.grid.addWidget(card, row, col)

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

            if task_id == "task-fedora44-readiness":
                from .fedora44_readiness_dialog import Fedora44ReadinessDialog
                dialog = Fedora44ReadinessDialog(self)
                dialog.exec()
                return

            from .task_wizard import AtlasTaskWizard
            wizard = AtlasTaskWizard(task.id, task.check_ids, task.action_ids, self)
            wizard.exec()
        except (ImportError, RuntimeError, OSError, ValueError) as e:
            logger.error("Failed to launch Atlas Task Wizard: %s", e, exc_info=True)
