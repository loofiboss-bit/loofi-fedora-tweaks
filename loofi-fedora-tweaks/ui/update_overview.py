"""Explicit, asynchronous update inspection with source-owned results."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from services.software.update_overview import OverviewCancelled, UpdateOverviewService, UpdateOverviewSnapshot
from ui.components import DetailsDisclosure, FeedbackBanner, PrimaryButton


class UpdateCheckWorker(QThread):
    """Keep a bounded read-only check alive if its originating page disappears."""

    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    active: set[UpdateCheckWorker] = set()

    def __init__(self, service: UpdateOverviewService) -> None:
        super().__init__(QApplication.instance())
        self.service = service
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    def run(self) -> None:
        try:
            self.completed.emit(self.service.check())
        except OverviewCancelled:
            pass
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            self.failed.emit(type(exc).__name__)

    @pyqtSlot()
    def shutdown(self) -> None:
        """Reap the query before QApplication destroys its child threads."""
        self.service.cancel()
        if not self.wait(8000):
            # Keep ownership outside QApplication if an injected runtime fails
            # to cooperate. Never destroy or forcibly terminate a running thread.
            self.setParent(None)

    def start_check(self) -> None:
        self.active.add(self)
        self.finished.connect(self._release)
        self.start()

    @pyqtSlot()
    def _release(self) -> None:
        self.active.discard(self)
        self.deleteLater()


class UpdateOverviewWidget(QWidget):
    """Inspection never creates a plan or starts an update."""

    snapshotChanged = pyqtSignal(object)

    def __init__(self, service: UpdateOverviewService | None = None) -> None:
        super().__init__()
        self.service = service or UpdateOverviewService()
        self.snapshot = UpdateOverviewSnapshot()
        self._worker: UpdateCheckWorker | None = None
        self._accept_results = True
        self.setObjectName("updateOverview")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.check_button = PrimaryButton(self.tr("Check for updates"))
        self.check_button.setAccessibleName(self.tr("Check all update sources"))
        self.check_button.clicked.connect(self.check)
        layout.addWidget(self.check_button)
        self.feedback = FeedbackBanner(self.tr("Saved update status"), self.tr("Check for updates to refresh these results."))
        layout.addWidget(self.feedback)
        self.rows: dict[str, tuple[FeedbackBanner, QLabel, DetailsDisclosure]] = {}
        for source, title in (("system", self.tr("System")), ("flatpak", self.tr("Flatpak")), ("firmware", self.tr("Firmware"))):
            banner = FeedbackBanner(title, self.tr("Not checked"))
            banner.setObjectName("updateSource_" + source)
            checked = QLabel()
            checked.setWordWrap(True)
            details = DetailsDisclosure(summary=self.tr("Show update details: %1").replace("%1", title))
            layout.addWidget(banner)
            layout.addWidget(checked)
            layout.addWidget(details)
            self.rows[source] = (banner, checked, details)
        self.set_snapshot(self.service.load())

    @pyqtSlot()
    def check(self) -> None:
        if self._worker is not None:
            return
        self._accept_results = True
        self.check_button.setEnabled(False)
        self.feedback.set_result("info", self.tr("Checking for updates"), self.tr("Reading System, Flatpak and Firmware. Existing results remain visible until the check finishes."))
        worker = UpdateCheckWorker(self.service)
        worker.completed.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        self._worker = worker
        worker.start_check()

    @pyqtSlot(object)
    def _completed(self, snapshot: object) -> None:
        if self._accept_results and isinstance(snapshot, UpdateOverviewSnapshot):
            self.set_snapshot(snapshot)

    @pyqtSlot(str)
    def _failed(self, _error: str) -> None:
        if self._accept_results:
            self.feedback.set_result("warning", self.tr("Could not finish the check"), self.tr("Saved results may be out of date. Check again when the source is available."))

    @pyqtSlot()
    def _finished(self) -> None:
        self._worker = None
        self.check_button.setEnabled(True)

    def hideEvent(self, event) -> None:
        self._accept_results = False
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        self._accept_results = True
        if self._worker is None:
            self.set_snapshot(self.service.load())
        super().showEvent(event)

    def set_snapshot(self, snapshot: UpdateOverviewSnapshot) -> None:
        self.snapshot = snapshot
        states = {
            "unchecked": (self.tr("Not checked"), "info"),
            "up_to_date": (self.tr("No updates available"), "success"),
            "available": (self.tr("Updates available"), "info"),
            "missing_tool": (self.tr("Required tool is not installed"), "warning"),
            "unsupported": (self.tr("Not supported on this system"), "warning"),
            "error": (self.tr("Could not check for updates"), "warning"),
        }
        for result in snapshot.sources:
            if result.source not in self.rows:
                continue
            banner, checked, details = self.rows[result.source]
            text, kind = states.get(result.status, states["error"])
            if result.stale and result.checked_at:
                text = self.tr("Out of date: %1").replace("%1", text)
                kind = "warning"
            banner.set_result(kind, {"system": self.tr("System"), "flatpak": self.tr("Flatpak"), "firmware": self.tr("Firmware")}[result.source], text)
            banner.setProperty("sourceStatus", result.status)
            banner.setProperty("sourceStale", result.stale)
            checked.setText(self.tr("Last checked: %1 · Updates: %2").replace("%1", result.checked_at or self.tr("Never")).replace("%2", str(len(result.items)) if result.status in {"available", "up_to_date"} else self.tr("Unknown")))
            restart = self.tr("Required") if result.reboot_required is True else self.tr("Not required") if result.reboot_required is False else self.tr("Determined when the plan is reviewed")
            lines = [self.tr("Restart: %1").replace("%1", restart)]
            for item in result.items:
                versions = " → ".join(value for value in (item.old_version, item.version) if value)
                lines.append(f"{item.name}  {versions}".strip())
            if result.error_code:
                lines.append(self.tr("Check detail: %1").replace("%1", result.error_code))
            details.set_details("\n".join(lines))
        warning = snapshot.storage_status != "ok" or any(item.status == "error" for item in snapshot.sources)
        self.feedback.set_result(
            "warning" if warning else "info",
            self.tr("Some results need attention") if warning else self.tr("Update overview"),
            self.tr("Results could not be saved. Existing saved data was preserved.") if snapshot.storage_status != "ok" else self.tr("Review one source below. Action Center checks its current state before running the plan."),
        )
        self.snapshotChanged.emit(snapshot)
