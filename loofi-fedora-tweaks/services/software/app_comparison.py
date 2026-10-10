"""Pure comparisons of captured application inventory, without additional probes."""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.tasks.applications import ApplicationCatalog
from services.software.installed_applications import InstalledApplication, InstalledInventory


@dataclass(frozen=True)
class ApplicationComparison:
    app_id: str
    installations: tuple[InstalledApplication, ...]
    errors: tuple[str, ...] = ()
    unknown_sources: frozenset[str] = frozenset()

    def to_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "installations": [app.to_dict() for app in self.installations],
            "errors": list(self.errors),
            "unknown_sources": sorted(self.unknown_sources),
        }


def compare_installations(inventory: InstalledInventory, app_id: str, *, catalog: ApplicationCatalog | None = None) -> ApplicationComparison:
    """Match exact Flatpak IDs and only catalog-declared RPM counterparts."""
    if not isinstance(app_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,255}", app_id):
        raise ValueError("Select a valid exact Flatpak application ID.")
    counterparts = {
        package for record in (catalog or ApplicationCatalog()).all()
        if record.source == "flatpak" and record.package_id == app_id
        for package in record.metadata.get("rpm_counterparts", ())
    }
    apps = tuple(sorted((app for app in inventory.applications
                         if (app.source == "flatpak" and app.app_id == app_id)
                         or (app.source == "fedora" and app.app_id in counterparts)),
                        key=lambda app: (app.source, app.installation, app.ref)))
    return ApplicationComparison(app_id, apps, inventory.errors, inventory.unknown_sources)


def comparison_id(app: InstalledApplication, *, catalog: ApplicationCatalog | None = None) -> str | None:
    """Resolve an RPM row to one explicitly declared Flatpak counterpart."""
    if app.source == "flatpak":
        return app.app_id
    return next((record.package_id for record in (catalog or ApplicationCatalog()).all()
                 if record.source == "flatpak" and app.app_id in record.metadata.get("rpm_counterparts", ())), None)
