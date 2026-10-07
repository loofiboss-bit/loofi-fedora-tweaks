"""Bounded, Qt-free client for local libflatpak maintenance evidence."""
from __future__ import annotations

import hashlib
import io
import json
import re
import selectors
import subprocess
import sysconfig
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence, cast

MAX_OUTPUT = 1024 * 1024
INSPECTION_TIMEOUT = 15
INSTALLATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
REF_PATTERN = re.compile(r"^(app|runtime)/[A-Za-z0-9][A-Za-z0-9._-]{1,255}/[A-Za-z0-9_-]+/[A-Za-z0-9._-]+$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_HELPER_ERRORS = frozenset({
    "Invalid maintenance command.",
    "Cleanup must use the invoking user and native Flatpak authorization.",
    "Local Flatpak support is unavailable. Optional PyGObject and libflatpak are required.",
    "The selected Flatpak installation could not be inspected.",
    "The selected ref is not installed in this installation.",
    "Flatpak evidence exceeded the output limit.",
})


def _safe_helper_error(value: Any) -> str:
    return value if isinstance(value, str) and value in _HELPER_ERRORS else "Local Flatpak inspection is unavailable."


def trusted_helpers() -> tuple[str, ...]:
    source = Path(__file__).resolve().parents[3] / "scripts" / "loofi-flatpak-maintenance"
    return tuple(dict.fromkeys((str(source), "/usr/bin/loofi-flatpak-maintenance", str(Path(sysconfig.get_path("scripts")) / "loofi-flatpak-maintenance"))))


def helper_command() -> str:
    return next((path for path in trusted_helpers() if Path(path).is_file()), "/usr/bin/loofi-flatpak-maintenance")


def validate_helper_args(args: Sequence[str]) -> bool:
    """Accept only closed helper modes; never paths, arbitrary options or code."""
    args = list(args)
    if len(args) > 517 or any(not isinstance(arg, str) or len(arg) > 512 for arg in args):
        return False
    if args == ["installations"]:
        return True
    if len(args) < 3 or args[1] != "--installation" or not INSTALLATION_PATTERN.fullmatch(args[2]):
        return False
    if args[0] == "unused":
        return len(args) == 3
    if args[0] == "details":
        return len(args) == 5 and args[3] == "--ref" and bool(REF_PATTERN.fullmatch(args[4]))
    if args[0] != "apply" or len(args) < 7 or args[3] != "--snapshot-digest" or not DIGEST_PATTERN.fullmatch(args[4]):
        return False
    refs = args[6::2]
    return (len(args) % 2 == 1 and len(refs) <= 256 and len(set(refs)) == len(refs)
            and all(args[index] == "--ref" for index in range(5, len(args), 2))
            and all(REF_PATTERN.fullmatch(ref) and ref.startswith("runtime/") for ref in refs))


