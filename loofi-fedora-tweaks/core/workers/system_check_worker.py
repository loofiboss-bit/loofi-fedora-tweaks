"""QThread adapter for an explicitly requested read-only System Check."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import pyqtSignal

from core.system_check.models import CheckProgress, SystemCheckResult
from core.workers.base_worker import BaseWorker

SystemCheckServiceFactory = Callable[[], Any]


class SystemCheckWorker(BaseWorker):
    """Run the canonical service off the UI thread with cooperative cancellation."""

    check_progress = pyqtSignal(object)

    def __init__(
        self,
        *,
        service_factory: SystemCheckServiceFactory | None = None,
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self._service_factory = service_factory
        self._cancel_event = threading.Event()

    def do_work(self) -> SystemCheckResult:
        factory = self._service_factory
        if factory is None:
            from core.system_check.service import SystemCheckService

            factory = SystemCheckService
        service = factory()
        return service.run(
            cancel_event=self._cancel_event,
            progress_callback=self._on_check_progress,
        )

    def cancel(self) -> None:
        self._cancel_event.set()
        super().cancel()

    def _on_check_progress(self, progress: CheckProgress) -> None:
        if self.is_cancelled() and progress.stage != "cancelling":
            return
        self.check_progress.emit(progress)
        self.report_progress(progress.source_id, progress.percentage)
