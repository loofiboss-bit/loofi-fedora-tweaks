"""Closed, versioned source trust definitions and reviewed setup client.

Trust anchors were read from the official RPM Fusion key endpoints and Flathub
repository descriptor. Changing a key requires a reviewed definition update.
Search and preview never fetch repository metadata or import signing keys.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFINITION_VERSION = 1
MAX_OUTPUT = 128 * 1024
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
INSTALLED_HELPER = "/usr/bin/loofi-setup-sources"
CODEC_PACKAGES = ("ffmpeg", "gstreamer1-plugins-bad-freeworld", "gstreamer1-plugins-ugly")


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    title: str
    provider: str
    url: str
    key_sha256: str
    fingerprints: tuple[str, ...]
    scopes: tuple[str, ...]
    key_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "fingerprints": list(self.fingerprints), "scopes": list(self.scopes), "definition_version": DEFINITION_VERSION}


SOURCES = {
    "flathub": SourceDefinition(
        "flathub", "Flathub", "Flathub", "https://dl.flathub.org/repo/",
        "8bdc20abc4e19c0796460beb5bfe0e7aa4138716999e19c6f2dbdd78cc41aeaa",
        ("6E5C05D979C76DAF93C081354184DD4D907A7CAE", "54A6CDDD8919FB204200D8AC562702E9E3ED7EE8"),
        ("user", "system"), "https://dl.flathub.org/repo/flathub.flatpakrepo"),
    "rpmfusion-free": SourceDefinition(
        "rpmfusion-free", "RPM Fusion Free", "RPM Fusion", "https://mirrors.rpmfusion.org/",
        "10fc0a3e1a0307e8088357a31a9c5e4e3d9f9e0b01db2b03b5790d949a47f3b3",
        ("E9A491A3DE247814E7E067EAE06F8ECDD651FF2E",), ("system",),
        "https://download1.rpmfusion.org/free/fedora/RPM-GPG-KEY-rpmfusion-free-fedora-2020"),
    "rpmfusion-nonfree": SourceDefinition(
        "rpmfusion-nonfree", "RPM Fusion Nonfree", "RPM Fusion", "https://mirrors.rpmfusion.org/",
        "7ac65a8dfeced70c8c335862b5f0696d57abac378deda34c4af78cd2220e3de6",
        ("79BDB88F9BBF73910FD4095B6A2AF96194843C65",), ("system",),
        "https://download1.rpmfusion.org/nonfree/fedora/RPM-GPG-KEY-rpmfusion-nonfree-fedora-2020"),
}


def trusted_helpers() -> tuple[str, ...]:
    return (INSTALLED_HELPER, str(Path(__file__).resolve().parents[3] / "scripts" / "loofi-setup-sources"))


def helper_command() -> str:
    return next((path for path in trusted_helpers() if Path(path).is_file()), INSTALLED_HELPER)


def validate_helper_args(args: Sequence[str]) -> bool:
    values = list(args)
    if len(values) not in {5, 7} or any(not isinstance(value, str) for value in values):
        return False
    mode, source, scope = values[0], values[2], values[4]
    if values[1] != "--source-id" or values[3] != "--scope" or source not in SOURCES or scope not in SOURCES[source].scopes:
        return False
    if mode in {"preview", "state"}:
        return len(values) == 5
    return mode == "apply" and len(values) == 7 and values[5] == "--snapshot-digest" and bool(DIGEST_PATTERN.fullmatch(values[6]))


def source_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class SourcePreview:
    source_id: str
    scope: str
    available: bool
    state: str
    digest: str = ""
    error: str = ""
    evidence: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "evidence_version": DEFINITION_VERSION, "definition": SOURCES[self.source_id].to_dict()}

    def apply_vector(self) -> list[str]:
        if not self.available or self.state not in {"absent", "key_import_required"} or not DIGEST_PATTERN.fullmatch(self.digest):
            raise ValueError("A fresh available source review is required.")
        command = INSTALLED_HELPER if self.scope == "system" else helper_command()
        return [command, "apply", "--source-id", self.source_id, "--scope", self.scope, "--snapshot-digest", self.digest]


def preview_from_facts(value: Any) -> SourcePreview:
    if not isinstance(value, Mapping) or value.get("evidence_version") != DEFINITION_VERSION:
        raise ValueError("Legacy source evidence requires a fresh review.")
    source, scope = value.get("source_id"), value.get("scope")
    if not isinstance(source, str) or source not in SOURCES or scope not in SOURCES[source].scopes or value.get("definition") != SOURCES[source].to_dict():
        raise ValueError("Source trust definition has changed; review again.")
    evidence, digest = value.get("evidence"), value.get("digest")
    if not isinstance(evidence, Mapping) or source_digest(evidence) != digest:
        raise ValueError("Source review evidence is invalid.")
    if (evidence.get("source_id") != source or evidence.get("scope") != scope
            or evidence.get("definition_version") != DEFINITION_VERSION or evidence.get("state") != value.get("state")):
        raise ValueError("Source review identity is invalid.")
    return SourcePreview(source, scope, value.get("available") is True, str(value.get("state")), str(digest), str(value.get("error", "")), dict(evidence))


class SetupSourceService:
    """Read-only helper client; mutations are rendered for OperationController."""

    def preview(self, source_id: str, scope: str) -> SourcePreview:
        args = ["preview", "--source-id", source_id, "--scope", scope]
        if not validate_helper_args(args):
            raise ValueError("Select an approved source and installation scope.")
        from services.software.installed_applications import InstalledApplicationService

        try:
            result = InstalledApplicationService._probe([helper_command(), *args], timeout=25)
            if not result.success or len(result.stdout) > MAX_OUTPUT:
                raise ValueError("Source inspection is unavailable.")
            preview = preview_from_facts(json.loads(result.stdout))
            if (preview.source_id, preview.scope) != (source_id, scope):
                raise ValueError("The source inspection returned a different source or scope.")
            return preview
        except (OSError, ValueError, TypeError):
            return SourcePreview(source_id, scope, False, "unknown", error="Source inspection is unavailable; inspect configuration before trying again.")
