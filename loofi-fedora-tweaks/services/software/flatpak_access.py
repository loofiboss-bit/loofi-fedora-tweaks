"""Bounded, read-only Flatpak declarations and override layers, never runtime grants."""
from __future__ import annotations

import configparser
import re
import subprocess
import time
from typing import Callable, Sequence

from core.executor.action_result import ActionResult
from core.privacy import redact_text
from dataclasses import asdict, dataclass

from services.software.installed_applications import InstalledApplicationService, Probe, installation_flag, validate_ref

NOTICE = ("Declarations and overrides are observations, not effective runtime access. Desktop portals and launch flags can change access. "
          "Overrides apply to the application ID and may affect multiple branches. Shared installations also use the current user's overrides.")
MAX_OUTPUT = 65536


@dataclass(frozen=True)
class AccessEntry:
    category: str
    key: str
    value: str
    explanation: str


@dataclass(frozen=True)
class AccessLayer:
    kind: str
    installation: str
    status: str
    entries: tuple[AccessEntry, ...] = ()
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FlatpakAccessReport:
    ref: str
    installation: str
    app_id: str = ""
    status: str = "unavailable"
    layers: tuple[AccessLayer, ...] = ()
    error: str = ""
    notice: str = NOTICE

    def to_dict(self) -> dict[str, object]:
        return {"schema": "loofi.flatpak-access/v1", **asdict(self)}


class _PermissionParser(configparser.ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


def parse_access(output: str) -> tuple[AccessEntry, ...]:
    """Discard private values before constructing any report or summary."""
    if len(output.encode("utf-8")) > MAX_OUTPUT:
        raise ValueError("Permission output exceeds the limit.")
    parser = _PermissionParser(interpolation=None, strict=True)
    parser.read_string(output)
    entries: list[AccessEntry] = []
    for section in parser.sections():
        if section not in {"Context", "Environment", "Session Bus Policy", "System Bus Policy"}:
            continue
        for key, raw in parser.items(section):
            if len(key) > 128 or any(ord(char) < 32 for char in key):
                raise ValueError("Invalid permission key.")
            if section == "Environment":
                entries.append(AccessEntry(section, "[hidden variable]", "[hidden]", "Environment values are hidden for privacy."))
                continue
            for value in raw.split(";"):
                if not value:
                    continue
                explanation = "Desktop service access." if "Bus" in section else "Desktop integration setting."
                shown = value
                if key == "filesystems":
                    # Only closed, standard folder tokens are safe to disclose.
                    token = value.lstrip("!").split(":", 1)[0]
                    known = {"home", "host", "host-os", "host-etc", "xdg-download", "xdg-documents", "xdg-pictures", "xdg-videos", "xdg-music", "xdg-desktop", "xdg-public-share", "xdg-templates"}
                    if token not in known:
                        shown = "[private path hidden]"
                    explanation = "File access rule; a leading ! removes access, :ro is read-only."
                elif key == "shared" and value.lstrip("!") == "network":
                    explanation = "Network access rule; a leading ! removes access."
                elif key == "devices":
                    explanation = "Device access rule; a leading ! removes access."
                if section == "Context" and key != "filesystems" and not all(char.isalnum() or char in "!_-" for char in value):
                    shown = "[hidden]"
                if "Bus" in section and value not in {"talk", "own", "see", "none"}:
                    shown = "[hidden]"
                # Unknown values might carry paths or personal information.
                if section == "Context" and key not in {"filesystems", "shared", "sockets", "devices", "features"}:
                    shown = "[hidden]"
                safe_key = key
                if section == "Context" and key not in {"filesystems", "shared", "sockets", "devices", "features"}:
                    safe_key = "[hidden key]"
                if "Bus" in section and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)+(?:\.\*)?", key):
                    safe_key = "[hidden service]"
                entries.append(AccessEntry(section, redact_text(safe_key), redact_text(shown), explanation))
    return tuple(entries)


class FlatpakAccessService:
    def __init__(self, *, probe: Probe | None = None, inventory: InstalledApplicationService | None = None,
                 cancelled: Callable[[], bool] | None = None) -> None:
        self._probe = probe
        self._cancelled = cancelled or (lambda: False)
        self._deadline = 0.0
        self.probe = self._bounded_probe
        self.inventory = inventory or InstalledApplicationService(probe=self.probe)

    def _bounded_probe(self, vector: Sequence[str]) -> ActionResult:
        remaining = self._deadline - time.monotonic()
        if self._cancelled() or remaining <= 0:
            return ActionResult(False, "Inspection was stopped or exceeded its total time budget.")
        if self._probe is not None:
            result = self._probe(vector)
        else:
            try:
                observed = subprocess.run(list(vector), capture_output=True, text=True, timeout=min(3.0, remaining))
                result = ActionResult(observed.returncode == 0, "Local access read", stdout=observed.stdout)
            except (OSError, subprocess.SubprocessError):
                return ActionResult(False, "The local access layer could not be read.")
        if len(result.stdout.encode("utf-8")) > MAX_OUTPUT:
            return ActionResult(False, "The local response exceeds the limit.")
        return result

    def inspect(self, ref: str, installation: str) -> FlatpakAccessReport:
        self._deadline = time.monotonic() + 20.0
        try:
            flag = installation_flag(installation)
            if not validate_ref(ref):
                raise ValueError("Invalid ref.")
        except (ValueError, TypeError):
            return FlatpakAccessReport(ref="", installation="", error="Select a full application ref and valid installation.")
        snapshot = self.inventory.flatpaks()
        if snapshot.unknown_sources or not any(app.ref == ref and app.installation == installation for app in snapshot.applications):
            return FlatpakAccessReport(ref, installation, error="The exact installed application identity could not be confirmed.")
        app_id = ref.split("/")[1]
        vectors = [("declared", installation, ("flatpak", "info", flag, "--show-metadata", ref))]
        for scope in ((installation,) if installation == "user" else (installation, "user")):
            vectors.extend((kind, scope, ("flatpak", "override", installation_flag(scope), "--show", *tail))
                           for kind, tail in (("global-overrides", ()), ("app-overrides", (app_id,))))
        layers: list[AccessLayer] = []
        for kind, scope, vector in vectors:
            try:
                result = self.probe(vector)
                if not result.success or (kind == "declared" and not result.stdout.strip()):
                    raise ValueError("Probe failed.")
                entries = parse_access(result.stdout)
                layers.append(AccessLayer(kind, scope, "available", entries))
            except (OSError, RuntimeError, ValueError, configparser.Error):
                layers.append(AccessLayer(kind, scope, "unknown", error="This layer could not be read; absence of overrides is not established."))
        available = sum(layer.status == "available" for layer in layers)
        status = "available" if available == len(layers) else "partial" if available else "unavailable"
        return FlatpakAccessReport(ref, installation, app_id, status, tuple(layers))
