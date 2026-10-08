"""Read-only installation inventory with explicit source failures."""
from __future__ import annotations

import re
import os
import subprocess
import time
from pathlib import Path
from dataclasses import asdict, dataclass
from typing import Callable, Sequence

from core.executor.action_result import ActionResult
from core.tasks.applications import ApplicationCatalog
from services.software.flatpak import FlatpakAppPermissions, FlatpakManager

_REF = re.compile(r"^app/[A-Za-z0-9][A-Za-z0-9._-]{1,255}/[A-Za-z0-9_-]+/[A-Za-z0-9._-]+$")
_INSTALLATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
Probe = Callable[[Sequence[str]], ActionResult]


def installation_flag(installation: str) -> str:
    if not _INSTALLATION.fullmatch(installation):
        raise ValueError("Invalid Flatpak installation identifier.")
    return f"--{installation}" if installation in {"user", "system"} else f"--installation={installation}"


def validate_ref(ref: str) -> bool:
    return bool(_REF.fullmatch(ref))


@dataclass(frozen=True)
class InstalledApplication:
    name: str
    app_id: str
    source: str
    installation: str
    ref: str
    version: str = ""
    size: str = ""

    @property
    def size_bytes(self) -> int | None:
        """Parse reported logical size for local sorting; never estimate savings."""
        match = re.fullmatch(r"([0-9]+(?:[.,][0-9]+)?)\s*(B|kB|KB|MB|GB|TB|KiB|MiB|GiB|TiB)", self.size.strip())
        if not match or len(match[1]) > 30:
            return None
        units = {"B": 1, "kB": 1000, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4}
        return int(float(match[1].replace(",", ".")) * units[match[2]])

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class InstalledInventory:
    applications: tuple[InstalledApplication, ...] = ()
    errors: tuple[str, ...] = ()
    unknown_sources: frozenset[str] = frozenset()

    @property
    def installed_ids(self) -> frozenset[str]:
        return frozenset(item.app_id for item in self.applications)

    def to_dict(self) -> dict[str, object]:
        return {"applications": [item.to_dict() for item in self.applications], "errors": list(self.errors), "unknown_sources": sorted(self.unknown_sources)}


def parse_flatpak_inventory(output: str) -> tuple[InstalledApplication, ...]:
    apps = []
    identities = set()
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != 6:
            raise ValueError("Flatpak returned an invalid installation inventory.")
        name, app_id, ref, version, size, installation = (part.strip() for part in fields)
        installation_flag(installation)
        # flatpak list --app prints id/arch/branch; preserve a full app ref.
        if len(ref.split("/")) == 3:
            ref = f"app/{ref}"
        if not validate_ref(ref) or ref.split("/")[1] != app_id or not name:
            raise ValueError("Flatpak returned an invalid application identity.")
        identity = (installation, ref)
        if identity in identities:
            raise ValueError("Flatpak returned a duplicate installation identity.")
        identities.add(identity)
        apps.append(InstalledApplication(name, app_id, "flatpak", installation, ref, version, size))
    return tuple(apps)


