"""services.desktop — Desktop environment services.

Re-exports from submodules for convenient top-level access:
    from services.desktop import DesktopUtils, KWinManager, TilingManager, ...
"""

from services.desktop.desktop import DesktopUtils
from services.desktop.display import DisplayInfo, WaylandDisplayManager
from services.desktop.kde44 import KDE44DesktopInfo, KDE44DesktopService
from services.desktop.kwin import KWinManager
from services.desktop.kwin import Result as KWinResult
from services.desktop.native_handoff import (
    NativeHandoffAvailability,
    NativeHandoffLaunch,
    NativeHandoffService,
    NativeHandoffTarget,
)
from services.desktop.tiling import DotfileManager, TilingManager
from services.desktop.tiling import Result as TilingResult

__all__ = [
    "DesktopUtils",
    "DisplayInfo",
    "DotfileManager",
    "KWinManager",
    "KWinResult",
    "KDE44DesktopInfo",
    "KDE44DesktopService",
    "NativeHandoffAvailability",
    "NativeHandoffLaunch",
    "NativeHandoffService",
    "NativeHandoffTarget",
    "TilingManager",
    "TilingResult",
    "WaylandDisplayManager",
]
