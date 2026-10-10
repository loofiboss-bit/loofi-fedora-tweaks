"""Manual restart advice using the existing cancellable operation adapter."""
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLabel, QWidget

from services.software.restart_advice import RestartAdvice, RestartAdviceService
from ui.components import Card, PrimaryButton, SecondaryButton
from ui.operation_worker import OperationControllerQtAdapter


class RestartAdviceCard(Card):
    """Display a session-only observation without checking or restarting automatically."""

    stopped = pyqtSignal()

    def __init__(self, *, service: RestartAdviceService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(self.tr("Restart advice"), self.tr("Read Fedora's local restart recommendation after updates."), parent=parent)
        self.setObjectName("restartAdviceCard")
        self.service = service or RestartAdviceService()
        self._accept_results = True
        self.check_button = PrimaryButton(self.tr("Check restart advice"))
        self.check_button.clicked.connect(self.check)
        self.add_widget(self.check_button)
        self.cancel_button = SecondaryButton(self.tr("Cancel check"))
        self.cancel_button.clicked.connect(self.request_stop)
        self.cancel_button.setEnabled(False)
        self.add_widget(self.cancel_button)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.add_widget(self.details)
        self._adapter = OperationControllerQtAdapter(parent=self)
        self._adapter.finished.connect(self._completed)
        self._adapter.failed.connect(self._failed)
        self._adapter.stopped.connect(self._stopped)
        self._freshness_timer = QTimer(self)
        self._freshness_timer.setInterval(60000)
        self._freshness_timer.timeout.connect(self.refresh_display)
        self._freshness_timer.start()
        self.refresh_display()

    @property
    def busy(self) -> bool:
        return self._adapter.busy

    def refresh_display(self) -> None:
        if not self.busy:
            self._render(self.service.load())

    def check(self) -> None:
        if self.busy:
            return
        self.service.reset_cancel()
        self._accept_results = True
        self.check_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.details.setText(self.tr("Reading local restart advice. The system will not restart."))
        self._adapter.start(self.service.check)

    def request_stop(self) -> None:
        self._accept_results = False
        self.service.cancel()
        self._adapter.cancel()
        if self.busy:
            self.details.setText(self.tr("Check cancelled. Previous restart advice remains available."))

    def cleanup(self, timeout_ms: int = 1000) -> bool:
        self._freshness_timer.stop()
        self.request_stop()
        return self._adapter.close(timeout_ms)

    def _stopped(self) -> None:
        self.check_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.stopped.emit()

    def _failed(self, _message: str) -> None:
        if self._accept_results:
            self.details.setText(self.tr("Restart advice unknown. The check failed; check again when the tool is available."))

    def _completed(self, advice: RestartAdvice) -> None:
        if self._accept_results:
            self._render(advice)

    def _render(self, advice: RestartAdvice) -> None:
        labels = {"required": self.tr("Restart recommended"), "not_required": self.tr("No restart recommended"),
                  "unknown": self.tr("Restart advice unknown")}
        title = labels[advice.state]
        if advice.stale and advice.checked_at:
            title = self.tr("Out of date: %1").replace("%1", title)
        lines = [title, self.tr("Last checked: %1").replace("%1", advice.checked_at or self.tr("Never"))]
        if advice.packages:
            lines.append(self.tr("Packages updated since boot: %1").replace("%1", ", ".join(advice.packages)))
        if advice.reason == "unsupported_backend":
            lines.append(self.tr("This check requires traditional Fedora with DNF5. Follow your edition's restart guidance."))
        elif advice.state == "unknown" and advice.checked_at:
            lines.append(self.tr("Check detail: %1").replace("%1", advice.reason))
        lines.append(self.tr("Local advice only. Loofi never restarts automatically."))
        self.setProperty("restartState", advice.state)
        self.setProperty("restartStale", advice.stale)
        self.details.setText("\n".join(lines))

    def showEvent(self, event) -> None:
        self.refresh_display()
        super().showEvent(event)
