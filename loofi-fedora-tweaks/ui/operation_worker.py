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
from typing import Any, cast

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal


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
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        # Cancellation cannot interrupt an operation that has crossed the
        # execution boundary. Its durable result takes precedence over a late
        # shutdown request so a completed host change is never hidden.
        self.finished.emit(result)


class OperationControllerQtAdapter(QObject):
    """Own the QThread lifecycle for one shared-controller operation."""

    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    started = pyqtSignal()
    stopped = pyqtSignal()

    def __init__(self, *, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: OperationWorker | None = None
        self._terminal: tuple[str, object] | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @property
    def busy(self) -> bool:
        """Return true until the GUI thread has delivered the terminal result."""
        return self._thread is not None

    def start(self, operation: OperationCallable) -> bool:
        """Start one operation, rejecting overlap until the thread is done."""
        if self._thread is not None:
            return False
        thread = QThread(self)
        worker = OperationWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.progress.emit)
        cast(Any, worker.finished).connect(self._record_finished, Qt.ConnectionType.DirectConnection)
        cast(Any, worker.failed).connect(self._record_failed, Qt.ConnectionType.DirectConnection)
        cast(Any, worker.cancelled).connect(self._record_cancelled, Qt.ConnectionType.DirectConnection)
        # Quit from the worker's emitting thread. A queued connection targets
        # the QThread object's GUI-thread affinity and can deadlock wait() or
        # shutdown while that GUI thread is waiting for this worker.
        cast(Any, worker.finished).connect(thread.quit, Qt.ConnectionType.DirectConnection)
        cast(Any, worker.failed).connect(thread.quit, Qt.ConnectionType.DirectConnection)
        cast(Any, worker.cancelled).connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(worker.deleteLater)
        cast(Any, thread.finished).connect(self._on_thread_finished, Qt.ConnectionType.QueuedConnection)
        self._thread = thread
        self._worker = worker
        self._terminal = None
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

    def _record_finished(self, result: object) -> None:
        self._terminal = ("finished", result)

    def _record_failed(self, message: str) -> None:
        self._terminal = ("failed", str(message))

    def _record_cancelled(self) -> None:
        self._terminal = ("cancelled", None)

    def _on_thread_finished(self) -> None:
        thread = self._thread
        if thread is None:
            return
        terminal = self._terminal
        self._terminal = None
        self._worker = None
        self._thread = None
        thread.deleteLater()
        if terminal is not None:
            kind, payload = terminal
            if kind == "finished":
                self.finished.emit(payload)
            elif kind == "failed":
                self.failed.emit(str(payload))
            else:
                self.cancelled.emit()
        self.stopped.emit()


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
