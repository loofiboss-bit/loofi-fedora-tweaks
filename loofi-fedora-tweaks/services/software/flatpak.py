"""
Flatpak Manager — size visualization, permission audit, and cleanup.

Provides Flatpak app size analysis, per-app permission auditing,
orphan runtime detection, and cleanup operations.

Migrated from utils/flatpak_manager.py in v2.0.0 "Evolution".
"""

import logging
import subprocess
from dataclasses import dataclass
from typing import List

from services.system.system import cached_which
from utils.commands import CommandTuple

logger = logging.getLogger(__name__)


@dataclass
class FlatpakSizeEntry:
    """Represents a Flatpak app with its disk usage."""

    name: str
    app_id: str
    size_bytes: int = 0
    size_str: str = ""
    runtime: str = ""
    ref: str = ""


@dataclass
class FlatpakPermission:
    """Represents a single permission granted to a Flatpak app."""

    category: str
    key: str
    value: str


@dataclass
class FlatpakAppPermissions:
    """All permissions for a single Flatpak app."""

    app_id: str
    name: str
    permissions: List[FlatpakPermission]
    ref: str = ""
    installation: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "loofi.flatpak-permissions/v1",
            "status": "unavailable" if self.error else "ready",
            "app_id": self.app_id,
            "name": self.name,
            "ref": self.ref,
            "installation": self.installation,
            "permissions": [
                {
                    "category": item.category,
                    "key": item.key,
                    # Flatpak metadata may declare arbitrary environment values.
                    # Keep them available in the parser result, but never expose
                    # their contents through a CLI or a persisted JSON payload.
                    "value": "[hidden]" if item.category.lower() == "environment" else item.value,
                }
                for item in self.permissions
            ],
            "error": self.error,
        }


