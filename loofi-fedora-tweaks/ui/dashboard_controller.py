"""One asynchronous, visibility-aware sampler shared by hardware views."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget


class _SampleWorker(QThread):
    completed = pyqtSignal(object, int)
    failed = pyqtSignal(str, int)

    def __init__(self, service, fast: bool, slow: bool, reset: bool, generation: int, parent=None):
        super().__init__(parent)
        self.service = service
        self.fast, self.slow, self.reset = fast, slow, reset
        self.generation = generation

    def run(self):
        try:
            if self.reset:
                self.service.reset_baselines()
            snapshot = self.service.collect(fast=self.fast, slow=self.slow)
            self.completed.emit(snapshot, self.generation)
        except (OSError, RuntimeError, ValueError, TypeError, KeyError, AttributeError) as exc:
            self.failed.emit(str(exc), self.generation)


class DashboardController(QObject):
    """Own the only pending sample; widgets never read the system themselves."""
    snapshotReady = pyqtSignal(object)
    failed = pyqtSignal(str)
    stopped = pyqtSignal()

    def __init__(self, parent=None, service=None):
        super().__init__(parent)
        if service is None:
            from services.system.dashboard import DashboardService
            service = DashboardService()
        self.service = service
        self.latest_snapshot = None
        self._consumers: set[str] = set()
        self._suspended = False
        self._closed = False
        self._stop_notified = False
        self._generation = 0
        self._reset = True
        self._worker = None
        self._pending_fast = False
        self._pending_slow = False
        self.fast_timer = QTimer(self)
        self.fast_timer.setInterval(2000)
        self.fast_timer.timeout.connect(lambda: self._request(True, False))
        self.slow_timer = QTimer(self)
        self.slow_timer.setInterval(5000)
        self.slow_timer.timeout.connect(lambda: self._request(False, True))
        if isinstance(parent, QWidget):
            parent.installEventFilter(self)

    @property
    def busy(self) -> bool:
        return self._worker is not None

    @property
    def active(self):
        return bool(self._consumers) and not self._suspended and not self._closed

    def set_consumer_active(self, consumer: str, active: bool):
        was_active = self.active
        if active:
            self._consumers.add(consumer)
        else:
            self._consumers.discard(consumer)
        self._update_activity(was_active)

    def set_suspended(self, suspended: bool):
        was_active = self.active
        self._suspended = suspended
        self._update_activity(was_active)

    def _update_activity(self, was_active):
        if self.active == was_active:
            return
        self._generation += 1
        self._reset = True
        self._pending_fast = self._pending_slow = False
        if self.active:
            self.fast_timer.start()
            self.slow_timer.start()
            self.refresh()
        else:
            self.fast_timer.stop()
            self.slow_timer.stop()

    def eventFilter(self, watched, event):
        if isinstance(watched, QWidget) and event.type() == QEvent.Type.Hide:
            self.set_suspended(True)
        elif isinstance(watched, QWidget) and event.type() in (QEvent.Type.WindowStateChange, QEvent.Type.Show):
            self.set_suspended(watched.isMinimized())
        return super().eventFilter(watched, event)

    def refresh(self):
        self._request(True, True)

    def _request(self, fast: bool, slow: bool):
        if not self.active:
            return
        if self._worker is not None:
            self._pending_fast |= fast
            self._pending_slow |= slow
            return
        worker = _SampleWorker(self.service, fast, slow, self._reset, self._generation, self)
        self._reset = False
        self._worker = worker
        worker.completed.connect(self._received)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.start()

    def _received(self, snapshot, generation):
        if self.active and generation == self._generation:
            self.latest_snapshot = snapshot
            self.snapshotReady.emit(snapshot)

    def _failed(self, message, generation):
        if self.active and generation == self._generation:
            self.failed.emit(message)

    def _finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        fast, slow = self._pending_fast, self._pending_slow
        self._pending_fast = self._pending_slow = False
        if fast or slow:
            self._request(fast, slow)
        self._notify_stopped()

    def request_stop(self) -> None:
        """Invalidate results and stop scheduling without blocking the GUI."""
        if not self._closed:
            self._closed = True
            self._generation += 1
        self.fast_timer.stop()
        self.slow_timer.stop()
        self._pending_fast = self._pending_slow = False
        if self._worker is not None:
            self._worker.requestInterruption()
        else:
            QTimer.singleShot(0, self._notify_stopped)

    def _notify_stopped(self) -> None:
        if self._closed and not self.busy and not self._stop_notified:
            self._stop_notified = True
            self.stopped.emit()

    def wait_for_stop(self, timeout_ms: int) -> bool:
        """Wait at most the supplied budget; retain live readers on timeout."""
        worker = self._worker
        return worker is None or worker.wait(max(0, int(timeout_ms)))

    def cleanup(self, timeout_ms: int = 5000) -> bool:
        self.request_stop()
        return self.wait_for_stop(timeout_ms)
