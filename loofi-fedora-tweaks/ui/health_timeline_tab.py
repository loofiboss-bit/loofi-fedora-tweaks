"""Compatibility import for the canonical System Check page."""

from __future__ import annotations

from ui.system_check_tab import SystemCheckTab


class HealthTimelineTab(SystemCheckTab):
    """Legacy class name backed by the canonical read-only System Check page."""