class InstalledApplicationService:
    """Inventory Flatpaks and visible RPM apps, retaining curated fallbacks."""
    FLATPAK_VECTOR = ("flatpak", "list", "--app", "--columns=name,application,ref,version,size,installation")

    def __init__(self, *, probe: Probe | None = None, catalog: ApplicationCatalog | None = None,
                 desktop_roots: tuple[Path, ...] | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.probe = probe or self._probe
        self._custom_probe = probe
        self.catalog = catalog or ApplicationCatalog()
        self.desktop_roots = desktop_roots
        self.clock = clock

    @staticmethod
    def _probe(vector: Sequence[str], *, timeout: float = 15) -> ActionResult:
        try:
            environment = {**os.environ, "LC_ALL": "C"} if tuple(vector[:2]) == ("rpm", "-qf") else None
            result = subprocess.run(list(vector), capture_output=True, text=True, timeout=timeout, env=environment)
            return ActionResult(result.returncode == 0, "Inventory read", exit_code=result.returncode, stdout=result.stdout)
        except (OSError, subprocess.TimeoutExpired):
            return ActionResult(False, "The installation inventory could not be read.")

    def flatpaks(self) -> InstalledInventory:
        result = self.probe(self.FLATPAK_VECTOR)
        if not result.success:
            return InstalledInventory(errors=("Flatpak installation inventory could not be read.",), unknown_sources=frozenset({"flatpak"}))
        try:
            return InstalledInventory(parse_flatpak_inventory(result.stdout))
        except ValueError as exc:
            return InstalledInventory(errors=(str(exc),), unknown_sources=frozenset({"flatpak"}))

    def snapshot(self) -> InstalledInventory:
        flatpaks = self.flatpaks()
        deadline = self.clock() + 20.0
        rpms = tuple(item for item in self.catalog.all() if item.source == "fedora")
        vector = ("rpm", "-qa", "--qf", "%{NAME}\\t%{VERSION}-%{RELEASE}\\t%{SIZE}\\n")
        remaining = deadline - self.clock()
        result = (self._custom_probe(vector) if self._custom_probe else self._probe(vector, timeout=min(15, remaining))) if remaining > 0 else ActionResult(False, "RPM inventory time limit reached.")
        apps = list(flatpaks.applications)
        errors = list(flatpaks.errors)
        unknown = set(flatpaks.unknown_sources)
        if not result.success:
            errors.append("RPM installation inventory could not be read.")
            unknown.add("fedora")
        else:
            records = {item.package_id: item for item in rpms}
            try:
                installed: dict[str, list[tuple[str, int]]] = {}
                for line in result.stdout.splitlines():
                    fields = line.split("\t")
                    if len(fields) != 3 or not fields[0] or not fields[2].isdigit():
                        raise ValueError("RPM returned an invalid installation inventory.")
                    package, version, size = fields
                    installed.setdefault(package, []).append((version, int(size)))
                from services.software.rpm_desktop_applications import discover_rpm_desktop_applications

                def ownership_probe(vector: Sequence[str], timeout: float) -> ActionResult:
                    return self._custom_probe(vector) if self._custom_probe else self._probe(vector, timeout=timeout)

                desktop_apps = discover_rpm_desktop_applications(ownership_probe, deadline=deadline, clock=self.clock, roots=self.desktop_roots)
                errors.extend(desktop_apps.errors)
                if desktop_apps.errors:
                    unknown.add("fedora")
                for package in sorted(installed):
                    if package not in records and package not in desktop_apps.names:
                        continue
                    name = records[package].name if package in records else desktop_apps.names[package]
                    versions = ", ".join(sorted({version for version, _size in installed[package]}))
                    size_bytes = sum(size for _version, size in installed[package])
                    apps.append(InstalledApplication(name, package, "fedora", "system", package, versions, f"{size_bytes} B"))
            except ValueError as exc:
                apps = list(flatpaks.applications)
                errors.append(str(exc))
                unknown.add("fedora")
        return InstalledInventory(tuple(apps), tuple(errors), frozenset(unknown))

    def details(self, app: InstalledApplication):
        if app.source != "flatpak":
            raise ValueError("Detailed Flatpak metadata is unavailable for RPM applications.")
        if not validate_ref(app.ref):
            raise ValueError("The selected Flatpak identity is invalid.")
        from services.software.flatpak_maintenance import FlatpakMaintenanceService
        return FlatpakMaintenanceService().details(app.ref, app.installation)

    def unused(self, installation: str):
        from services.software.flatpak_maintenance import FlatpakMaintenanceService
        return FlatpakMaintenanceService().unused(installation)

    def installations(self):
        from services.software.flatpak_maintenance import FlatpakMaintenanceService
        return FlatpakMaintenanceService().installations()

    def permissions(self, app: InstalledApplication) -> FlatpakAppPermissions:
        if app.source != "flatpak":
            raise ValueError("Permission inspection is only available for Flatpak applications.")
        if not validate_ref(app.ref) or app.ref.split("/")[1] != app.app_id:
            raise ValueError("The selected Flatpak identity is invalid.")
        return FlatpakManager.get_flatpak_permissions(
            app.ref, installation=app.installation, name=app.name, strict=True,
        )


def filter_installed_applications(
    inventory: InstalledInventory, *, query: str = "", source: str = "", installation: str = "", sort: str = "name",
) -> tuple[InstalledApplication, ...]:
    """Project captured inventory without probing any installation."""
    query = query.strip().casefold()
    apps = [app for app in inventory.applications
            if (not source or app.source == source) and (not installation or app.installation == installation)
            and (not query or query in " ".join((app.name, app.app_id, app.ref, app.installation, app.source, app.version)).casefold())]
    if sort == "size":
        apps.sort(key=lambda app: (app.size_bytes is None, -(app.size_bytes or 0), app.name.casefold(), app.installation, app.ref))
    else:
        apps.sort(key=lambda app: (app.name.casefold(), app.installation, app.ref))
    return tuple(apps)
