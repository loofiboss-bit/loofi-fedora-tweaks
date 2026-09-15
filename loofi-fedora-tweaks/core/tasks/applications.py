"""Curated, source-aware application catalog for the v29 Install journey.

The catalog is intentionally static and reviewable. It is not a package
search endpoint and it never contains shell commands. A selected entry is
translated into an :class:`~core.actions.bundles.ActionBundle` containing only
the audited ``install-application`` action and its bounded parameters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Literal, Mapping, Sequence

from core.actions.bundles import ActionBundle, ActionBundleItem
from core.catalog_models import FedoraVariant

from .catalog import TaskContext


ApplicationSource = Literal["flatpak", "fedora"]
ApplicationState = Literal[
    "available",
    "installed",
    "advanced",
    "unavailable",
    "offline",
]

_PACKAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._-]{0,127}$")
_FLATPAK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,255}$")
_SOURCES = frozenset({"flatpak", "fedora"})


@dataclass(frozen=True)
class ApplicationRecord:
    """One curated application and its trusted source metadata."""

    id: str
    name: str
    description: str
    category: str
    source: ApplicationSource
    package_id: str
    gui: bool = True
    keywords: tuple[str, ...] = ()
    curated: bool = True
    requires_reboot_on_atomic: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        for value, label in (
            (self.id, "application id"),
            (self.name, "application name"),
            (self.description, "application description"),
            (self.category, "application category"),
        ):
            if not str(value).strip():
                raise ValueError(f"{label} must not be empty.")
        source = str(self.source).strip().lower()
        if source not in _SOURCES:
            raise ValueError("Application source must be flatpak or fedora.")
        package_id = str(self.package_id).strip()
        pattern = _FLATPAK_ID if source == "flatpak" else _PACKAGE_ID
        if not pattern.fullmatch(package_id) or package_id.startswith("-"):
            raise ValueError("Application package_id contains unsupported characters.")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "package_id", package_id)
        object.__setattr__(self, "keywords", tuple(str(item).strip() for item in self.keywords if str(item).strip()))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def source_label(self) -> str:
        return "Flatpak (Flathub)" if self.source == "flatpak" else "Fedora RPM"

    @property
    def search_text(self) -> str:
        return " ".join(
            (self.id, self.name, self.description, self.category, self.source, *self.keywords)
        ).casefold()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "source": self.source,
            "source_label": self.source_label,
            "package_id": self.package_id,
            "gui": self.gui,
            "keywords": list(self.keywords),
            "curated": self.curated,
            "requires_reboot_on_atomic": self.requires_reboot_on_atomic,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ApplicationContext:
    """Host facts needed to decide whether an application may be selected."""

    variant: FedoraVariant = FedoraVariant.UNKNOWN
    capabilities: frozenset[str] = frozenset()
    installed_ids: frozenset[str] = frozenset()
    online: bool | None = None

    @classmethod
    def from_task_context(
        cls,
        context: TaskContext,
        *,
        installed_ids: Iterable[str] = (),
        online: bool | None = None,
    ) -> "ApplicationContext":
        return cls(
            variant=context.variant,
            capabilities=context.capabilities,
            installed_ids=frozenset(str(item).strip() for item in installed_ids if str(item).strip()),
            online=online if online is not None else context.online,
        )


@dataclass(frozen=True)
class ApplicationEligibility:
    """Presentation state for one record under one host context."""

    application: ApplicationRecord
    state: ApplicationState
    reason: str
    advanced: bool = False
    requires_reboot: bool = False

    @property
    def selectable(self) -> bool:
        return self.state in {"available", "advanced"}

    @property
    def installed(self) -> bool:
        return self.state == "installed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "application": self.application.to_dict(),
            "state": self.state,
            "reason": self.reason,
            "advanced": self.advanced,
            "requires_reboot": self.requires_reboot,
            "selectable": self.selectable,
        }


@dataclass(frozen=True)
class InstallSelection:
    """Immutable reviewed selection ready to become an action bundle."""

    applications: tuple[ApplicationRecord, ...]
    context: ApplicationContext
    bundle: ActionBundle

    @property
    def count(self) -> int:
        return len(self.applications)

    @property
    def reboot_required(self) -> bool:
        return any(
            item.requires_reboot_on_atomic and self.context.variant is FedoraVariant.ATOMIC
            for item in self.applications
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "applications": [item.to_dict() for item in self.applications],
            "context": {
                "variant": self.context.variant.value,
                "capabilities": sorted(self.context.capabilities),
                "installed_ids": sorted(self.context.installed_ids),
                "online": self.context.online,
            },
            "bundle": self.bundle.to_dict(),
            "reboot_required": self.reboot_required,
        }


def _default_applications() -> tuple[ApplicationRecord, ...]:
    """Return the bounded first-party catalog.

    Flatpak entries are the preferred GUI path. Fedora RPM entries are kept
    for CLI and system-integrated tools that benefit from the host package
    manager. No remote metadata is fetched while rendering this list.
    """

    return (
        ApplicationRecord("firefox", "Firefox", "Private, standards-based web browser.", "Browser", "flatpak", "org.mozilla.firefox", keywords=("web", "browser")),
        ApplicationRecord("chromium", "Chromium", "Open-source Chromium browser for web testing.", "Browser", "flatpak", "org.chromium.Chromium", keywords=("web", "browser")),
        ApplicationRecord("vlc", "VLC", "Versatile media player with broad codec support.", "Media", "flatpak", "org.videolan.VLC", keywords=("video", "audio", "player")),
        ApplicationRecord("kdenlive", "Kdenlive", "Non-linear video editor for Fedora desktops.", "Media", "flatpak", "org.kde.kdenlive", keywords=("video", "editor")),
        ApplicationRecord("gimp", "GIMP", "Image editor for photographs and graphics.", "Graphics", "flatpak", "org.gimp.GIMP", keywords=("image", "graphics", "photo")),
        ApplicationRecord("inkscape", "Inkscape", "Vector graphics editor for illustrations and diagrams.", "Graphics", "flatpak", "org.inkscape.Inkscape", keywords=("vector", "design")),
        ApplicationRecord("libreoffice", "LibreOffice", "Full office suite for documents, spreadsheets, and presentations.", "Office", "flatpak", "org.libreoffice.LibreOffice", keywords=("documents", "office", "spreadsheet")),
        ApplicationRecord("thunderbird", "Thunderbird", "Email and calendar client from Mozilla.", "Communication", "flatpak", "org.mozilla.Thunderbird", keywords=("email", "mail", "calendar")),
        ApplicationRecord("signal", "Signal", "Private messaging client with end-to-end encryption.", "Communication", "flatpak", "org.signal.Signal", keywords=("chat", "messaging", "privacy")),
        ApplicationRecord("keepassxc", "KeePassXC", "Local password manager with encrypted vaults.", "Security", "flatpak", "org.keepassxc.KeePassXC", keywords=("password", "security")),
        ApplicationRecord("code", "Visual Studio Code", "Extensible editor for software development.", "Development", "flatpak", "com.visualstudio.code", keywords=("editor", "development", "programming")),
        ApplicationRecord("git", "Git", "Distributed version control for source code.", "Development", "fedora", "git", gui=False, keywords=("development", "version control", "cli"), requires_reboot_on_atomic=True),
        ApplicationRecord("podman", "Podman", "Daemonless containers for Fedora and Linux.", "Development", "fedora", "podman", gui=False, keywords=("containers", "cli", "development"), requires_reboot_on_atomic=True),
        ApplicationRecord("ripgrep", "ripgrep", "Fast recursive search for source trees and logs.", "Development", "fedora", "ripgrep", gui=False, keywords=("search", "cli", "development"), requires_reboot_on_atomic=True),
        ApplicationRecord("toolbox", "Toolbox", "Fedora development containers for immutable desktops.", "Development", "fedora", "toolbox", gui=False, keywords=("containers", "atomic", "development"), requires_reboot_on_atomic=True),
        ApplicationRecord("p7zip", "7-Zip", "Archive utility for common compressed formats.", "Utilities", "fedora", "p7zip", gui=False, keywords=("archive", "compression"), requires_reboot_on_atomic=True),
    )


class ApplicationCatalog:
    """Search and eligibility facade for the curated Install catalog."""

    def __init__(self, records: Sequence[ApplicationRecord] | None = None) -> None:
        selected = tuple(records or _default_applications())
        by_id: dict[str, ApplicationRecord] = {}
        for record in selected:
            if not record.curated:
                continue
            if record.id in by_id:
                raise ValueError(f"Duplicate application id: {record.id}")
            by_id[record.id] = record
        if not by_id:
            raise ValueError("Application catalog must contain at least one curated entry.")
        self._records = tuple(by_id.values())
        self._by_id = by_id

    def all(self, *, context: ApplicationContext | None = None) -> tuple[ApplicationRecord, ...]:
        records = self._records
        if context is not None and context.variant is FedoraVariant.ATOMIC:
            # Flatpak-first ordering keeps the low-friction path visible first.
            records = tuple(
                sorted(records, key=lambda item: (item.source != "flatpak", item.category, item.name.casefold()))
            )
        return records

    def get(self, application_id: str) -> ApplicationRecord | None:
        return self._by_id.get(str(application_id).strip())

    def categories(self) -> tuple[str, ...]:
        return tuple(sorted({item.category for item in self._records}, key=str.casefold))

    def search(
        self,
        query: str = "",
        *,
        category: str | None = None,
        context: ApplicationContext | None = None,
        include_installed: bool = True,
    ) -> tuple[tuple[ApplicationRecord, ApplicationEligibility], ...]:
        normalized = " ".join(str(query or "").casefold().split())
        category_key = str(category or "").casefold().strip()
        results: list[tuple[ApplicationRecord, ApplicationEligibility]] = []
        for record in self.all(context=context):
            if normalized and not all(token in record.search_text for token in normalized.split()):
                continue
            if category_key and record.category.casefold() != category_key:
                continue
            eligibility = self.eligibility(record, context)
            if not include_installed and eligibility.installed:
                continue
            results.append((record, eligibility))
        return tuple(results)

    def eligibility(
        self,
        application: ApplicationRecord | str,
        context: ApplicationContext | None = None,
    ) -> ApplicationEligibility:
        record = application if isinstance(application, ApplicationRecord) else self.get(str(application))
        if record is None:
            raise KeyError(f"Unknown application: {application}")
        if context is None:
            return ApplicationEligibility(record, "available", "Ready for review.")
        if record.id in context.installed_ids or record.package_id in context.installed_ids:
            return ApplicationEligibility(record, "installed", "Already installed.")
        if context.online is False:
            return ApplicationEligibility(record, "offline", "An online connection is required to install this application.")
        if context.variant is FedoraVariant.UNKNOWN:
            return ApplicationEligibility(record, "unavailable", "The Fedora deployment type is unknown; installation is fail-closed.")
        if record.source == "fedora" and context.variant is FedoraVariant.ATOMIC:
            return ApplicationEligibility(
                record,
                "advanced",
                "RPM layering creates a new Atomic deployment and may require a reboot.",
                advanced=True,
                requires_reboot=True,
            )
        if record.source == "fedora" and "dnf5" not in context.capabilities and context.variant is FedoraVariant.TRADITIONAL:
            return ApplicationEligibility(record, "unavailable", "Fedora RPM installation needs the supported dnf5 capability.")
        return ApplicationEligibility(record, "available", "Ready for review.")

    def build_selection(
        self,
        application_ids: Iterable[str],
        *,
        context: ApplicationContext,
        title: str = "Install selected applications",
    ) -> InstallSelection:
        ids = tuple(str(item).strip() for item in application_ids if str(item).strip())
        if not ids:
            raise ValueError("Select at least one application.")
        if not isinstance(context, ApplicationContext):
            raise ValueError("A verified ApplicationContext is required before building an install bundle.")
        if context.variant is FedoraVariant.UNKNOWN:
            raise ValueError("Fedora deployment backend is unknown; installation is fail-closed.")
        if len(ids) != len(set(ids)):
            raise ValueError("An application can only be selected once.")
        records: list[ApplicationRecord] = []
        for application_id in ids:
            record = self.get(application_id)
            if record is None:
                raise ValueError(f"Unknown application: {application_id}")
            eligibility = self.eligibility(record, context)
            if not eligibility.selectable:
                raise ValueError(f"{record.name} is not available: {eligibility.reason}")
            records.append(record)
        items = tuple(
            ActionBundleItem(
                action_id="install-application",
                parameters={"source": record.source, "package_id": record.package_id},
                title=record.name,
                metadata={
                    "application_id": record.id,
                    "source": record.source,
                    "source_label": record.source_label,
                    "requires_reboot_on_atomic": record.requires_reboot_on_atomic,
                },
            )
            for record in records
        )
        bundle = ActionBundle.applications(
            items,
            title=title,
            description="Review the exact source and identifier for every application before installing.",
            metadata={
                "catalog": "curated-v29",
                "variant": context.variant.value,
                "application_ids": [record.id for record in records],
            },
        )
        return InstallSelection(tuple(records), context, bundle)


def curated_applications() -> tuple[ApplicationRecord, ...]:
    """Return the immutable default catalog for documentation and tests."""

    return ApplicationCatalog().all()


def build_install_bundle(
    application_ids: Iterable[str],
    *,
    context: ApplicationContext,
    catalog: ApplicationCatalog | None = None,
    title: str = "Install selected applications",
) -> ActionBundle:
    """Build a reviewed independent-install bundle without executing it."""

    return (catalog or ApplicationCatalog()).build_selection(application_ids, context=context, title=title).bundle


__all__ = [
    "ApplicationCatalog",
    "ApplicationContext",
    "ApplicationEligibility",
    "ApplicationRecord",
    "ApplicationSource",
    "ApplicationState",
    "InstallSelection",
    "build_install_bundle",
    "curated_applications",
]
