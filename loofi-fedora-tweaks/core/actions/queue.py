"""Sequential Action Center queue."""

from __future__ import annotations

from collections import deque

from core.actions.model import ActionCenterItem


class ActionQueue:
    """Small FIFO queue that prevents fix-all style parallel execution."""

    def __init__(self):
        self._items: deque[ActionCenterItem] = deque()
        self._running: ActionCenterItem | None = None

    def enqueue(self, item: ActionCenterItem) -> ActionCenterItem:
        if item.manual_only:
            item.state = "manual_only"
        elif item.risk_level in {"medium", "high"} and not item.confirmation_required:
            item.state = "needs_review"
        elif not item.executable:
            item.state = "blocked"
        else:
            item.state = "ready"
        self._items.append(item)
        return item

    def next_ready(self) -> ActionCenterItem | None:
        if self._running is not None:
            return None
        while self._items:
            item = self._items.popleft()
            if item.state == "ready":
                self._running = item
                item.state = "running"
                return item
        return None

    def finish_current(self, state: str, output_summary: str = "") -> ActionCenterItem | None:
        item = self._running
        if item is None:
            return None
        item.state = state  # type: ignore[assignment]
        item.output_summary = output_summary
        self._running = None
        return item

    def to_dict(self) -> dict[str, object]:
        return {
            "running": self._running.to_dict() if self._running else None,
            "queued": [item.to_dict() for item in self._items],
        }
