"""Preset management for saving and applying system configuration snapshots."""
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from core.local_profiles import (
    PROFILE_KEYS as LOCAL_PROFILE_KEYS,
    PROFILE_SCHEMA_VERSION as LOCAL_PROFILE_SCHEMA_VERSION,
    validate_local_profile,
)
from core.state.atomic_io import atomic_write_json, durable_unlink
from services.system.system import cached_which

logger = logging.getLogger(__name__)


class PresetManager:
    PRESETS_DIR = os.path.expanduser("~/.config/loofi-fedora-tweaks/presets")
    PROFILE_SCHEMA_VERSION = LOCAL_PROFILE_SCHEMA_VERSION
    MAX_IMPORT_BYTES = 1024 * 1024
    PROFILE_KEYS = LOCAL_PROFILE_KEYS

    def __init__(self):
        os.makedirs(self.PRESETS_DIR, exist_ok=True)

    def list_presets(self):
        """Returns a list of preset names."""
        if not os.path.exists(self.PRESETS_DIR):
            return []
        files = [f for f in os.listdir(self.PRESETS_DIR) if f.endswith(".json")]
        return [os.path.splitext(f)[0] for f in files]

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitize preset name to prevent path traversal."""
        # Strip directory separators and dangerous characters
        safe = os.path.basename(name)
        safe = safe.replace("..", "").replace("/", "").replace("\\", "")
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", safe).strip(".-_")
        if not safe:
            safe = "unnamed_preset"
        return safe

    def save_preset(self, name):
        """Captures current system state and saves as JSON."""
        data = {
            "schema_version": self.PROFILE_SCHEMA_VERSION,
            "name": name,
            "theme": self._get_gsettings("org.gnome.desktop.interface", "gtk-theme"),
            "icon_theme": self._get_gsettings(
                "org.gnome.desktop.interface", "icon-theme"
            ),
            "cursor_theme": self._get_gsettings(
                "org.gnome.desktop.interface", "cursor-theme"
            ),
            "color_scheme": self._get_gsettings(
                "org.gnome.desktop.interface", "color-scheme"
            ),
            "battery_limit": self._get_battery_limit(),
            "power_profile": self._get_power_profile(),
        }

        safe_name = self._sanitize_name(name)
        path = Path(self.PRESETS_DIR) / f"{safe_name}.json"
        atomic_write_json(path, data, mode=0o600)
        return True

    def load_preset(self, name):
        """Loads a preset and applies settings."""
        safe_name = self._sanitize_name(name)
        path = os.path.join(self.PRESETS_DIR, f"{safe_name}.json")
        if not os.path.exists(path):
            return False

        with open(path, "r") as f:
            data = json.load(f)

        try:
            return self._validated_profile(data)
        except ValueError as exc:
            logger.debug("Rejected local profile %s: %s", safe_name, exc)
            return False

    def delete_preset(self, name):
        safe_name = self._sanitize_name(name)
        path = os.path.join(self.PRESETS_DIR, f"{safe_name}.json")
        if os.path.exists(path):
            durable_unlink(Path(path))
            return True
        return False

    def save_preset_data(self, name, data):
        """Save validated data supplied by an explicit local-file import."""
        safe_name = self._sanitize_name(name)
        path = Path(self.PRESETS_DIR) / f"{safe_name}.json"
        try:
            validated = self._validated_profile({"name": name, **dict(data)})
            atomic_write_json(path, validated, mode=0o600)
            return True
        except (OSError, TypeError, ValueError) as e:
            logger.debug("Failed to save preset data: %s", e)
            return False

    @classmethod
    def _validated_profile(cls, payload: Any) -> dict[str, Any]:
        """Validate one closed, data-only local profile schema."""
        return validate_local_profile(payload)

    def import_preset(self, source: str | Path) -> tuple[bool, str]:
        """Import one explicit regular JSON file after path and schema validation."""
        path = Path(source)
        if path.suffix.casefold() != ".json" or path.is_symlink() or not path.is_file():
            return False, "Select a regular local JSON profile file."
        try:
            if path.stat().st_size > self.MAX_IMPORT_BYTES:
                return False, "Profile exceeds the 1 MiB import limit."
            payload = json.loads(path.read_text(encoding="utf-8"))
            validated = self._validated_profile(payload)
        except (OSError, json.JSONDecodeError, UnicodeError, ValueError) as exc:
            return False, f"Profile validation failed: {exc}"
        name = self._sanitize_name(str(validated["name"]) or path.stem)
        destination = Path(self.PRESETS_DIR) / f"{name}.json"
        try:
            atomic_write_json(destination, validated, mode=0o600)
        except OSError as exc:
            return False, f"Profile import failed: {exc}"
        return True, name

    def create_review_plan(self, name: str):
        """Convert a validated local profile to a non-executable Action Center plan."""
        data = self.load_preset(name)
        if not isinstance(data, dict):
            raise ValueError(f"Local profile '{name}' is missing or invalid.")
        from core.actions.orchestrator import ActionCenterOrchestrator
        from core.fedora_release_policy import FEDORA_RELEASE_POLICY

        return ActionCenterOrchestrator().plan(
            "local-profile-review",
            {"profile": self._sanitize_name(name), "settings": data},
            target=FEDORA_RELEASE_POLICY.stable_target,
        )

    def export_preset(self, name: str, destination: str | Path) -> bool:
        """Atomically export a validated profile with private file permissions."""
        data = self.load_preset(name)
        if not isinstance(data, dict):
            return False
        path = Path(destination)
        if path.suffix.casefold() != ".json" or path.is_symlink():
            return False
        try:
            atomic_write_json(path, data, mode=0o600)
            return True
        except OSError as exc:
            logger.debug("Failed to export local profile: %s", exc)
            return False

    # --- Helpers ---
    def _get_gsettings(self, schema, key):
        if not cached_which("gsettings"):
            return None
        try:
            return (
                subprocess.check_output(
                    ["gsettings", "get", schema, key], text=True, timeout=15
                )
                .strip()
                .strip("'")
            )
        except subprocess.CalledProcessError:
            return None

    def _get_battery_limit(self):
        # Read from config file primarily
        try:
            with open("/etc/loofi-fedora-tweaks/battery.conf", "r") as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 100

    def _get_power_profile(self):
        if not cached_which("powerprofilesctl"):
            return "balanced"
        try:
            return subprocess.check_output(
                ["powerprofilesctl", "get"], text=True, timeout=60
            ).strip()
        except subprocess.CalledProcessError:
            return "balanced"
