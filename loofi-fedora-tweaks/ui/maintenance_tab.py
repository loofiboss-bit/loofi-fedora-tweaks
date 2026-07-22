"""
Maintenance Tab - Consolidated tab merging Updates, Cleanup, and Overlays.
Part of v11.0 "Aurora Update".

Uses a lazy route-owned stack to preserve all features from the
original UpdatesTab, CleanupTab, and OverlaysTab.
The Overlays sub-tab is only shown on Atomic (rpm-ostree) systems.
"""

# flake8: noqa: F401

from services.system.system import cached_which

from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from services.system import SystemManager
from utils.commands import PrivilegedCommand

from ui.base_tab import BaseTab
from ui.components.layout import PageScaffold
from ui.design import semantic_qcolor
from ui.shared_states import ActionProgress, DetailsDisclosure, ResultBanner
from ui.tooltips import MAINT_CLEANUP, MAINT_JOURNAL, MAINT_ORPHANS

# ---------------------------------------------------------------------------
# Sub-tab: Updates
# ---------------------------------------------------------------------------


from ui.maintenance_action_center import (
    _ActionCenterOperationWorker,
    _ActionCenterSubTab,
    _HealthTimelineSubTab,
)
from ui.maintenance_updates import (
    _CleanupSubTab,
    _OverlaysSubTab,
    _SmartUpdatesSubTab,
    _UpdatesSubTab,
    _UpgradeAssistantSubTab,
)


class MaintenanceTab(BaseTab):
    """Consolidated maintenance tab merging Updates, Cleanup, and Overlays.

    Uses a lazy route-owned stack. The Overlays page is only present when
    the system is detected as Atomic (rpm-ostree based).
    """

    _METADATA = plugin_metadata_for_module(__name__)

    actionCenterRequested = pyqtSignal(str, object)

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QStackedWidget()
        self.tabs.setObjectName("maintenanceRouteStack")

        self._sub_tab_factories = [
            (self.tr("Updates"), _UpdatesSubTab),
            (self.tr("Action Center"), _ActionCenterSubTab),
            (self.tr("Cleanup"), _CleanupSubTab),
            (self.tr("Health Timeline"), _HealthTimelineSubTab),
            (self.tr("Upgrade Assistant"), _UpgradeAssistantSubTab),
        ]

        if SystemManager.is_atomic():
            self._sub_tab_factories.append((self.tr("Overlays"), _OverlaysSubTab))

        self._loaded_tabs = {}

        for _label, _factory in self._sub_tab_factories:
            placeholder = QWidget()
            self.tabs.addWidget(placeholder)

        self.tabs.currentChanged.connect(self._lazy_load_sub_tab)
        self._lazy_load_sub_tab(0)

        layout.addWidget(self.tabs)

    def _lazy_load_sub_tab(self, index):
        """Instantiate sub-tab on first visit to avoid eager construction."""
        if index in self._loaded_tabs:
            return

        if index < len(self._sub_tab_factories):
            _label, factory = self._sub_tab_factories[index]
            widget = factory()
            request = getattr(widget, "actionCenterRequested", None)
            if request is not None and hasattr(request, "connect"):
                request.connect(self._open_action_center)
            self._loaded_tabs[index] = widget
            self.tabs.blockSignals(True)
            placeholder = self.tabs.widget(index)
            self.tabs.removeWidget(placeholder)
            placeholder.deleteLater()
            self.tabs.insertWidget(index, widget)
            self.tabs.setCurrentIndex(index)
            self.tabs.blockSignals(False)

    def _open_action_center(self, action_id: str, parameters=None) -> None:
        self.preselect_action(action_id, parameters)

    def preselect_action(self, action_id: str, parameters=None) -> bool:
        """Open Action Center and preselect one candidate without side effects."""
        for index, (label, _factory) in enumerate(self._sub_tab_factories):
            if label != self.tr("Action Center"):
                continue
            self.tabs.setCurrentIndex(index)
            self._lazy_load_sub_tab(index)
            action_center = self._loaded_tabs.get(index)
            preselect = getattr(action_center, "preselect_action", None)
            if not callable(preselect):
                return False
            if parameters is None:
                return bool(preselect(action_id))
            return bool(preselect(action_id, parameters))
        return False
    def activate_route(self, route) -> bool:
        """Resolve stable Maintenance subroutes after presentation consolidation."""
        original_subroute = str(getattr(route, "subroute", "") or "")
        subroute = "updates" if original_subroute == "smart-updates" else original_subroute
        labels = {
            "updates": self.tr("Updates"),
            "cleanup": self.tr("Cleanup"),
            "health-timeline": self.tr("Health Timeline"),
            "action-center": self.tr("Action Center"),
            "upgrade-assistant": self.tr("Upgrade Assistant"),
            "overlays": self.tr("Overlays"),
        }
        wanted = labels.get(subroute)
        if wanted is None:
            if subroute:
                return False
            self.tabs.setCurrentIndex(0)
            self._lazy_load_sub_tab(0)
            return True
        for index, (label, _factory) in enumerate(self._sub_tab_factories):
            if label != wanted:
                continue
            self.tabs.setCurrentIndex(index)
            self._lazy_load_sub_tab(index)
            if original_subroute == "smart-updates":
                reveal = getattr(
                    self._loaded_tabs.get(index),
                    "reveal_advanced_options",
                    None,
                )
                if callable(reveal):
                    reveal()
            return True
        return False
