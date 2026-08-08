"""Background adapter for Action Center probes and persistence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal


class ActionCenterOperationWorker(QObject):
    """Run one non-GUI Action Center operation away from the GUI thread."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self._operation = operation

    def run(self) -> None:
        try:
            self.finished.emit(self._operation())
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            self.failed.emit(str(exc))


__all__ = ["ActionCenterOperationWorker"]
