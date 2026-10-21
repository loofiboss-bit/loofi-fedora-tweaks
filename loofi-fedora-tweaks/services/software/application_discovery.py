"""Local AppStream discovery; metadata never supplies executable commands.

A component is only an index entry. RPM repository identity is joined against
DNF's existing cache, and Flatpak identity is bound to its configured remote
and installation. Discovery does not fetch metadata or authorize installation.
"""
from __future__ import annotations

import configparser
import gzip
import hashlib
import re
import subprocess
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence, cast

from core.actions.bundles import ActionBundle, ActionBundleItem
from core.tasks.applications import ApplicationCatalog, ApplicationContext, ApplicationEligibility, ApplicationRecord, InstallSelection
from services.system.system import SystemManager

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._:-]{0,255}$")
_REF = re.compile(r"^app/[A-Za-z0-9][A-Za-z0-9._-]{1,255}/[A-Za-z0-9_-]+/[A-Za-z0-9._-]+$")
MAX_XML_BYTES = 64 * 1024 * 1024
MAX_COMPONENTS = 50000
_PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._-]{0,127}$")


def rpm_catalog_paths() -> tuple[Path, ...]:
    """Return packaged or locally cached catalogs without downloading metadata."""
    return tuple(path for root in ("/usr/share/swcatalog/xml", "/var/cache/swcatalog/xml")
                 for path in sorted(Path(root).glob("*.xml*")) if path.name.endswith((".xml", ".xml.gz")))


