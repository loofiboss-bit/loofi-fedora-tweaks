"""Compatibility import for the shared v29 Qt operation adapter."""

from __future__ import annotations

from ui.operation_worker import OperationWorker


class ActionCenterOperationWorker(OperationWorker):
    """Legacy name retained while all GUI work uses the neutral adapter."""


__all__ = ["ActionCenterOperationWorker"]
