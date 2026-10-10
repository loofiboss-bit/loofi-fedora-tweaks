"""Health storage presentation using saved source evidence only."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QLabel, QPushButton, QSizePolicy

from ui.components import Card


def _size(value: object) -> str:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return ""
    number = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if number < 1024 or unit == "TiB":
            return f"{number:.1f} {unit}"
        number /= 1024
    return ""


class SpaceGuideCard(Card):
    actionRequested = pyqtSignal(str, object)
    routeRequested = pyqtSignal(str, object)
    recheckRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(self.tr("Storage space guide"), parent=parent)
        self.setObjectName("spaceGuideCard")
        self.observations = QLabel()
        self.observations.setWordWrap(True)
        self.observations.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.observations.setTextFormat(Qt.TextFormat.PlainText)
        self.observations.setAccessibleName(self.tr("Measured storage observations"))
        self.add_widget(self.observations)
        guidance = QLabel(self.tr("Measured sizes are not promised disk savings. DNF cache may need downloading again. "
                                  "System journal size is measured data, not a cleanup estimate; review log retention manually."))
        guidance.setWordWrap(True)
        self.add_widget(guidance)
        self.cache_button = QPushButton(self.tr("Review DNF cache cleanup"))
        self.cache_button.clicked.connect(lambda: self.actionRequested.emit("dnf-clean-all", {}))
        self.add_widget(self.cache_button)
        self.installation = QComboBox()
        self.installation.setAccessibleName(self.tr("Flatpak installation to inspect"))
        self.installation.addItem(self.tr("Current user"), "user")
        self.installation.addItem(self.tr("System"), "system")
        self.add_widget(self.installation)
        self.runtime_button = QPushButton(self.tr("Inspect unused Flatpak runtimes"))
        self.runtime_button.clicked.connect(lambda: self.routeRequested.emit(
            "software:apps", {"section": "unused-runtimes", "installation": self.installation.currentData()}))
        self.add_widget(self.runtime_button)
        self.recheck_button = QPushButton(self.tr("Check again"))
        self.recheck_button.clicked.connect(self.recheckRequested)
        self.add_widget(self.recheck_button)

    def set_observation(self, data: dict | None) -> None:
        self.setVisible(data is not None)
        if data is None:
            return
        lines = []
        stamp = data.get("sampled_at")
        if isinstance(stamp, (int, float)):
            lines.append(self.tr("Observed: %1").replace("%1", datetime.fromtimestamp(stamp).astimezone().strftime("%Y-%m-%d %H:%M")))
        for row in data.get("filesystems", ()):
            paths = row.get("paths", "")
            free = _size(row.get("free_bytes"))
            if row.get("state") == "observed" and free:
                lines.append(self.tr("%1: %2% used · %3 free").replace("%1", paths).replace("%2", str(row.get("percent_used"))).replace("%3", free))
            else:
                lines.append(self.tr("%1: measurement unavailable").replace("%1", paths))
        atomic = bool(data.get("atomic"))
        cache = data.get("package_cache_bytes")
        cache_text = self.tr("Unavailable on Atomic") if atomic else _size(cache) or self.tr("Unknown / incomplete")
        lines.append(self.tr("DNF cache: %1").replace("%1", cache_text))
        lines.append(self.tr("System journal: %1").replace("%1", _size(data.get("journal_bytes")) or self.tr("Unknown")))
        self.observations.setText("\n".join(lines))
        self.observations.setMinimumHeight(self.observations.fontMetrics().lineSpacing() * len(lines) + 4)
        self.cache_button.setEnabled(not atomic and isinstance(cache, int) and not isinstance(cache, bool) and cache > 0)
