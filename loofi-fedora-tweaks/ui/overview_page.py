"""Read-only, responsive system overview backed by the shared sampler."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import math

from PyQt6.QtCore import QPointF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from core.plugins.interface import PluginInterface
from core.tasks.next_steps import next_steps
from core.product_catalog import plugin_metadata_for_module
from ui.components.actions import QuietButton, SecondaryButton
from ui.components.cards import Card
from ui.components.feedback import InlineNotice, StatusBadge
from ui.design import semantic_qcolor
from ui.guide_panel import GuidePanel


class MetricGraph(QWidget):
    """Bounded unit-aware graph; unavailable samples leave real gaps."""

    def __init__(self, label: str, unit: str, parent=None):
        super().__init__(parent)
        self.label, self.unit = label, unit
        self.points: deque[float | None] = deque(maxlen=60)
        self.setMinimumHeight(44)
        self.setAccessibleName(label)
        self.setAccessibleDescription(self.tr("Recent measurements in %1").replace("%1", unit))

    def add_sample(self, value):
        value = float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None
        self.points.append(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        baseline_y = self.height() - 6
        painter.setPen(QPen(semantic_qcolor("border", 50), 1))
        painter.drawLine(0, baseline_y, self.width(), baseline_y)

        values = [value for value in self.points if value is not None]
        if not values or len(self.points) < 2:
            return

        scale = 100.0 if self.unit == "%" else max(max(values), 1.0)
        line_path = QPainterPath()
        connected = False
        count = len(self.points)
        step = self.width() / max(count - 1, 1)
        first_point = None
        last_point = None

        for index, value in enumerate(self.points):
            if value is None:
                connected = False
                continue
            x = index * step
            norm_val = min(max(value, 0.0) / scale, 1.0)
            y = baseline_y - norm_val * (self.height() - 12)
            point = QPointF(x, y)
            if connected:
                line_path.lineTo(point)
            else:
                line_path.moveTo(point)
                first_point = point
            connected = True
            last_point = point

        if first_point is not None and last_point is not None:
            area_path = QPainterPath(line_path)
            area_path.lineTo(last_point.x(), baseline_y)
            area_path.lineTo(first_point.x(), baseline_y)
            area_path.closeSubpath()

            grad = QLinearGradient(0, 0, 0, baseline_y)
            grad.setColorAt(0.0, semantic_qcolor("accent", 45))
            grad.setColorAt(1.0, semantic_qcolor("accent", 0))
            painter.fillPath(area_path, grad)

        painter.setPen(QPen(semantic_qcolor("accent"), 2))
        painter.drawPath(line_path)

        if last_point is not None:
            painter.setPen(QPen(semantic_qcolor("window"), 1.5))
            painter.setBrush(semantic_qcolor("accent"))
            painter.drawEllipse(last_point, 3.0, 3.0)


class _MetricRow(QWidget):
    def __init__(self, reading, parent=None):
        super().__init__(parent)
        self.last_sample = None
        self.is_compact = reading.group == "temperature"

        self.label = QLabel()
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setObjectName("definitionLabel")

        self.value = QLabel()
        self.value.setTextFormat(Qt.TextFormat.PlainText)
        self.value.setObjectName("dashboardMetricValue" if self.is_compact else "dashboardMetricHeroValue")
        value_font = QFont(self.font())
        if self.is_compact:
            value_font.setWeight(QFont.Weight.DemiBold)
        else:
            value_font.setPointSizeF(max(10.0, value_font.pointSizeF()) * 1.35)
            value_font.setWeight(QFont.Weight.DemiBold)
        self.value.setFont(value_font)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setObjectName("metricProgressBar")
        self.progress.hide()

        self.reason = QLabel()
        self.reason.setTextFormat(Qt.TextFormat.PlainText)
        self.reason.setObjectName("cardDescription")

        self.badge = StatusBadge(self.tr("Collecting"))
        self.graph = MetricGraph(reading.label, reading.unit, self)

        if self.is_compact:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(6)
            self.label.setWordWrap(False)
            self.value.setWordWrap(False)
            self.reason.hide()
            self.graph.hide()
            layout.addWidget(self.label, 1)
            layout.addWidget(self.value, 0)
            layout.addWidget(self.badge, 0)
        else:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(2)
            self.label.setWordWrap(True)
            self.value.setWordWrap(True)
            self.reason.setWordWrap(True)
            layout.addWidget(self.label)
            layout.addWidget(self.value)
            layout.addWidget(self.progress)
            layout.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self.reason)
            layout.addWidget(self.graph)

        self.update_reading(reading)

    def update_reading(self, reading):
        status = getattr(reading.status, "value", reading.status)
        valid = status in ("ready", "ok", "valid", "available")
        stale = status == "stale"
        if self.is_compact:
            display_label = reading.label
            if reading.detail and reading.detail.lower() not in reading.label.lower():
                display_label = f"{reading.detail} · {reading.label}"
            self.label.setText(self.tr(display_label))
            self.label.show()
        else:
            self.label.setText(self.tr(reading.label))
            if reading.label.strip().lower() == reading.group.strip().lower():
                self.label.hide()
            else:
                self.label.show()

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

        if not self.is_compact and reading.unit == "%" and isinstance(value, (int, float)) and valid:
            self.progress.setValue(int(min(max(value, 0.0), 100.0)))
            self.progress.show()
        else:
            self.progress.hide()

        reason = " · ".join(self.tr(part) for part in (reading.reason, reading.detail) if part)
        self.reason.setText(reason)
        if not self.is_compact:
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
        self.badge.setVisible(not (valid and caption == self.tr("Measured")))

        stamp = reading.sampled_at
        timestamp = _format_time(stamp)
        self.setToolTip(self.tr("Source: %1\nMeasured: %2").replace("%1", reading.source).replace("%2", timestamp))
        self.setAccessibleName(self.tr(reading.label))
        self.setAccessibleDescription(" · ".join((text, caption, reason, timestamp)))
        if not self.is_compact:
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
    contextRouteRequested = pyqtSignal(str, object)
    taskRequested = pyqtSignal(str)
    guideChanged = pyqtSignal(str)
    guideTargetRequested = pyqtSignal(object)
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
        self._has_registered_problem = False
        self._intro_dismissed = False
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 12)
        root.setSpacing(12)
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
        self.notice.setObjectName("overviewNotice")
        root.addWidget(self.notice)
        self.intro_card = Card(self.tr("Start with a useful setting"), self.tr("Find a control, review motion preferences, or see what is installed."), parent=self)
        self.intro_card.setObjectName("overviewIntro")
        self._intro_buttons = {}
        for task_id, title in (("click-behavior", "Find click behavior"), ("reduced-motion", "Review Reduced motion"), ("installed", "Open Installed")):
            button = QuietButton(self.tr(title))
            button.setAccessibleName(self.tr(title))
            button.clicked.connect(lambda _checked=False, selected=task_id: self.taskRequested.emit(selected))
            self.intro_card.add_widget(button)
            self._intro_buttons[task_id] = button
        self.dismiss_intro_button = QuietButton(self.tr("Dismiss"))
        self.dismiss_intro_button.clicked.connect(self._dismiss_intro)
        self.intro_card.add_widget(self.dismiss_intro_button)
        root.addWidget(self.intro_card)
        self.guide_panel = GuidePanel(self)
        self.guide_panel.guideChanged.connect(self.guideChanged)
        self.guide_panel.targetRequested.connect(self.guideTargetRequested)
        root.addWidget(self.guide_panel)
        self.next_steps_card = Card(self.tr("Next steps"), parent=self)
        self.next_steps_empty = QLabel(self.tr("Suggestions appear after the first measurement."))
        self.next_steps_empty.setWordWrap(True)
        self.next_steps_card.add_widget(self.next_steps_empty)
        self.next_steps_card.hide()
        self._next_step_rows = []
        self._last_next_steps = None
        root.addWidget(self.next_steps_card)
        self.main_grid = QGridLayout()
        self.main_grid.setSpacing(12)
        root.addLayout(self.main_grid)
        self.detail_grid = QGridLayout()
        self.detail_grid.setSpacing(12)
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
        self._temp_container = QWidget(self._cards["temperature"])
        self._temp_grid = QGridLayout(self._temp_container)
        self._temp_grid.setContentsMargins(0, 0, 0, 0)
        self._temp_grid.setHorizontalSpacing(16)
        self._temp_grid.setVerticalSpacing(2)
        self._cards["temperature"].add_widget(self._temp_container)
        self.maintenance_grid = QGridLayout()
        self.maintenance_grid.setSpacing(12)
        root.addLayout(self.maintenance_grid)
        self._maintenance = {}
        for key, title, route in (("updates", self.tr("Updates"), "maintenance:updates"), ("health", self.tr("Health"), "maintenance:health-timeline"),
                                  ("activity", self.tr("Recent activity"), "activity")):
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

    def open_guide(self, guide_id: str) -> bool:
        """Reveal and focus one guide requested by global discovery or the shell."""
        return bool(self.guide_panel.open_guide(guide_id))

    def create_widget(self):
        return self

    def set_platform_profile(self, profile) -> None:
        """Show only starter actions supported by the detected desktop."""
        self.profile = profile
        desktop = str(getattr(getattr(profile, "desktop", None), "value", "unknown"))
        self._intro_buttons["click-behavior"].setVisible(desktop in {"kde", "gnome"})
        try:
            from core.tasks.tweak_presets import profile_for_preset

            profile_for_preset("reduced-motion", profile)
            reduced_motion = True
        except (ImportError, ValueError, TypeError):
            reduced_motion = False
        self._intro_buttons["reduced-motion"].setVisible(reduced_motion)
        self._load_intro_preference()

    def _load_intro_preference(self) -> None:
        try:
            from utils.settings import SettingsManager

            self._intro_dismissed = bool(SettingsManager.instance().get("overview_intro_dismissed", False))
        except (ImportError, OSError, RuntimeError, TypeError, ValueError):
            self._intro_dismissed = False
        self._update_intro_visibility()

    def _dismiss_intro(self) -> None:
        try:
            from utils.settings import SettingsManager

            manager = SettingsManager.instance()
            previous = manager.get("overview_intro_dismissed", False)
            manager.set("overview_intro_dismissed", True)
            if not manager.save():
                manager.set("overview_intro_dismissed", previous)
                self.notice.set_notice("error", self.tr("Could not save preference"), self.tr("The introduction remains visible."))
                return
            self._intro_dismissed = True
            self._update_intro_visibility()
        except (ImportError, OSError, RuntimeError, TypeError, ValueError):
            self.notice.set_notice("error", self.tr("Could not save preference"), self.tr("The introduction remains visible."))

    def _update_intro_visibility(self) -> None:
        self.intro_card.setVisible(not self._intro_dismissed and not self._has_registered_problem)

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
        self.refresh_button.setEnabled(False)
        QTimer.singleShot(800, lambda: self.refresh_button.setEnabled(not self._paused))
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
        now = snapshot.collected_at.timestamp() if isinstance(snapshot.collected_at, datetime) else snapshot.collected_at
        self._show_next_steps(next_steps(maintenance or {}, snapshot.metrics, now=now))
        identity_keys = ("hostname", "os", "desktop", "deployment", "cpu", "kernel")
        self.identity.setText(" · ".join(str(snapshot.identity[key]) for key in identity_keys if snapshot.identity.get(key)))
        self.notice.set_notice("info", self.tr("Last measured: %1").replace("%1", _format_time(snapshot.collected_at)),
                               self.tr("Live measurements refresh every two seconds; sensors every five seconds."))
        present = set()
        temp_rows = []
        for reading in snapshot.metrics:
            if reading.group not in self._cards:
                continue
            present.add(reading.id)
            if reading.id not in self._rows:
                row = _MetricRow(reading, self._cards[reading.group])
                if reading.group != "temperature":
                    self._cards[reading.group].add_widget(row)
                self._rows[reading.id] = row
            else:
                self._rows[reading.id].update_reading(reading)
            self._rows[reading.id].show()
            if reading.group == "temperature":
                temp_rows.append(self._rows[reading.id])

        for idx, row in enumerate(temp_rows):
            r, c = divmod(idx, 2)
            if self._temp_grid.indexOf(row) != -1:
                self._temp_grid.removeWidget(row)
            self._temp_grid.addWidget(row, r, c)
        self._temp_container.setVisible(bool(temp_rows))

        for key, row in list(self._rows.items()):
            if key not in present:
                if self._temp_grid.indexOf(row) != -1:
                    self._temp_grid.removeWidget(row)
                row.setParent(None)
                row.deleteLater()
                del self._rows[key]
        groups = {reading.group for reading in snapshot.metrics}
        for group, label in self._empty.items():
            label.setVisible(group not in groups)
            label.setText(self.tr("No available data source"))
        has_battery = any(
            reading.group == "battery" and reading.id != "battery.none" and reading.status != "unavailable"
            for reading in snapshot.metrics
        )
        battery_card = self._cards.get("battery")
        if battery_card is not None:
            if not has_battery and not battery_card.isHidden():
                battery_card.hide()
                self._columns = 0
                self._reflow(self.width())
            elif has_battery and battery_card.isHidden():
                battery_card.show()
                self._columns = 0
                self._reflow(self.width())

    def _show_next_steps(self, suggestions):
        self._has_registered_problem = bool(suggestions)
        self._update_intro_visibility()
        self.next_steps_card.setVisible(bool(suggestions))
        if not suggestions:
            for row in self._next_step_rows:
                self.next_steps_card.body.removeWidget(row)
                row.setParent(None)
                row.deleteLater()
            self._next_step_rows = []
            self._last_next_steps = ()
            return
        if suggestions == self._last_next_steps:
            return
        previous = self._last_next_steps or ()
        self._last_next_steps = suggestions
        if [(step.id, step.route, step.context) for step in suggestions] == [(step.id, step.route, step.context) for step in previous]:
            for row, step in zip(self._next_step_rows, suggestions):
                detail = self.tr(step.reason)
                if step.sampled_at is not None:
                    detail += " · " + _format_time(step.sampled_at)
                row.layout().itemAt(0).widget().setText(self.tr(step.title))
                row.layout().itemAt(1).widget().setText(detail)
                row.layout().itemAt(2).widget().setAccessibleDescription(detail)
            return
        for row in self._next_step_rows:
            self.next_steps_card.body.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._next_step_rows = []
        self.next_steps_empty.setText(self.tr("No next steps from the recorded observations."))
        self.next_steps_empty.setVisible(not suggestions)
        for step in suggestions:
            row = QWidget(self.next_steps_card)
            layout = QVBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(self.tr(step.title))
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            detail = self.tr(step.reason)
            if step.sampled_at is not None:
                detail += " · " + _format_time(step.sampled_at)
            reason = QLabel(detail)
            reason.setWordWrap(True)
            reason.setTextFormat(Qt.TextFormat.PlainText)
            reason.setObjectName("cardDescription")
            button = QuietButton(self.tr(step.button), description=detail)
            context = step.context.to_dict() if step.context is not None else {}
            button.clicked.connect(lambda checked=False, destination=step.route, preselection=context: self._request_next_step(destination, preselection))
            layout.addWidget(label)
            layout.addWidget(reason)
            layout.addWidget(button)
            self.next_steps_card.add_widget(row)
            self._next_step_rows.append(row)

    def _request_next_step(self, route: str, context: dict) -> None:
        if context:
            self.contextRouteRequested.emit(route, context)
        else:
            self.routeRequested.emit(route)

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
        visible_details = [group for group in ("network", "disk", "temperature", "battery")
                           if not self._cards[group].isHidden()]
        for index, group in enumerate(visible_details):
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