def _read_appstream(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        payload = stream.read(MAX_XML_BYTES + 1)
    if len(payload) > MAX_XML_BYTES or b"<!DOCTYPE" in payload or b"<!ENTITY" in payload:
        raise ValueError("Unsafe or oversized metadata")
    root = ET.fromstring(payload)
    if root.tag != "components":
        raise ValueError("Not an AppStream collection")
    return root


def rpm_appstream_catalog_available(paths: Sequence[Path] | None = None) -> bool:
    """Check real bounded catalogs, independently of DNF's package cache."""
    for path in rpm_catalog_paths() if paths is None else paths:
        try:
            root = _read_appstream(path)
            for index, component in enumerate(root.findall("component")):
                if index >= MAX_COMPONENTS:
                    break
                if (component.get("type") in {"desktop", "desktop-application"}
                        and component.findtext("id", "").strip() and component.findtext("name", "").strip()
                        and _PACKAGE.fullmatch(component.findtext("pkgname", "").strip())):
                    return True
        except (OSError, ValueError, ET.ParseError, DefusedXmlException, EOFError):
            continue
    return False


@dataclass(frozen=True)
class MetadataSource:
    """Trusted filesystem location and independently configured source identity."""
    path: Path
    source: str
    remote: str = ""
    installation: str = ""


@dataclass(frozen=True)
class DiscoverySnapshot:
    records: tuple[ApplicationRecord, ...] = ()
    checked_at: str = ""
    metadata_updated_at: str = ""
    status: str = "missing"
    issues: tuple[str, ...] = ()
    refresh_targets: tuple[tuple[str, str, str], ...] = ()


class ApplicationDiscoveryCatalog(ApplicationCatalog):
    """Existing catalog contract with separately identified AppStream choices."""
    def __init__(self, curated: ApplicationCatalog, discovered: Sequence[ApplicationRecord], *, installed_identities: frozenset[tuple[str, str]] = frozenset()) -> None:
        super().__init__(curated.all())
        self._installed_identities = installed_identities
        self._records = (*curated.all(), *discovered)
        self._by_id = {item.id: item for item in self._records}

    def eligibility(self, application, context=None):
        record = application if isinstance(application, ApplicationRecord) else self.get(str(application))
        if record is not None and not record.curated and record.source == "flatpak" and context is not None:
            identity = (str(record.metadata["installation"]), str(record.metadata["ref"]))
            if identity in self._installed_identities:
                return ApplicationEligibility(record, "installed", "Already installed in this installation.")
            context = replace(context, installed_ids=frozenset())
        return super().eligibility(application, context)

    def build_selection(self, application_ids, *, context: ApplicationContext, title="Install selected applications") -> InstallSelection:
        selection = super().build_selection(application_ids, context=context, title=title)
        items = []
        for record, raw_item in zip(selection.applications, selection.bundle.items):
            item = cast(ActionBundleItem, raw_item)
            parameters = dict(item.parameters)
            if not record.curated:
                if record.source == "fedora":
                    parameters.update(package_id=f"{record.package_id}-{record.metadata['version']}.{record.metadata['arch']}", repo_id=record.metadata["repo_id"], component_id=record.metadata["component_id"])
                else:
                    parameters.update(package_id=record.metadata["ref"], installation=record.metadata["installation"], remote=record.metadata["remote"])
            metadata = dict(item.metadata)
            if not record.curated:
                metadata["source_label"] = ("Flatpak · " + str(record.metadata["remote"]) + " · " + str(record.metadata["installation"])) if record.source == "flatpak" else "RPM · " + str(record.metadata["repo_id"])
                metadata["component_id"] = str(record.metadata["component_id"])
            items.append(ActionBundleItem(action_id=item.action_id, parameters=parameters, title=item.title, metadata=metadata))
        bundle = ActionBundle.applications(tuple(items), title=title, description=selection.bundle.description, metadata=dict(selection.bundle.metadata))
        return InstallSelection(selection.applications, context, bundle)


class ApplicationDiscoveryService:
    """Bounded local readers with cooperative cancellation between sources."""
    def __init__(self, sources: Sequence[MetadataSource] | None = None, *, runner: Callable | None = None) -> None:
        self._sources = tuple(sources) if sources is not None else None
        self._runner = runner
        self._refresh_targets: list[tuple[str, str, str]] = []
        self._source_issues: list[str] = []

    def _read(self, vector: list[str], cancelled: Callable[[], bool] = lambda: False) -> str:
        if self._runner is not None:
            result = self._runner(vector, capture_output=True, text=True, timeout=20, check=False)
            success = result.returncode == 0
        else:
            from services.software.installed_applications import InstalledApplicationService
            result = InstalledApplicationService._probe(vector, timeout=20, cancelled=cancelled)
            success = result.success
        if not success or len(result.stdout) > MAX_XML_BYTES:
            raise ValueError("Local metadata unavailable")
        return str(result.stdout)

    def _configured_sources(self, cancelled: Callable[[], bool]) -> tuple[MetadataSource, ...]:
        self._source_issues = []
        self._refresh_targets = [("fedora", "", "")] if not SystemManager.is_atomic() else []
        sources = [MetadataSource(path, "fedora") for path in rpm_catalog_paths()]
        if not sources and not SystemManager.is_atomic():
            self._source_issues.append("Local RPM AppStream catalog is missing. Review installation of appstream-data; refreshing DNF metadata alone cannot supply it.")
        installations = [("system", Path("/var/lib/flatpak"), "--system"), ("user", Path.home() / ".local/share/flatpak", "--user")]
        for configuration in sorted(Path("/etc/flatpak/installations.d").glob("*.conf")):
            parser = configparser.ConfigParser(interpolation=None)
            try:
                parser.read(configuration, encoding="utf-8")
                for section in parser.sections():
                    match = re.fullmatch(r'Installation "([A-Za-z0-9][A-Za-z0-9._-]{0,127})"', section)
                    location = parser.get(section, "Path", fallback="")
                    if match and match[1] not in {"system", "user", "default"} and Path(location).is_absolute():
                        installations.append((match[1], Path(location), "--installation=" + match[1]))
            except (OSError, configparser.Error):
                continue
        for installation, root, flag in installations:
            if cancelled():
                break
            try:
                remotes = self._read(["flatpak", "remotes", flag, "--columns=name"], cancelled).splitlines()
            except (OSError, subprocess.SubprocessError, ValueError):
                self._source_issues.append(f"Configured Flatpak remotes could not be read for {installation}.")
                continue
            for remote in remotes:
                if _SAFE.fullmatch(remote):
                    self._refresh_targets.append(("flatpak", installation, remote))
                    paths = sorted((root / "appstream" / remote).glob("*/active/appstream.xml.gz"))
                    if not paths:
                        self._source_issues.append(f"Local AppStream metadata is missing for {installation} / {remote}.")
                    sources.extend(MetadataSource(path, "flatpak", remote, installation) for path in paths)
        return tuple(sources)

    def snapshot(self, *, cancelled: Callable[[], bool] = lambda: False) -> DiscoverySnapshot:
        checked = datetime.now(timezone.utc).isoformat()
        issues: list[str] = []
        records: dict[str, ApplicationRecord] = {}
        timestamps: list[float] = []
        rpm_components: list[tuple[str, str, str, str, str]] = []
        sources = self._sources if self._sources is not None else self._configured_sources(cancelled)
        if self._sources is None:
            issues.extend(self._source_issues)
        for source in sources:
            if cancelled():
                return DiscoverySnapshot(tuple(records.values()), checked, status="cancelled", issues=tuple(issues))
            try:
                root = _read_appstream(source.path)
                timestamps.append(source.path.stat().st_mtime)
                for index, component in enumerate(root.findall("component")):
                    if cancelled():
                        break
                    if index >= MAX_COMPONENTS:
                        issues.append(f"The component limit was reached for {source.path.name}.")
                        break
                    if component.get("type") not in {"desktop", "desktop-application"}:
                        continue
                    component_id = component.findtext("id", "").strip()
                    name = component.findtext("name", "").strip()[:256]
                    summary = component.findtext("summary", "").strip()[:1024]
                    category = component.findtext("categories/category", "Applications").strip()[:128]
                    if not component_id or not name:
                        continue
                    if source.source == "fedora":
                        package = component.findtext("pkgname", "").strip()
                        if _PACKAGE.fullmatch(package):
                            rpm_components.append((component_id, name, summary or name, category or "Applications", package))
                        continue
                    for bundle in component.findall("bundle"):
                        ref = (bundle.text or "").strip()
                        if bundle.get("type") != "flatpak" or not _REF.fullmatch(ref):
                            continue
                        identity = f"flatpak:{source.installation}:{source.remote}:{ref}"
                        record_id = "appstream-" + hashlib.sha256(identity.encode()).hexdigest()[:24]
                        release = component.find("releases/release")
                        records[record_id] = ApplicationRecord(
                            record_id, name, summary or name, category or "Applications", "flatpak", ref.split("/")[1], curated=False,
                            metadata={"component_id": component_id, "ref": ref, "installation": source.installation, "remote": source.remote, "version": release.get("version", "") if release is not None else ""})
            except (OSError, ValueError, ET.ParseError, DefusedXmlException, EOFError):
                issues.append(f"Could not read {source.path.name}.")
        if rpm_components and not cancelled():
            try:
                if SystemManager.is_atomic():
                    raise ValueError("RPM discovery is unavailable on Atomic")
                manager = SystemManager.get_package_manager()
                if manager != "dnf5":
                    raise ValueError("DNF5 required")
                package_names = sorted({item[4] for item in rpm_components})
                outputs: list[str] = []
                output_size = 0
                for offset in range(0, len(package_names), 256):
                    if cancelled():
                        break
                    batch_output = self._read([manager, "--cacheonly", "repoquery", "--available", "--queryformat", "%{name}\t%{repoid}\t%{evr}\t%{arch}\n", *package_names[offset:offset + 256]], cancelled)
                    output_size += len(batch_output)
                    if output_size > MAX_XML_BYTES:
                        raise ValueError("RPM metadata exceeded the output bound")
                    outputs.append(batch_output)
                output = "\n".join(outputs)
                packages: dict[str, set[tuple[str, str, str]]] = {}
                for line in output.splitlines():
                    fields = line.split("\t")
                    if len(fields) == 4 and _PACKAGE.fullmatch(fields[0]) and _SAFE.fullmatch(fields[1]) and 0 < len(fields[2]) < 256 and not any(ord(ch) < 32 for ch in fields[2]) and _SAFE.fullmatch(fields[3]):
                        packages.setdefault(fields[0], set()).add((fields[1], fields[2], fields[3]))
                for component_id, name, summary, category, package in rpm_components:
                    for repo, version, arch in sorted(packages.get(package, ())):
                        identity = f"rpm:{repo}:{package}:{version}:{arch}:{component_id}"
                        record_id = "appstream-" + hashlib.sha256(identity.encode()).hexdigest()[:24]
                        records[record_id] = ApplicationRecord(
                            record_id, name, summary, category, "fedora", package, curated=False,
                            metadata={"component_id": component_id, "repo_id": repo, "version": version, "arch": arch})
            except (OSError, subprocess.SubprocessError, ValueError):
                issues.append("RPM metadata could not be matched to the local DNF5 cache.")
        if cancelled():
            status = "cancelled"
        else:
            status = "partial" if records and issues else "available" if records else "missing"
        updated = datetime.fromtimestamp(min(timestamps), timezone.utc).isoformat() if timestamps else ""
        return DiscoverySnapshot(tuple(sorted(records.values(), key=lambda item: (item.name.casefold(), item.id))), checked, updated, status, tuple(issues), tuple(self._refresh_targets))
