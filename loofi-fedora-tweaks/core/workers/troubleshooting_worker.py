"""QThread adapter for one explicitly started Compass session."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import pyqtSignal

from core.troubleshooting.lifecycle import CancellationSignal
from core.workers.base_worker import BaseWorker

TroubleshootingServiceFactory = Callable[[], Any]


class TroubleshootingWorker(BaseWorker):
    """Run the PyQt-free troubleshooting service off the UI thread."""

    source_progress = pyqtSignal(object)

    def __init__(
        self,
        profile_id: str,
        *,
        parameters: dict[str, Any] | None = None,
        service_factory: TroubleshootingServiceFactory | None = None,
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.profile_id = profile_id
        self.parameters = dict(parameters or {})
        self._service_factory = service_factory
        self._cancellation = CancellationSignal()

    def do_work(self) -> Any:
        factory = self._service_factory
        if factory is None:
            from core.troubleshooting.service import TroubleshootingService

            factory = TroubleshootingService
        return factory().run(
            self.profile_id,
            parameters=self.parameters,
            cancellation=self._cancellation,
            progress_callback=self.source_progress.emit,
        )

    def cancel(self) -> None:
        """Request cooperative cancellation while retaining the terminal result."""
        self._cancellation.cancel()
