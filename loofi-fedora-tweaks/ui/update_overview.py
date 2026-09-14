"""Explicit, asynchronous update inspection with source-owned results."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from services.software.update_overview import (
    OverviewCancelled,
    Source,
    UpdateOverviewService,
    UpdateOverviewSnapshot,
)
from ui.components import DetailsDisclosure, FeedbackBanner, PrimaryButton, SecondaryButton


class UpdateCheckWorker(QThread):
    """Keep a bounded read-only check alive if its originating page disappears."""

    completed = pyqtSignal(object)
    sourceCompleted = pyqtSignal(object)
    failed = pyqtSignal(str)
    active: set[UpdateCheckWorker] = set()

    def __init__(self, service: UpdateOverviewService, *, sources: tuple[Source, ...] | None = None) -> None:
        super().__init__(QApplication.instance())
        self.service = service
        self.sources = sources
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    def run(self) -> None:
        try:
            if isinstance(self.service, UpdateOverviewService):
                if self.sources is not None:
                    snapshot = self.service.check(
                        sources=self.sources,
                        on_source_result=self.sourceCompleted.emit,
                    )
                else:
                    snapshot = self.service.check(
                        on_source_result=self.sourceCompleted.emit,
                    )
                self.completed.emit(snapshot)
            else:
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
        self._checking_source: str | None = None
        self._accept_results = True
        self.setObjectName("updateOverview")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        check_row = QHBoxLayout()
        self.check_button = PrimaryButton(self.tr("Check for updates"))
        self.check_button.setAccessibleName(self.tr("Check all update sources"))
        self.check_button.clicked.connect(self.check)
        check_row.addWidget(self.check_button)
        self.cancel_button = SecondaryButton(self.tr("Cancel check"))
        self.cancel_button.setAccessibleName(self.tr("Cancel update check"))
        self.cancel_button.clicked.connect(self.cancel_check)
        self.cancel_button.setEnabled(False)
        check_row.addWidget(self.cancel_button)
        layout.addLayout(check_row)
        self.feedback = FeedbackBanner(self.tr("Saved update status"), self.tr("Check for updates to refresh these results."))
        layout.addWidget(self.feedback)
        self.rows: dict[str, tuple[FeedbackBanner, QLabel, DetailsDisclosure]] = {}
        self.retry_buttons: dict[str, SecondaryButton] = {}
        for source, title in (("system", self.tr("System")), ("flatpak", self.tr("Flatpak")), ("firmware", self.tr("Firmware"))):
            banner = FeedbackBanner(title, self.tr("Not checked"))
            banner.setObjectName("updateSource_" + source)
            checked = QLabel()
            checked.setWordWrap(True)
            details = DetailsDisclosure(summary=self.tr("Show update details: %1").replace("%1", title))
            layout.addWidget(banner)
            layout.addWidget(checked)
            layout.addWidget(details)
            retry = SecondaryButton(self.tr("Retry %1").replace("%1", title))
            retry.setAccessibleName(self.tr("Retry %1 update check").replace("%1", title))
            retry.clicked.connect(lambda _checked=False, source=source: self.check(source))
            retry.setEnabled(False)
            layout.addWidget(retry)
            self.retry_buttons[source] = retry
            self.rows[source] = (banner, checked, details)
        self.set_snapshot(self.service.load())

    @pyqtSlot()
    def check(self, source: Source | None = None) -> None:
        if self._worker is not None:
            return
        reset_cancel = getattr(self.service, "reset_cancel", None)
        if callable(reset_cancel):
            reset_cancel()
        self._accept_results = True
        self._checking_source = source
        self.check_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        for retry in self.retry_buttons.values():
            retry.setEnabled(False)
        self.feedback.set_result("info", self.tr("Checking for updates"), self.tr("Reading System, Flatpak and Firmware. Existing results remain visible until the check finishes."))
        worker = UpdateCheckWorker(
            self.service,
            sources=(source,) if source is not None else None,
        )
        worker.sourceCompleted.connect(self._partial_completed)
        worker.completed.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        self._worker = worker
        worker.start_check()

    @pyqtSlot()
    def cancel_check(self) -> None:
        if self._worker is None:
            return
        self.service.cancel()
        self.feedback.set_result(
            "warning",
            self.tr("Check cancelled"),
            self.tr("Completed source results remain visible. Check again to refresh the remaining sources."),
        )

    @pyqtSlot(object)
    def _partial_completed(self, snapshot: object) -> None:
        if self._accept_results and isinstance(snapshot, UpdateOverviewSnapshot):
            self.set_snapshot(snapshot)

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
        self._checking_source = None
        self.check_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        for retry in self.retry_buttons.values():
            retry.setEnabled(True)

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
            "bootc_manual_guidance": (self.tr("Manual guidance required for bootc"), "warning"),
            "backend_unknown": (self.tr("Deployment backend is unknown"), "warning"),
            "fedora_release_unknown": (self.tr("Fedora release is outside the verified policy"), "warning"),
            "error": (self.tr("Could not check for updates"), "warning"),
        }
        for result in snapshot.sources:
            if result.source not in self.rows:
                continue
            banner, checked, details = self.rows[result.source]
            text, kind = states.get(result.status, states["error"])
            if result.error_code in states:
                text, kind = states[result.error_code]
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
            self.retry_buttons[result.source].setEnabled(self._worker is None)
        warning = snapshot.storage_status != "ok" or any(item.status == "error" for item in snapshot.sources)
        self.feedback.set_result(
            "warning" if warning else "info",
            self.tr("Some results need attention") if warning else self.tr("Update overview"),
            self.tr("Results could not be saved. Existing saved data was preserved; run a new check when storage is available.") if snapshot.storage_status != "ok" else self.tr("Choose an update source below. Action Center prepares, runs, and verifies it here."),
        )
        self.snapshotChanged.emit(snapshot)