class FlatpakManager:
    """Flatpak size analysis, permission auditing, and cleanup.

    All public methods are ``@staticmethod`` so the class can be used without
    instantiation, consistent with other service managers.
    """

    @staticmethod
    def is_available() -> bool:
        """Check if flatpak is installed."""
        return cached_which("flatpak") is not None

    @staticmethod
    def get_flatpak_sizes() -> List[FlatpakSizeEntry]:
        """Get installed Flatpak apps with their disk sizes.

        Returns:
            List of FlatpakSizeEntry sorted by size (largest first).
        """
        entries: List[FlatpakSizeEntry] = []
        if not FlatpakManager.is_available():
            return entries

        try:
            result = subprocess.run(
                ["flatpak", "list", "--app", "--columns=name,application,size,runtime,ref"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        app_id = parts[1].strip()
                        size_str = parts[2].strip()
                        runtime = parts[3].strip() if len(parts) > 3 else ""
                        ref = parts[4].strip() if len(parts) > 4 else ""

                        size_bytes = FlatpakManager._parse_size(size_str)
                        entries.append(
                            FlatpakSizeEntry(
                                name=name,
                                app_id=app_id,
                                size_bytes=size_bytes,
                                size_str=size_str,
                                runtime=runtime,
                                ref=ref,
                            )
                        )
            entries.sort(key=lambda e: e.size_bytes, reverse=True)
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error("Failed to get Flatpak sizes: %s", e)
        return entries

    @staticmethod
    def _parse_size(size_str: str) -> int:
        """Parse a human-readable size string to bytes.

        Handles formats like "1.2 GB", "500 MB", "100 kB".
        """
        size_str = size_str.strip()
        if not size_str:
            return 0

        multipliers = {
            "b": 1,
            "kb": 1024,
            "mb": 1024**2,
            "gb": 1024**3,
            "tb": 1024**4,
        }

        try:
            parts = size_str.split()
            if len(parts) >= 2:
                number = float(parts[0].replace(",", "."))
                unit = parts[1].lower().replace("i", "")
                return int(number * multipliers.get(unit, 1))
            return int(float(size_str))
        except (ValueError, IndexError):
            return 0

    @staticmethod
    def get_flatpak_permissions(ref: str, *, installation: str, name: str = "", strict: bool = False) -> FlatpakAppPermissions:
        """Read metadata permissions for one exact installed application ref.

        Args:
            ref: Full installed application ref (e.g. app/id/arch/branch).

        Returns:
            FlatpakAppPermissions with all granted permissions.
        """
        from services.software.installed_applications import installation_flag, validate_ref

        if not validate_ref(ref):
            raise ValueError("Select a valid full Flatpak application ref.")
        scope = [installation_flag(installation)]
        app_id = ref.split("/", 3)[1]
        permissions: List[FlatpakPermission] = []
        display_name = name or app_id

        if not FlatpakManager.is_available():
            if strict:
                raise ValueError("Flatpak is not available for permission inspection.")
            return FlatpakAppPermissions(app_id=app_id, name=display_name, permissions=[], ref=ref,
                                         installation=installation, error="Flatpak is unavailable.")

        try:
            result = subprocess.run(
                ["flatpak", "info", *scope, "--show-permissions", ref],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                if strict:
                    raise ValueError("Permissions could not be read from this installation.")
                return FlatpakAppPermissions(app_id, display_name, [], ref, installation,
                                             "Permissions could not be read.")
            if len(result.stdout.encode("utf-8")) > 65536:
                raise ValueError("The permission response exceeds the 64 KiB limit.")
            current_category = "Context"
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_category = line[1:-1].strip()
                elif "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    if not key or len(key) > 128:
                        raise ValueError("Flatpak returned an invalid permission key.")
                    for val in value.split(";"):
                        val = val.strip()
                        if val:
                            permissions.append(FlatpakPermission(current_category, key, val))

        except (subprocess.TimeoutExpired, OSError, ValueError) as e:
            logger.error("Failed to inspect permissions for %s: %s", app_id, e)
            if strict:
                if isinstance(e, ValueError):
                    raise
                raise ValueError("Permission inspection failed.") from e
            return FlatpakAppPermissions(app_id, display_name, [], ref, installation, "Permission inspection failed.")

        return FlatpakAppPermissions(app_id, display_name, permissions, ref, installation)

    @staticmethod
    def get_all_permissions() -> List[FlatpakAppPermissions]:
        """Get permissions for all installed Flatpak apps.

        Returns:
            List of FlatpakAppPermissions for each installed app.
        """
        from services.software.installed_applications import InstalledApplicationService

        service = InstalledApplicationService()
        inventory = service.flatpaks()
        if inventory.unknown_sources:
            return []
        all_perms: List[FlatpakAppPermissions] = []
        for app in inventory.applications:
            try:
                all_perms.append(service.permissions(app))
            except (OSError, RuntimeError, TypeError, ValueError):
                continue
        return all_perms

    @staticmethod
    def find_orphan_runtimes() -> List[str]:
        """Find runtimes not referenced by any installed app.

        Returns:
            List of runtime refs that can be safely removed.
        """
        from services.software.flatpak_maintenance import FlatpakMaintenanceService
        snapshot = FlatpakMaintenanceService().unused("user")
        if not snapshot.available:
            raise RuntimeError(snapshot.error)
        return [item.ref for item in snapshot.refs]

    @staticmethod
    def cleanup_unused() -> CommandTuple:
        """Build command to remove unused Flatpak runtimes.

        Returns:
            CommandTuple for the cleanup operation.
        """
        raise RuntimeError("Review exact unused runtimes in Apps and use the remove-unused-flatpaks Action Center workflow.")

    @staticmethod
    def get_total_size() -> str:
        """Get total disk space used by all Flatpak apps.

        Returns:
            Human-readable total size string.
        """
        entries = FlatpakManager.get_flatpak_sizes()
        total = sum(e.size_bytes for e in entries)

        if total >= 1024**3:
            return f"{total / (1024**3):.1f} GB"
        if total >= 1024**2:
            return f"{total / (1024**2):.1f} MB"
        if total >= 1024:
            return f"{total / 1024:.1f} KB"
        return f"{total} B"
