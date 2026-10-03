"""Atlas dashboard tab shim for backward compatibility and catalog projection."""

from core.plugins.interface import PluginInterface
from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from PyQt6.QtWidgets import QWidget
from ui.tweaks_page import TweaksPage


class AtlasDashboardTab(TweaksPage, PluginInterface):
    """Backward compatibility alias for TweaksPage."""

    _METADATA = plugin_metadata_for_module(__name__)

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self
