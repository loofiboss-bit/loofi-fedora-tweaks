"""Read-only installation inventory with explicit source failures."""
from __future__ import annotations

import re
import os
import selectors
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
MAX_INVENTORY_OUTPUT_BYTES = 1024 * 1024
MAX_INVENTORY_ROWS = 10000
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


def parse_flatpak_inventory(output: str, *, installation: str | None = None) -> tuple[InstalledApplication, ...]:
    apps = []
    identities = set()
    lines = output.splitlines()
    if len(lines) > MAX_INVENTORY_ROWS:
        raise ValueError("Flatpak installation inventory exceeded its row limit.")
    for line in lines:
        if not line.strip():
            continue
        fields = line.split("\t")
        expected_lengths = {6} if installation is None else {5, 6}
        if len(fields) not in expected_lengths:
            raise ValueError("Flatpak returned an invalid installation inventory.")
        if installation is None:
            name, app_id, ref, version, size, scope = (part.strip() for part in fields)
        else:
            # A scoped query supplies the stable installation ID. The optional
            # CLI installation column may contain a display value, so it is
            # intentionally not used to form the application identity.
            name, app_id, ref, version, size = (part.strip() for part in fields[:5])
            scope = installation
        installation_flag(scope)
        # flatpak list --app prints id/arch/branch; preserve a full app ref.
        if len(ref.split("/")) == 3:
            ref = f"app/{ref}"
        if not validate_ref(ref) or ref.split("/")[1] != app_id or not name:
            raise ValueError("Flatpak returned an invalid application identity.")
        identity = (scope, ref)
        if identity in identities:
            raise ValueError("Flatpak returned a duplicate installation identity.")
        identities.add(identity)
        apps.append(InstalledApplication(name, app_id, "flatpak", scope, ref, version, size))
    return tuple(apps)


