"""Read-only, responsive system overview backed by the shared sampler."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import math

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.plugins.interface import PluginInterface
from core.product_catalog import plugin_metadata_for_module
from ui.components.actions import QuietButton, SecondaryButton
from ui.components.cards import Card
from ui.components.feedback import InlineNotice, StatusBadge
from ui.design import semantic_qcolor


class MetricGraph(QWidget):
    """Bounded unit-aware graph; unavailable samples leave real gaps."""

    def __init__(self, label: str, unit: str, parent=None):
        super().__init__(parent)
        self.label, self.unit = label, unit
        self.points: deque[float | None] = deque(maxlen=60)
        self.setMinimumHeight(56)
        self.setAccessibleName(label)
        self.setAccessibleDescription(self.tr("Recent measurements in %1").replace("%1", unit))

    def add_sample(self, value):
        value = float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None
        self.points.append(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(semantic_qcolor("border"), 1))
        painter.drawLine(0, self.height() - 8, self.width(), self.height() - 8)
        values = [value for value in self.points if value is not None]
        if not values or len(self.points) < 2:
            return
        scale = 100 if self.unit == "%" else max(max(values), 1)
        path = QPainterPath()
        connected = False
        for index, value in enumerate(self.points):
            if value is None:
                connected = False
                continue
            point = QPointF(index * self.width() / max(len(self.points) - 1, 1),
                            self.height() - 8 - min(value / scale, 1) * (self.height() - 16))
            if connected:
                path.lineTo(point)
            else:
                path.moveTo(point)
            connected = True
        painter.setPen(QPen(semantic_qcolor("accent"), 2))
        painter.drawPath(path)


class _MetricRow(QWidget):
    def __init__(self, reading, parent=None):
        super().__init__(parent)
        self.last_sample = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setObjectName("definitionLabel")
        self.value = QLabel()
        self.value.setWordWrap(True)
        self.value.setTextFormat(Qt.TextFormat.PlainText)
        self.value.setObjectName("definitionValue")
        self.reason = QLabel()
        self.reason.setWordWrap(True)
        self.reason.setTextFormat(Qt.TextFormat.PlainText)
        self.reason.setObjectName("cardDescription")
        self.badge = StatusBadge(self.tr("Collecting"))
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.reason)
        self.graph = MetricGraph(reading.label, reading.unit, self)
        layout.addWidget(self.graph)
        self.update_reading(reading)

    def update_reading(self, reading):
        status = getattr(reading.status, "value", reading.status)
        valid = status in ("ready", "ok", "valid", "available")
        stale = status == "stale"
        self.label.setText(self.tr(reading.label))
        value = reading.value
        if isinstance(value, float):
            text = f"{value:,.1f}"
        elif value is None:
            text = self.tr("Waiting for measurement") if status in ("loading", "sampling") else self.tr("Unavailable")
        else:
            text = str(value)
        if value is not None:
            if reading.unit in ("B", "bytes", "B/s") and isinstance(value, (int, float)):
                magnitude = float(value)
                units = ["B", "KiB", "MiB", "GiB", "TiB"]
                index = 0
                while abs(magnitude) >= 1024 and index < len(units) - 1:
                    magnitude /= 1024
                    index += 1
                text = f"{magnitude:,.1f} {units[index]}" + ("/s" if reading.unit == "B/s" else "")
            elif reading.unit:
                text += " " + reading.unit
        self.value.setText(text)
        reason = " · ".join(self.tr(part) for part in (reading.reason, reading.detail) if part)
        self.reason.setText(reason)
        self.reason.setVisible(bool(reason))
        kind, caption = "neutral", self.tr("Unavailable")
        if valid:
            kind, caption = "success", self.tr("Measured")
            if isinstance(value, (int, float)) and reading.critical is not None and value >= reading.critical:
                kind, caption = "error", self.tr("Critical")
            elif isinstance(value, (int, float)) and reading.high is not None and value >= reading.high:
                kind, caption = "warning", self.tr("High")
        elif stale:
            kind, caption = "warning", self.tr("Last known value")
        elif status == "error":
            kind, caption = "error", self.tr("Read failed")
        elif status in ("loading", "sampling"):
            kind, caption = "info", self.tr("Collecting")
        self.badge.set_status(caption, kind=kind, description=reason)
        stamp = reading.sampled_at
        timestamp = _format_time(stamp)
        self.setToolTip(self.tr("Source: %1\nMeasured: %2").replace("%1", reading.source).replace("%2", timestamp))
        self.setAccessibleName(self.tr(reading.label))
        self.setAccessibleDescription(" · ".join((text, caption, reason, timestamp)))
        graphable = reading.group in ("cpu", "memory", "network", "disk") and reading.unit in ("%", "B/s", "bytes/s")
        self.graph.setVisible(graphable)
        if stamp != self.last_sample:
            self.graph.add_sample(value if valid else None)
            self.last_sample = stamp


def _format_time(value):
    if isinstance(value, datetime):
        return value.astimezone().strftime("%x %X")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).astimezone().strftime("%x %X")
    return str(value or "")


class OverviewPage(QWidget, PluginInterface):
    routeRequested = pyqtSignal(str)
    refreshRequested = pyqtSignal()

    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self.profile = profile
        self._controller = None
        self._active = False
        self._paused = False
        self._snapshot = None
        self._columns = 0
        self._rows = {}
        self._cards = {}
        self._empty = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(16)
        header = QHBoxLayout()
        self.identity = QLabel(self.tr("System information will appear after the first measurement."))
        self.identity.setWordWrap(True)
        self.identity.setTextFormat(Qt.TextFormat.PlainText)
        self.identity.setObjectName("cardDescription")
        header.addWidget(self.identity, 1)
        self.pause_button = QuietButton(self.tr("Pause"), description=self.tr("Pause live measurements"))
        self.pause_button.clicked.connect(self._toggle_pause)
        self.refresh_button = SecondaryButton(self.tr("Refresh"), description=self.tr("Refresh system measurements"))
        self.refresh_button.clicked.connect(self._refresh)
        header.addWidget(self.pause_button)
        header.addWidget(self.refresh_button)
        root.addLayout(header)
        self.notice = InlineNotice(self.tr("Collecting system information"), self.tr("Measurements run while this page is visible."))
        root.addWidget(self.notice)
        self.main_grid = QGridLayout()
        self.main_grid.setSpacing(16)
        root.addLayout(self.main_grid)
        self.detail_grid = QGridLayout()
        self.detail_grid.setSpacing(16)
        root.addLayout(self.detail_grid)
        groups = (("cpu", self.tr("CPU")), ("memory", self.tr("RAM")), ("gpu", self.tr("GPU")),
                  ("storage", self.tr("Storage")), ("network", self.tr("Network activity")),
                  ("disk", self.tr("Disk activity")), ("temperature", self.tr("Temperatures")), ("battery", self.tr("Battery")))
        for group, title in groups:
            card = Card(title, parent=self)
            empty = QLabel(self.tr("Waiting for measurements"))
            empty.setWordWrap(True)
            empty.setObjectName("cardDescription")
            card.add_widget(empty)
            self._cards[group] = card
            self._empty[group] = empty
        self.maintenance_grid = QGridLayout()
        self.maintenance_grid.setSpacing(16)
        root.addLayout(self.maintenance_grid)
        self._maintenance = {}
        for key, title, route in (("updates", self.tr("Updates"), "maintenance:updates"), ("health", self.tr("Health"), "maintenance:health-timeline"),
                                  ("activity", self.tr("Recent activity"), "changes")):
            card = Card(title)
            label = QLabel(self.tr("No recorded result yet"))
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            card.add_widget(label)
            button = QuietButton(self.tr("Open %1").replace("%1", title))
            button.clicked.connect(lambda checked=False, destination=route: self.routeRequested.emit(destination))
            card.add_widget(button)
            self._maintenance[key] = (card, label)
        root.addStretch()
        self._reflow(900)

    def metadata(self):
        return plugin_metadata_for_module(__name__)

    def create_widget(self):
        return self

    def set_controller(self, controller):
        if self._controller is controller:
            return
        if self._controller is not None:
            self._controller.set_consumer_active("overview", False)
            self._controller.snapshotReady.disconnect(self.set_snapshot)
            self._controller.failed.disconnect(self._show_error)
        self._controller = controller
        controller.snapshotReady.connect(self.set_snapshot)
        controller.failed.connect(self._show_error)
        if controller.latest_snapshot is not None:
            self.set_snapshot(controller.latest_snapshot)
        controller.set_consumer_active("overview", self._active and not self._paused)

    def set_active(self, active):
        self._active = active
        if self._controller is not None:
            self._controller.set_consumer_active("overview", active and not self._paused)

    def on_activate(self):
        self.set_active(True)

    def on_deactivate(self):
        self.set_active(False)

    def _toggle_pause(self):
        self._paused = not self._paused
        self.pause_button.setText(self.tr("Resume") if self._paused else self.tr("Pause"))
        self.refresh_button.setEnabled(not self._paused)
        self.set_active(self._active)
        if self._paused:
            self.notice.set_notice("neutral", self.tr("Measurements paused"), self.tr("Displayed values are the last recorded measurements."))

    def _refresh(self):
        self.refreshRequested.emit()
        if self._controller is not None:
            self._controller.refresh()

    def _show_error(self, reason):
        self.notice.set_notice("error", self.tr("Unable to refresh measurements"), reason)

    def set_snapshot(self, snapshot):
        if self._paused:
            return
        if self._snapshot is not None and snapshot.collected_at < self._snapshot.collected_at:
            return
        self._snapshot = snapshot
        maintenance = getattr(snapshot, "maintenance", None)
        if maintenance:
            self.set_maintenance(**{key: maintenance[key] for key in ("updates", "health", "activity") if key in maintenance})
        identity_keys = ("hostname", "os", "desktop", "deployment", "cpu", "kernel")
        self.identity.setText(" · ".join(str(snapshot.identity[key]) for key in identity_keys if snapshot.identity.get(key)))
        self.notice.set_notice("info", self.tr("Last measured: %1").replace("%1", _format_time(snapshot.collected_at)),
                               self.tr("Live measurements refresh every two seconds; sensors every five seconds."))
        present = set()
        for reading in snapshot.metrics:
            if reading.group not in self._cards:
                continue
            present.add(reading.id)
            if reading.id not in self._rows:
                row = _MetricRow(reading, self._cards[reading.group])
                self._cards[reading.group].add_widget(row)
                self._rows[reading.id] = row
            else:
                self._rows[reading.id].update_reading(reading)
            self._rows[reading.id].show()
        for key, row in list(self._rows.items()):
            if key not in present:
                row.setParent(None)
                row.deleteLater()
                del self._rows[key]
        groups = {reading.group for reading in snapshot.metrics}
        for group, label in self._empty.items():
            label.setVisible(group not in groups)
            label.setText(self.tr("No available data source"))

    def set_maintenance(self, updates=None, health=None, activity=None):
        """Present caller-supplied real cached results; never initiate checks."""
        for key, result in (("updates", updates), ("health", health), ("activity", activity)):
            if result is None:
                continue
            if isinstance(result, dict):
                detail = str(result.get("summary", result.get("detail", "")))
                status = str(result.get("status", ""))
                text = " · ".join(self.tr(part) for part in (status.replace("_", " "), detail) if part)
                if result.get("sources"):
                    lines = []
                    for source in result["sources"]:
                        caption = self.tr("%1: %2 · %3 updates").replace("%1", self.tr(str(source.get("source", ""))))
                        caption = caption.replace("%2", self.tr(str(source.get("status", "unchecked"))))
                        caption = caption.replace("%3", str(source.get("count", 0)))
                        if source.get("stale"):
                            caption += " · " + self.tr("Last known result")
                        if source.get("sampled_at"):
                            caption += " · " + _format_time(source["sampled_at"])
                        lines.append(caption)
                    text = "\n".join(lines)
                stamp = result.get("checked_at", result.get("timestamp", result.get("sampled_at", "")))
                if stamp:
                    text += "\n" + _format_time(stamp)
            else:
                text = str(result)
            self._maintenance[key][1].setText(text or self.tr("No recorded result yet"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow(event.size().width())

    def _reflow(self, width):
        minimum_card_width = max(224, self.fontMetrics().horizontalAdvance(self.tr("Graphics memory")) + 48)
        four_panel_width = max(960, minimum_card_width * 4 + 48)
        two_panel_width = max(600, minimum_card_width * 2 + 16)
        columns = 4 if width >= four_panel_width else 2 if width >= two_panel_width else 1
        if columns == self._columns:
            return
        self._columns = columns
        for grid in (self.main_grid, self.detail_grid, self.maintenance_grid):
            while grid.count():
                grid.takeAt(0)
            for column in range(4):
                grid.setColumnStretch(column, 0)
        for index, group in enumerate(("cpu", "memory", "gpu", "storage")):
            self.main_grid.addWidget(self._cards[group], index // columns, index % columns)
        details = min(columns, 2)
        for index, group in enumerate(("network", "disk", "temperature", "battery")):
            self.detail_grid.addWidget(self._cards[group], index // details, index % details)
        for index, (card, label) in enumerate(self._maintenance.values()):
            self.maintenance_grid.addWidget(card, index // details, index % details)
        for column in range(columns):
            self.main_grid.setColumnStretch(column, 1)
        for column in range(details):
            self.detail_grid.setColumnStretch(column, 1)
            self.maintenance_grid.setColumnStretch(column, 1)

    def cleanup(self):
        self.set_active(False)
