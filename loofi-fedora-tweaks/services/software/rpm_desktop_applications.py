"""Bounded read-only discovery of RPM-owned desktop application entries."""
from __future__ import annotations

import configparser
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from core.executor.action_result import ActionResult

MAX_FILES = 1024
MAX_DIRECTORIES = 128
MAX_FILE_BYTES = 64 * 1024
MAX_QUERY_BYTES = 4 * 1024 * 1024
BATCH_SIZE = 32


@dataclass(frozen=True)
class DesktopApplications:
    names: dict[str, str]
    errors: tuple[str, ...] = ()


class _DesktopParser(configparser.ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


def desktop_name(data: str, *, desktop: str, locale: str) -> str | None:
    """Interpret menu visibility without evaluating Exec, TryExec, or DBus keys."""
    parser = _DesktopParser(interpolation=None, strict=True)
    parser.read_string(data)
    entry = parser["Desktop Entry"]
    if entry.get("Type") != "Application":
        return None
    if entry.getboolean("Hidden", fallback=False) or entry.getboolean("NoDisplay", fallback=False):
        return None
    desktops = set(desktop.casefold().split(":")) - {""}
    only = set(entry.get("OnlyShowIn", "").casefold().strip(";").split(";")) - {""}
    excluded = set(entry.get("NotShowIn", "").casefold().strip(";").split(";")) - {""}
    if (only and not only.intersection(desktops)) or excluded.intersection(desktops):
        return None
    raw_base, _, modifier = locale.partition("@")
    base = raw_base.split(".", 1)[0]
    language = base + ("@" + modifier if modifier else "")
    candidates = [language, base]
    short = base.split("_", 1)[0]
    if modifier:
        candidates.append(short + "@" + modifier)
    candidates.append(short)
    name = next((entry[f"Name[{key}]"] for key in candidates if f"Name[{key}]" in entry), entry.get("Name", ""))
    escapes = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
    if re.search(r"\\(?:[^sntr\\]|$)", name):
        raise ValueError("Invalid desktop string escape.")
    name = re.sub(r"\\([sntr\\])", lambda match: escapes[match[1]], name).strip()
    if not name or len(name) > 512 or any(ord(char) < 32 for char in name):
        raise ValueError("Invalid desktop application name.")
    return name


def discover_rpm_desktop_applications(
    probe: Callable[[Sequence[str], float], ActionResult], *, deadline: float,
    roots: tuple[Path, ...] | None = None,
    clock: Callable[[], float] = time.monotonic, desktop: str | None = None, locale: str | None = None,
) -> DesktopApplications:
    """Resolve visible system entries in batches with a single elapsed-time budget."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "") if desktop is None else desktop
    locale = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG", "C")) if locale is None else locale
    roots = (Path("/usr/share/applications"), Path("/usr/local/share/applications")) if roots is None else roots
    entries: dict[str, str] = {}
    errors: list[str] = []
    directories = 0
    files_seen = 0
    limited = False
    for root in roots:
        def walk_error(_error: OSError) -> None:
            errors.append("Some desktop application directories could not be read.")

        for directory, subdirs, filenames in os.walk(root, followlinks=False, onerror=walk_error):
            subdirs.sort()
            directories += 1
            if directories > MAX_DIRECTORIES or clock() >= deadline:
                limited = True
                break
            for filename in sorted(filenames):
                if not filename.endswith(".desktop"):
                    continue
                files_seen += 1
                if files_seen > MAX_FILES or clock() >= deadline:
                    limited = True
                    break
                path = Path(directory) / filename
                try:
                    if path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
                        errors.append("Some desktop application files exceeded the safe inspection limits.")
                        continue
                    with path.open("rb") as stream:
                        data = stream.read(MAX_FILE_BYTES + 1)
                    if len(data) > MAX_FILE_BYTES:
                        raise ValueError("Desktop entry exceeds inspection limit.")
                    name = desktop_name(data.decode("utf-8"), desktop=desktop, locale=locale)
                    if name:
                        entries[str(path)] = name
                except (OSError, UnicodeError, ValueError, KeyError, configparser.Error):
                    errors.append("Some desktop application files could not be inspected.")
            if limited:
                break
        if limited:
            break
    if limited:
        errors.append("Desktop application inspection reached its time or file limit; results are partial.")
    names: dict[str, str] = {}
    paths = sorted(entries)
    for offset in range(0, len(paths), BATCH_SIZE):
        remaining = deadline - clock()
        if remaining <= 0:
            errors.append("RPM ownership inspection timed out; results are partial.")
            break
        batch = paths[offset:offset + BATCH_SIZE]
        # Include filenames in the response so failed/unowned inputs cannot
        # shift positional associations. No scriptlets or desktop commands run.
        result = probe(("rpm", "-qf", "--qf", "[%{FILENAMES}\\t%{=NAME}\\n]", "--", *batch), min(8.0, remaining))
        if len(result.stdout.encode("utf-8")) > MAX_QUERY_BYTES:
            errors.append("RPM ownership response exceeded the inspection limit; results are partial.")
            continue
        matched: set[str] = set()
        unowned: set[str] = set()
        for line in result.stdout.splitlines():
            unowned_match = re.fullmatch(r"file (.+) is not owned by any package", line)
            if unowned_match and unowned_match[1] in batch:
                unowned.add(unowned_match[1])
                continue
            fields = line.split("\t")
            if len(fields) != 2:
                continue
            owner_path, package = fields
            if owner_path not in batch or not package or len(package) > 255 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._+-" for char in package):
                continue
            # First visible desktop filename wins deterministically per package.
            names.setdefault(package, entries[owner_path])
            matched.add(owner_path)
        accounted = matched | unowned
        if accounted != set(batch) or (not result.success and result.exit_code != 1):
            errors.append("Some RPM desktop file owners could not be read; results are partial.")
    return DesktopApplications(names, tuple(dict.fromkeys(errors)))
