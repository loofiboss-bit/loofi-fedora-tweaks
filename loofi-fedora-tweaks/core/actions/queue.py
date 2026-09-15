"""Read-only compatibility view for the retired Action Center queue.

v29 operations are coordinated by :class:`OperationController` and the
digest-bound :class:`ActionCenterOrchestrator`.  The old queue remains as a
small state reader so older integrations can still render persisted items,
but it deliberately has no execution path.
"""

from __future__ import annotations

from collections import deque

from core.actions.model import ActionCenterItem


class ActionQueue:
    """Passive FIFO compatibility container.

    ``enqueue`` remains useful to old readers that assemble a list of
    recommendations.  ``next_ready`` and ``finish_current`` are retained as
    compatibility methods but never authorize, start, or complete a host
    mutation.  New callers must use ``OperationController``.
    """

    def __init__(self):
        self._items: deque[ActionCenterItem] = deque()
        # Kept only so old serialized views continue to have a stable shape;
        # v29 never places an item in this slot.
        self._running: ActionCenterItem | None = None
        self.execution_disabled = True

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

    def peek_ready(self) -> ActionCenterItem | None:
        """Return the first ready compatibility item without claiming it."""
        if self._running is not None:
            return None
        return next((item for item in self._items if item.state == "ready"), None)

    def next_ready(self) -> ActionCenterItem | None:
        """Return no item: queue selection is no longer an execution authority.

        The method intentionally does not transition an item to ``running``.
        This prevents a stale caller from obtaining a queue item and treating
        that as permission to execute it.
        """
        return None

    def finish_current(self, state: str, output_summary: str = "") -> ActionCenterItem | None:
        """No-op compatibility method; queue items are never running in v29."""
        return None

    def pending(self) -> list[ActionCenterItem]:
        """Return a snapshot of queued legacy items for read-only surfaces."""
        return list(self._items)

    def to_dict(self) -> dict[str, object]:
        return {
            "running": self._running.to_dict() if self._running else None,
            "queued": [item.to_dict() for item in self._items],
            "execution_disabled": True,
            "replacement": "OperationController",
        }