class InstalledApplicationService:
    """Inventory Flatpaks and visible RPM apps, retaining curated fallbacks."""
    FLATPAK_VECTOR = ("flatpak", "list", "--app", "--columns=name,application,ref,version,size,installation")

    def __init__(self, *, probe: Probe | None = None, catalog: ApplicationCatalog | None = None,
                 desktop_roots: tuple[Path, ...] | None = None, clock: Callable[[], float] = time.monotonic,
                 installation_reader: Callable[[], Sequence[str]] | None = None) -> None:
        self.probe = probe or self._probe
        self._custom_probe = probe
        self.catalog = catalog or ApplicationCatalog()
        self.desktop_roots = desktop_roots
        self.clock = clock
        self.installation_reader = installation_reader

    @staticmethod
    def _probe(vector: Sequence[str], *, timeout: float = 15,
               cancelled: Callable[[], bool] = lambda: False) -> ActionResult:
        process = None
        selector = None
        try:
            environment = {**os.environ, "LC_ALL": "C"} if tuple(vector[:2]) == ("rpm", "-qf") else None
            process = subprocess.Popen(list(vector), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment)
            if process.stdout is None:
                return ActionResult(False, "The installation inventory could not be read.")
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            output = bytearray()
            deadline = time.monotonic() + max(0.0, timeout)
            while selector.get_map():
                if cancelled():
                    process.kill()
                    process.wait()
                    return ActionResult(False, "The installation inventory read was cancelled.", exit_code=-1)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    process.kill()
                    process.wait()
                    return ActionResult(False, "The installation inventory read timed out.", exit_code=-1)
                ready = selector.select(min(remaining, 0.05))
                if not ready:
                    continue
                chunk = os.read(process.stdout.fileno(), min(8192, MAX_INVENTORY_OUTPUT_BYTES + 1 - len(output)))
                if not chunk:
                    selector.unregister(process.stdout)
                    break
                output.extend(chunk)
                if len(output) > MAX_INVENTORY_OUTPUT_BYTES:
                    process.kill()
                    process.wait()
                    return ActionResult(False, "The installation inventory exceeded its output limit.", exit_code=-1)
            returncode = process.wait(timeout=max(0.01, deadline - time.monotonic()))
            stdout = output.decode("utf-8", errors="replace")
            return ActionResult(returncode == 0, "Inventory read" if returncode == 0 else "The installation inventory could not be read.", exit_code=returncode, stdout=stdout)
        except (OSError, subprocess.SubprocessError):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            return ActionResult(False, "The installation inventory could not be read.")
        finally:
            if selector is not None:
                selector.close()
            if process is not None and process.stdout is not None:
                process.stdout.close()

    def _read_probe(self, vector: Sequence[str], *, timeout: float,
                    cancelled: Callable[[], bool]) -> ActionResult:
        if cancelled():
            return ActionResult(False, "The installation inventory read was cancelled.", exit_code=-1)
        if self._custom_probe:
            return self._custom_probe(vector)
        return self._probe(vector, timeout=timeout, cancelled=cancelled)

    def flatpaks(self, *, installation: str | None = None, timeout: float = 8.0,
                 cancelled: Callable[[], bool] = lambda: False) -> InstalledInventory:
        if installation is not None:
            try:
                installation_flag(installation)
            except (TypeError, ValueError) as exc:
                return InstalledInventory(errors=(str(exc),), unknown_sources=frozenset({"flatpak"}))
            scopes: tuple[str, ...] = (installation,)
        elif self._custom_probe is not None and self.installation_reader is None:
            # Keep the existing aggregate probe contract for reviewed executors
            # and deterministic test doubles.
            return self._aggregate_flatpaks(timeout=timeout, cancelled=cancelled)
        else:
            try:
                if self.installation_reader is None:
                    from services.software.flatpak_maintenance import FlatpakMaintenanceService
                    scope_values: Sequence[str] = FlatpakMaintenanceService().installations()
                else:
                    scope_values = self.installation_reader()
                scopes = tuple(dict.fromkeys(scope_values))
            except (OSError, RuntimeError, TypeError, ValueError):
                scopes = tuple()
            if not scopes:
                # Preserve the default-installation listing where optional
                # libflatpak enumeration is unavailable. Unknown named scopes
                # still fail closed in the aggregate parser.
                return self._aggregate_flatpaks(timeout=timeout, cancelled=cancelled)

        applications: list[InstalledApplication] = []
        errors: list[str] = []
        deadline = time.monotonic() + max(0.0, timeout)
        for scope in scopes:
            try:
                scope_flag = installation_flag(scope)
            except (TypeError, ValueError):
                errors.append("Flatpak returned an invalid installation identifier.")
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0 or cancelled():
                errors.append("Flatpak installation inventory read was cancelled or exceeded its time limit.")
                break
            vector = ("flatpak", "list", scope_flag, "--app", "--columns=name,application,ref,version,size")
            result = self._read_probe(vector, timeout=remaining, cancelled=cancelled)
            if not result.success:
                errors.append("Flatpak installation inventory could not be read for " + scope + ".")
                continue
            try:
                applications.extend(parse_flatpak_inventory(result.stdout, installation=scope))
            except ValueError as exc:
                errors.append(str(exc))
        return InstalledInventory(
            tuple(applications), tuple(dict.fromkeys(errors)),
            frozenset({"flatpak"}) if errors else frozenset(),
        )

    def _aggregate_flatpaks(self, *, timeout: float,
                            cancelled: Callable[[], bool]) -> InstalledInventory:
        result = self._read_probe(self.FLATPAK_VECTOR, timeout=max(0.0, timeout), cancelled=cancelled)
        if not result.success:
            return InstalledInventory(errors=("Flatpak installation inventory could not be read.",), unknown_sources=frozenset({"flatpak"}))
        try:
            return InstalledInventory(parse_flatpak_inventory(result.stdout))
        except ValueError as exc:
            return InstalledInventory(errors=(str(exc),), unknown_sources=frozenset({"flatpak"}))

    def snapshot(self, *, cancelled: Callable[[], bool] = lambda: False) -> InstalledInventory:
        deadline = self.clock() + 20.0
        flatpak_budget = max(0.0, min(8.0, deadline - self.clock()))
        flatpaks = self.flatpaks(timeout=flatpak_budget, cancelled=cancelled)
        if cancelled():
            return InstalledInventory(flatpaks.applications, flatpaks.errors + ("Application inventory read was cancelled.",),
                                      flatpaks.unknown_sources | frozenset({"fedora"}))
        rpms = tuple(item for item in self.catalog.all() if item.source == "fedora")
        vector = ("rpm", "-qa", "--qf", "%{NAME}\\t%{VERSION}-%{RELEASE}\\t%{SIZE}\\n")
        remaining = deadline - self.clock()
        result = self._read_probe(vector, timeout=min(remaining, 12.0), cancelled=cancelled) if remaining > 0 else ActionResult(False, "RPM inventory time limit reached.")
        apps = list(flatpaks.applications)
        errors = list(flatpaks.errors)
        unknown = set(flatpaks.unknown_sources)
        if not result.success:
            errors.append("RPM installation inventory could not be read.")
            unknown.add("fedora")
        else:
            records = {item.package_id: item for item in rpms}
            for item in self.catalog.all():
                if item.source != "flatpak":
                    continue
                for package in item.metadata.get("rpm_counterparts", ()):
                    records[package] = item
            try:
                installed: dict[str, list[tuple[str, int]]] = {}
                rows = result.stdout.splitlines()
                if len(rows) > MAX_INVENTORY_ROWS:
                    raise ValueError("RPM installation inventory exceeded its row limit.")
                for line in rows:
                    fields = line.split("\t")
                    if len(fields) != 3 or not fields[0] or not fields[2].isdigit():
                        raise ValueError("RPM returned an invalid installation inventory.")
                    package, version, size = fields
                    installed.setdefault(package, []).append((version, int(size)))
                from services.software.rpm_desktop_applications import discover_rpm_desktop_applications

                def ownership_probe(vector: Sequence[str], timeout: float) -> ActionResult:
                    return self._read_probe(vector, timeout=min(timeout, max(0.0, deadline - self.clock())), cancelled=cancelled)

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

    def snapshot_for_troubleshooting(self, *, cancelled: Callable[[], bool]) -> InstalledInventory:
        """Expose the existing exact inventory through a cancellable bounded read."""
        return self.snapshot(cancelled=cancelled)

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
