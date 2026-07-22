from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PluginMetadata:
    id: str                          # unique slug, e.g. "hardware"
    name: str                        # display name
    description: str                 # tooltip and breadcrumb text
    category: str                    # sidebar category group, e.g. "System"
    icon: str                        # semantic icon id (or legacy icon ref string)
    badge: str                       # "recommended" | "advanced" | ""
    version: str = "1.0.0"          # plugin version string
    min_app_version: str = ""       # minimum app version required (empty = no limit)
    max_app_version: str = ""       # maximum app version supported (empty = no limit)
    requires: tuple[str, ...] = ()   # dependency plugin IDs (tuple for hashability)
    compat: dict[str, Any] = field(  # {min_fedora: 38, de: ["gnome","kde"], ...}
        default_factory=dict
    )
    order: int = 100                 # sort order within category (lower = higher in list)
    enabled: bool = True             # default enabled state


@dataclass
class CompatStatus:
    compatible: bool
    reason: str = ""                 # human-readable reason if not compatible
    warnings: list[str] = field(default_factory=list)
