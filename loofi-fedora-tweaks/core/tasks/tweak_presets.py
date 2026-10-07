"""Curated, reviewable desktop presets built from supported tweak values."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from core.tasks.tweak_profiles import TweakProfile
from core.tasks.tweaks import _profile_desktop


@dataclass(frozen=True)
class TweakPreset:
    id: str
    name: str
    description: str
    settings: Mapping[str, Mapping[str, str]]

    def __post_init__(self) -> None:
        frozen = {
            desktop: MappingProxyType(dict(values))
            for desktop, values in self.settings.items()
        }
        object.__setattr__(self, "settings", MappingProxyType(frozen))

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "desktops": sorted(self.settings),
        }


PRESETS: tuple[TweakPreset, ...] = (
    TweakPreset(
        "reduced-motion",
        "Reduced motion",
        "Reduce desktop animation and motion effects.",
        {
            "gnome": {"gnome-animations": "false"},
            "kde": {"kde-animation": "0", "kde-wobbly-windows": "false"},
        },
    ),
    TweakPreset(
        "file-navigation",
        "File navigation",
        "Use double-click opening, a list view, and an editable location field where supported.",
        {
            "gnome": {
                "gnome-files-click-policy": "double",
                "gnome-files-default-folder-view": "list-view",
                "gnome-files-editable-location": "true",
            },
            "kde": {
                "kde-single-click": "false",
                "kde-dolphin-editable-location": "true",
                "kde-dolphin-show-full-path": "true",
            },
        },
    ),
)
BY_PRESET_ID = {preset.id: preset for preset in PRESETS}


def list_presets() -> tuple[TweakPreset, ...]:
    """Return stable public preset metadata without inspecting the host."""
    return PRESETS


def profile_for_preset(preset_id: str, platform: object) -> TweakProfile:
    """Build the ordinary profile contract for the detected desktop preset."""
    preset = BY_PRESET_ID.get(str(preset_id).strip())
    if preset is None:
        raise ValueError(f"Unknown tweak preset: {preset_id}")
    desktop = _profile_desktop(platform)
    settings = preset.settings.get(desktop)
    if settings is None:
        raise ValueError("This preset is unavailable on the detected desktop.")
    return TweakProfile(preset.name, desktop, tuple(settings.items()))


__all__ = ["BY_PRESET_ID", "PRESETS", "TweakPreset", "list_presets", "profile_for_preset"]
