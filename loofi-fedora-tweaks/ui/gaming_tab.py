"""Gaming optimization tools and package operations."""

from core.plugins.metadata import PluginMetadata
from core.product_catalog import plugin_metadata_for_module
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from utils.gaming_utils import GamingUtils
from utils.log import get_logger

from ui.base_tab import BaseTab
from ui.components import PageScaffold

logger = get_logger(__name__)


class GamingTab(BaseTab):

    actionCenterRequested = pyqtSignal(str, object)

    _METADATA = plugin_metadata_for_module(__name__)

    def metadata(self) -> PluginMetadata:
        return self._METADATA

    def create_widget(self) -> QWidget:
        return self

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scaffold = PageScaffold(
            self.tr("Gaming tools"),
            self.tr("Install optional performance and compatibility tools for games."),
        )
        root.addWidget(self.scaffold)
        layout = self.scaffold.content_layout

        # Performance Tools Group
        perf_group = QGroupBox(self.tr("Performance Tools"))
        perf_layout = QVBoxLayout()
        perf_group.setLayout(perf_layout)

        # Feral Gamemode
        self.btn_gamemode = QPushButton(self.tr("Install Feral GameMode"))
        self.btn_gamemode.setAccessibleName(self.tr("Install GameMode"))
        self.btn_gamemode.clicked.connect(self.install_gamemode)
        perf_layout.addWidget(self.btn_gamemode)

        self.lbl_gamemode_status = QLabel(self.tr("GameMode Status: Unknown"))
        perf_layout.addWidget(self.lbl_gamemode_status)

        # MangoHud
        btn_mangohud = QPushButton(self.tr("Install MangoHud & Goverlay"))
        btn_mangohud.setAccessibleName(self.tr("Install MangoHud"))
        btn_mangohud.clicked.connect(self.install_mangohud)
        perf_layout.addWidget(btn_mangohud)

        layout.addWidget(perf_group)

        # Steam Utilities
        steam_group = QGroupBox(self.tr("Steam Utilities"))
        steam_layout = QVBoxLayout()
        steam_group.setLayout(steam_layout)

        # ProtonUp-Qt
        btn_protonup = QPushButton(self.tr("Install ProtonUp-Qt (Flatpak)"))
        btn_protonup.setAccessibleName(self.tr("Install ProtonUp-Qt"))
        btn_protonup.clicked.connect(self.install_protonup)
        steam_layout.addWidget(btn_protonup)

        # Steam Devices
        btn_steam_devices = QPushButton(self.tr("Install Steam Devices (Controller Support)"))
        btn_steam_devices.setAccessibleName(self.tr("Install Steam Devices"))
        btn_steam_devices.clicked.connect(self.install_steam_devices)
        steam_layout.addWidget(btn_steam_devices)

        layout.addWidget(steam_group)

        self.add_output_disclosure(layout, self.tr("Show gaming operation output"))
        layout.addStretch()

        # Check status
        self.check_gamemode_status()

    def install_gamemode(self):
        self.actionCenterRequested.emit("install-application", {"source": "fedora", "package_id": "gamemode"})
        QMessageBox.information(self, self.tr("Review required"), self.tr("Review the GameMode install plan in Action Center."))

    def check_gamemode_status(self):
        status = GamingUtils.get_gamemode_status()
        if status == "active":
            self.lbl_gamemode_status.setText(
                self.tr("GameMode Status: Active (Service Running)"))
            self.btn_gamemode.setEnabled(False)
            self.btn_gamemode.setText(self.tr("GameMode Installed"))
        elif status == "installed":
            self.lbl_gamemode_status.setText(
                self.tr("GameMode Status: Installed but Inactive"))
            self.btn_gamemode.setText(self.tr("Reinstall GameMode"))
        elif status == "missing":
            self.lbl_gamemode_status.setText(
                self.tr("GameMode Status: Not Installed"))
        else:
            self.lbl_gamemode_status.setText(
                self.tr("Status check failed"))

    def install_mangohud(self):
        self.actionCenterRequested.emit("install-application", {"source": "fedora", "package_id": "mangohud"})
        QMessageBox.information(
            self,
            self.tr("Review required"),
            self.tr("Review the MangoHud install plan in Action Center. Goverlay can be planned separately."),
        )

    def install_protonup(self):
        self.actionCenterRequested.emit(
            "install-application",
            {"source": "flatpak", "package_id": "net.davidotek.pupgui2"},
        )
        QMessageBox.information(self, self.tr("Review required"), self.tr("Review the ProtonUp-Qt install plan in Action Center."))

    def install_steam_devices(self):
        self.actionCenterRequested.emit("install-application", {"source": "fedora", "package_id": "steam-devices"})
        QMessageBox.information(self, self.tr("Review required"), self.tr("Review the Steam Devices install plan in Action Center."))
