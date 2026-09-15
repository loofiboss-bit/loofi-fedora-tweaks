"""Shared Qt adapter for the PyQt-free v29 operation controller.

The controller in :mod:`core.actions.operation_controller` owns policy and
durable state.  This module only provides the Qt thread boundary used by GUI
surfaces: one operation per worker, cooperative cancellation, progress/event
forwarding, and a terminal result signal.  It never constructs commands or
calls a service directly.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal


OperationCallable = Callable[[], Any]


class OperationWorker(QObject):
    """Run one controller operation on a Qt-owned worker thread."""

    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, operation: OperationCallable, *, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._operation = operation
        self._cancel_requested = Event()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested.is_set()

    def cancel(self) -> None:
        """Request cooperative cancellation before/within the operation.

        The controller remains responsible for interrupting a durable run;
        terminating a thread would leave its persisted state ambiguous.
        """
        self._cancel_requested.set()

    def run(self) -> None:
        if self.cancel_requested:
            self.cancelled.emit()
            return
        try:
            result = self._operation()
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            self.failed.emit(str(exc))
            return
        if self.cancel_requested:
            self.cancelled.emit()
            return
        self.finished.emit(result)


class OperationControllerQtAdapter(QObject):
    """Own the QThread lifecycle for one shared-controller operation."""

    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    started = pyqtSignal()

    def __init__(self, *, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: OperationWorker | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self, operation: OperationCallable) -> bool:
        """Start one operation, rejecting overlap until the thread is done."""
        if self.running:
            return False
        thread = QThread(self)
        worker = OperationWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.progress.emit)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        self.started.emit()
        thread.start()
        return True

    def cancel(self) -> bool:
        """Request cancellation without force-killing the worker thread."""
        if self._worker is None or not self.running:
            return False
        self._worker.cancel()
        return True

    def wait(self, timeout_ms: int = 5000) -> bool:
        """Wait for a terminal worker state during controlled shutdown."""
        thread = self._thread
        if thread is None:
            return True
        return bool(thread.wait(max(0, int(timeout_ms))))

    def close(self, timeout_ms: int = 5000) -> bool:
        """Cancel and wait, keeping durable operation state authoritative."""
        if self.running:
            self.cancel()
        return self.wait(timeout_ms)

    def _on_finished(self, result: object) -> None:
        self.finished.emit(result)

    def _on_failed(self, message: str) -> None:
        self.failed.emit(str(message))

    def _on_cancelled(self) -> None:
        self.cancelled.emit()

    def _on_thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        self._worker = None
        if thread is not None:
            thread.deleteLater()


# Explicit names make migration from the former Action Center worker
# mechanical while all new pages can use the neutral adapter name.
QtOperationWorker = OperationWorker
OperationWorkerAdapter = OperationControllerQtAdapter


__all__ = [
    "OperationCallable",
    "OperationControllerQtAdapter",
    "OperationWorker",
    "OperationWorkerAdapter",
    "QtOperationWorker",
]