def snapshot_digest(installation: str, installed: Sequence[dict[str, Any]], unused: Sequence[dict[str, Any]], pins: Sequence[str], dependency_digest: str = "") -> str:
    payload = {"installation": installation, "installed": sorted(installed, key=lambda item: item["ref"]),
               "refs": sorted(unused, key=lambda item: item["ref"]), "pins": sorted(pins)}
    if dependency_digest:
        payload["dependency_digest"] = dependency_digest
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class RefRecord:
    ref: str
    commit: str
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UnusedSnapshot:
    installation: str
    available: bool = False
    error: str = ""
    warning: str = ""
    refs: tuple[RefRecord, ...] = ()
    installed: tuple[RefRecord, ...] = ()
    pins: tuple[str, ...] = ()
    digest: str = ""
    dependency_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FlatpakDetails:
    ref: str
    installation: str
    available: bool = False
    error: str = ""
    name: str = ""
    version: str = ""
    origin: str = ""
    runtime: str = ""
    size_bytes: int | None = None
    eol: str = ""
    eol_rebase: str = ""
    runtime_eol: str = ""
    runtime_eol_rebase: str = ""
    runtime_missing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FlatpakMaintenanceService:
    def __init__(self, *, probe: Callable[[Sequence[str]], dict[str, Any]] | None = None) -> None:
        self.probe = probe or self._probe

    @staticmethod
    def _probe(vector: Sequence[str]) -> dict[str, Any]:
        # Read incrementally: communicate() would accumulate an unbounded child output.
        process = None
        try:
            process = subprocess.Popen(list(vector), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            assert process.stdout is not None
            deadline = time.monotonic() + INSPECTION_TIMEOUT
            output = bytearray()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    for key, _ in selector.select(remaining):
                        chunk = cast(io.BufferedReader, process.stdout).read1(65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        output.extend(chunk)
                        if len(output) > MAX_OUTPUT:
                            raise ValueError("Flatpak inspection exceeded the output limit.")
            process.wait(timeout=max(0.01, deadline - time.monotonic()))
            payload = json.loads(output)
            if not isinstance(payload, dict):
                raise ValueError("Invalid Flatpak inspection response.")
            if process.returncode != 0:
                if payload.get("available") is False:
                    return {"available": False, "error": _safe_helper_error(payload.get("error"))}
                return {"available": False, "error": "Local Flatpak inspection could not complete."}
            return payload
        except (OSError, TimeoutError, subprocess.TimeoutExpired, ValueError):
            return {"available": False, "error": "Local Flatpak inspection is unavailable or exceeded its limits."}
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=2)
                if process.stdout is not None:
                    process.stdout.close()

    def installations(self) -> tuple[str, ...]:
        payload = self.probe((helper_command(), "installations"))
        values = payload.get("installations", [])
        if not payload.get("available") or not isinstance(values, list) or any(not isinstance(item, str) or not INSTALLATION_PATTERN.fullmatch(item) for item in values):
            return ()
        return tuple(values)

    def details(self, ref: str, installation: str = "user") -> FlatpakDetails:
        args = ["details", "--installation", installation, "--ref", ref]
        if not validate_helper_args(args):
            return FlatpakDetails(ref, installation, error="Invalid Flatpak identity.")
        payload = self.probe((helper_command(), *args))
        if not payload.get("available"):
            return FlatpakDetails(ref, installation, error=_safe_helper_error(payload.get("error")))
        fields = {name: payload.get(name, field.default) for name, field in FlatpakDetails.__dataclass_fields__.items() if name not in {"ref", "installation"}}
        if payload.get("ref") != ref or payload.get("installation") != installation:
            return FlatpakDetails(ref, installation, error="Invalid Flatpak detail identity.")
        strings = ("name", "version", "origin", "runtime", "eol", "eol_rebase", "runtime_eol", "runtime_eol_rebase", "error")
        if any(not isinstance(fields[key], str) or len(fields[key]) > 1024 or any(ord(char) < 32 or ord(char) == 127 for char in fields[key]) for key in strings):
            return FlatpakDetails(ref, installation, error="Invalid Flatpak detail evidence.")
        size = fields["size_bytes"]
        if (size is not None and (type(size) is not int or size < 0)) or type(fields["runtime_missing"]) is not bool:
            return FlatpakDetails(ref, installation, error="Invalid Flatpak detail evidence.")
        if (fields["origin"] and not INSTALLATION_PATTERN.fullmatch(fields["origin"])) or (fields["runtime"] and not REF_PATTERN.fullmatch(fields["runtime"])):
            return FlatpakDetails(ref, installation, error="Invalid Flatpak source or runtime evidence.")
        return FlatpakDetails(ref, installation, **fields)

    def unused(self, installation: str = "user") -> UnusedSnapshot:
        args = ["unused", "--installation", installation]
        if not validate_helper_args(args):
            return UnusedSnapshot(installation, error="Invalid Flatpak installation.")
        payload = self.probe((helper_command(), *args))
        warning = "This installation is shared. Other users' private application inventories are not inspected." if installation != "user" else ""
        if not payload.get("available"):
            return UnusedSnapshot(installation, error=_safe_helper_error(payload.get("error")), warning=warning)
        try:
            if not payload.get("available") or payload.get("installation") != installation:
                raise ValueError(str(payload.get("error", "Flatpak inspection is unavailable.")))

            def records(key: str) -> tuple[RefRecord, ...]:
                values = tuple(RefRecord(**record) for record in payload[key])
                if any(not REF_PATTERN.fullmatch(item.ref) or not DIGEST_PATTERN.fullmatch(item.commit)
                       or (item.size_bytes is not None and (type(item.size_bytes) is not int or item.size_bytes < 0)) for item in values):
                    raise ValueError("Invalid Flatpak ref evidence.")
                if len({item.ref for item in values}) != len(values):
                    raise ValueError("Duplicate Flatpak evidence.")
                return values
            installed, refs = records("installed"), records("refs")
            pins = tuple(payload["pins"])
            if any(not isinstance(pin, str) or len(pin) > 512 for pin in pins) or any(not item.ref.startswith("runtime/") for item in refs):
                raise ValueError("Invalid Flatpak unused evidence.")
            dependencies = payload.get("dependency_digest", "")
            if not isinstance(dependencies, str) or (dependencies and not DIGEST_PATTERN.fullmatch(dependencies)) or (installation != "user" and not dependencies):
                raise ValueError("Shared Flatpak dependency evidence is unavailable.")
            digest = snapshot_digest(installation, [item.to_dict() for item in installed], [item.to_dict() for item in refs], pins, dependencies)
            if payload["digest"] != digest or not set(refs).issubset(set(installed)):
                raise ValueError("Inconsistent Flatpak snapshot.")
            return UnusedSnapshot(installation, True, warning=warning, refs=refs, installed=installed, pins=pins, digest=digest, dependency_digest=dependencies)
        except (ValueError, KeyError, TypeError):
            return UnusedSnapshot(installation, error="Local Flatpak unused evidence is unavailable or invalid.", warning=warning)
