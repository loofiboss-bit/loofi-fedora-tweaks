"""
Worker base classes for v23.0 Architecture Hardening.

Provides standardized QThread worker pattern for background tasks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # Backward compatibility: worker base classes are exported from this package.
    from core.workers.base_worker import BaseWorker
    from core.workers.command_worker import CommandWorker


def __getattr__(name: str):
    """Lazily resolve worker exports without importing PyQt6 on module import."""
    if name == "BaseWorker":
        from core.workers.base_worker import BaseWorker

        return BaseWorker
    if name == "CommandWorker":
        from core.workers.command_worker import CommandWorker

        return CommandWorker
    raise AttributeError(name)


__all__ = ["BaseWorker", "CommandWorker"]
