"""Bounded source setup helper with pinned trust and conflict-safe writes."""
from __future__ import annotations

import base64
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import urllib.request

try:
    from gi.repository import GLib
except ImportError:
    _GLIB_ERRORS: tuple[type[Exception], ...] = ()
else:
    _GLIB_ERRORS = (GLib.Error,)

try:
    import rpm
except ImportError:
    _RPM_ERRORS: tuple[type[Exception], ...] = ()
else:
    _RPM_ERRORS = (rpm.error,)

from core.fedora_release_policy import FEDORA_RELEASE_POLICY
from services.software.setup_sources import DEFINITION_VERSION, SOURCES, SourcePreview, source_digest, validate_helper_args
from services.system.system import SystemManager

REPO_DIR = Path("/etc/yum.repos.d")
KEY_DIR = Path("/etc/pki/rpm-gpg")
MAX_FILE_BYTES = 128 * 1024
_SOURCE_ERRORS: tuple[type[Exception], ...] = (
    ImportError, OSError, ValueError, RuntimeError, TypeError, AttributeError, KeyError, IndexError,
    subprocess.SubprocessError, configparser.Error,
) + _GLIB_ERRORS + _RPM_ERRORS


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Source configuration is unavailable or exceeds its safe limit.")
    return path.read_bytes()


def _fingerprints(key: bytes) -> tuple[str, ...]:
    with tempfile.TemporaryDirectory(prefix="loofi-source-key-") as directory:
        key_path = Path(directory) / "key"
        key_path.write_bytes(key)
        result = subprocess.run(["/usr/bin/gpg", "--batch", "--no-options", "--homedir", directory,
                                 "--with-colons", "--show-keys", str(key_path)], capture_output=True, timeout=10, check=False)
        if result.returncode or len(result.stdout) > MAX_FILE_BYTES:
            raise ValueError("The source signing key could not be inspected.")
        return tuple(line.split(":")[9] for line in result.stdout.decode().splitlines() if line.startswith("fpr:"))


def _fetch(url: str) -> bytes:
    # URLs are supplied exclusively by the immutable source registry.
    with urllib.request.urlopen(url, timeout=20) as response:
        if response.geturl() != url:
            raise ValueError("The source endpoint redirected; its trust definition requires review.")
        data = bytes(response.read(MAX_FILE_BYTES + 1))
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("The source response exceeds the safe size limit.")
    return data


def _key(source_id: str) -> bytes:
    definition = SOURCES[source_id]
    key = _fetch(definition.key_url)
    if source_id == "flathub":
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(key.decode())
        if parser["Flatpak Repo"]["Url"] != definition.url:
            raise ValueError("The Flathub repository URL has changed.")
        key = base64.b64decode(parser["Flatpak Repo"]["GPGKey"], validate=True)
    if hashlib.sha256(key).hexdigest() != definition.key_sha256 or _fingerprints(key) != definition.fingerprints:
        raise ValueError("The source signing key differs from the reviewed trust definition.")
    return key


def _rpm_configuration(source_id: str) -> str:
    kind = source_id.removeprefix("rpmfusion-")
    key = f"file://{KEY_DIR}/RPM-GPG-KEY-loofi-{source_id}"
    return "\n".join(
        f"[{source_id}{suffix}]\nname=RPM Fusion for Fedora - {kind}{label}\n"
        f"metalink=https://mirrors.rpmfusion.org/metalink?repo={kind}-fedora{repo_suffix}-$releasever&arch=$basearch\n"
        f"enabled=1\ngpgcheck=1\ngpgkey={key}\nsslverify=1\n"
        for suffix, label, repo_suffix in (("", "", ""), ("-updates", " - Updates", "-updates-released"))
    )


def _normalize_variables(value: str) -> str:
    """Accept the two documented spellings of known DNF variables only."""
    return value.replace("${releasever}", "$releasever").replace("${basearch}", "$basearch")


def _rpm_key_imported(source_id: str) -> bool:
    import rpm

    definition = SOURCES[source_id]
    matches = rpm.TransactionSet().dbMatch("name", "gpg-pubkey")
    for index, header in enumerate(matches):
        if index >= 256:
            raise ValueError("Too many RPM signing keys to inspect safely.")
        version = str(header["version"]).upper()
        if version not in {definition.fingerprints[0], definition.fingerprints[0][-8:]}:
            continue
        key = str(header["description"]).encode()
        if len(key) > MAX_FILE_BYTES:
            raise ValueError("RPM signing key evidence exceeds the safe limit.")
        if _fingerprints(key) == definition.fingerprints:
            return True
    return False


def _rpm_state(source_id: str) -> tuple[str, dict[str, Any]]:
    if SystemManager.is_atomic() or SystemManager.get_package_manager() != "dnf5":
        raise ValueError("This source setup requires traditional Fedora with DNF5.")
    release = str(SystemManager.get_platform_profile().fedora_version)
    if not FEDORA_RELEASE_POLICY.is_supported_version(release):
        raise ValueError("Source setup is unavailable for this Fedora release.")
    files = sorted(REPO_DIR.glob("*.repo"))
    if len(files) > 128:
        raise ValueError("Too many source configuration files to inspect safely.")
    wanted = {source_id, f"{source_id}-updates"}
    matches: dict[str, dict[str, str]] = {}
    hashes: dict[str, str] = {}
    conflict = False
    for path in files:
        data = _read(path)
        hashes[path.name] = hashlib.sha256(data).hexdigest()
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(data.decode())
        for section in wanted.intersection(parser.sections()):
            if section in matches:
                conflict = True
            matches[section] = dict(parser[section])
    own_path = REPO_DIR / f"loofi-{source_id}.repo"
    if own_path.is_symlink() or (own_path.exists() and _read(own_path) != _rpm_configuration(source_id).encode()):
        conflict = True
    keys: dict[str, str] = {}
    for section, values in matches.items():
        kind = source_id.removeprefix("rpmfusion-")
        repo_suffix = "-updates-released" if section.endswith("-updates") else ""
        expected_metalink = f"https://mirrors.rpmfusion.org/metalink?repo={kind}-fedora{repo_suffix}-$releasever&arch=$basearch"
        if (_normalize_variables(values.get("metalink", "")) != expected_metalink or values.get("enabled", "1") != "1"
                or values.get("gpgcheck") != "1" or values.get("sslverify", "1") != "1"
                or values.get("baseurl") or values.get("mirrorlist")):
            conflict = True
        key_url = _normalize_variables(values.get("gpgkey", "")).replace("$releasever", release)
        if not key_url.startswith(f"file://{KEY_DIR}/") or "\n" in key_url or " " in key_url:
            conflict = True
            continue
        key_path = Path(key_url.removeprefix("file://"))
        # Distribution-managed key symlinks are allowed only inside the key directory.
        resolved = key_path.resolve()
        if KEY_DIR.resolve() not in resolved.parents or not resolved.is_file():
            conflict = True
            continue
        key_data = _read(resolved)
        keys[str(key_path)] = hashlib.sha256(key_data).hexdigest()
        if keys[str(key_path)] != SOURCES[source_id].key_sha256:
            conflict = True
    own_key = KEY_DIR / f"RPM-GPG-KEY-loofi-{source_id}"
    if own_key.exists() or own_key.is_symlink():
        if own_key.is_symlink() or hashlib.sha256(_read(own_key)).hexdigest() != SOURCES[source_id].key_sha256:
            conflict = True
        else:
            keys[str(own_key)] = SOURCES[source_id].key_sha256
    imported = _rpm_key_imported(source_id)
    state = "conflict" if conflict or (matches and set(matches) != wanted) else "enabled" if matches and imported else "key_import_required" if matches else "absent"
    return state, {"release": release, "configuration": hashes, "keys": keys, "rpm_key_imported": imported}


def _flatpak_installation(scope: str):
    import gi

    gi.require_version("Flatpak", "1.0")
    from gi.repository import Flatpak

    return Flatpak.Installation.new_user(None) if scope == "user" else Flatpak.Installation.new_system(None)


def _flatpak_state(scope: str) -> tuple[str, dict[str, Any]]:
    # Even Flatpak.Installation.new_user() creates an OSTree repository. Check
    # its fixed default location first so an inspection never initializes it.
    if scope == "user":
        data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        root = Path(os.environ.get("FLATPAK_USER_DIR") or data_home / "flatpak")
    else:
        root = Path(os.environ.get("FLATPAK_SYSTEM_DIR") or "/var/lib/flatpak")
    configuration = root / "repo" / "config"
    if not configuration.exists() and not configuration.is_symlink():
        return "absent", {"remotes": []}
    _read(configuration)
    installation = _flatpak_installation(scope)
    remotes = installation.list_remotes(None)
    if len(remotes) > 128:
        raise ValueError("Too many Flatpak sources to inspect safely.")
    remote = next((item for item in remotes if item.get_name() == "flathub"), None)
    if remote is None:
        return "absent", {"remotes": sorted(item.get_name() for item in remotes)}
    path = Path(installation.get_path().get_path()) / "repo" / "flathub.trustedkeys.gpg"
    key = _read(path)
    state = "enabled" if (remote.get_url() == SOURCES["flathub"].url and remote.get_gpg_verify()
                          and not remote.get_disabled() and _fingerprints(key) == SOURCES["flathub"].fingerprints) else "conflict"
    return state, {"url": remote.get_url(), "gpg_verify": remote.get_gpg_verify(), "disabled": remote.get_disabled(),
                   "key_digest": hashlib.sha256(key).hexdigest()}


def inspect_source(source_id: str, scope: str) -> SourcePreview:
    try:
        state, facts = _flatpak_state(scope) if source_id == "flathub" else _rpm_state(source_id)
        evidence = {"source_id": source_id, "scope": scope, "definition_version": DEFINITION_VERSION, "state": state, **facts}
        return SourcePreview(source_id, scope, state in {"absent", "enabled", "key_import_required"}, state, source_digest(evidence),
                             "Existing source configuration conflicts with this definition; inspect it explicitly." if state == "conflict" else "", evidence)
    except _SOURCE_ERRORS:
        evidence = {"source_id": source_id, "scope": scope, "definition_version": DEFINITION_VERSION, "state": "unknown"}
        return SourcePreview(source_id, scope, False, "unknown", source_digest(evidence),
                             "Source configuration or signing evidence could not be inspected.", evidence)


def _exclusive_write(path: Path, data: bytes) -> None:
    # A hard link publishes a complete same-filesystem file atomically and
    # refuses existing destinations, including symlinks.
    descriptor, temporary_name = tempfile.mkstemp(prefix=".loofi-source-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fchmod(handle.fileno(), 0o644)
            os.fsync(handle.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def apply_source(source_id: str, scope: str, digest: str) -> SourcePreview:
    if (scope == "system") != (os.geteuid() == 0):
        raise ValueError("System setup needs the installed elevated helper; user setup must use the invoking user.")
    key = _key(source_id)
    lock_path = Path("/run/loofi-setup-sources.lock") if scope == "system" else Path(_flatpak_installation(scope).get_path().get_path()) / ".loofi-source-setup.lock"
    # The user installation normally exists. No directory is created during preview.
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = inspect_source(source_id, scope)
        if not current.available or current.state not in {"absent", "key_import_required"} or current.digest != digest:
            raise ValueError("Source configuration changed after review; create a fresh review.")
        if source_id == "flathub":
            from gi.repository import Flatpak, GLib

            remote = Flatpak.Remote.new("flathub")
            remote.set_url(SOURCES[source_id].url)
            remote.set_gpg_verify(True)
            remote.set_gpg_key(GLib.Bytes.new(key))
            _flatpak_installation(scope).modify_remote(remote, None)
        else:
            key_path = KEY_DIR / f"RPM-GPG-KEY-loofi-{source_id}"
            if not key_path.exists():
                _exclusive_write(key_path, key)
            # Only the pinned key at our fixed root-owned path can be imported.
            imported = subprocess.run(["/usr/bin/rpmkeys", "--import", str(key_path)], capture_output=True, timeout=20, check=False)
            if imported.returncode or not _rpm_key_imported(source_id):
                raise ValueError("The pinned RPM signing key import could not be verified.")
            if current.state == "absent":
                _exclusive_write(REPO_DIR / f"loofi-{source_id}.repo", _rpm_configuration(source_id).encode())
        result = inspect_source(source_id, scope)
        if not result.available or result.state != "enabled":
            raise ValueError("Source setup finished without verified configuration; inspect the recorded result.")
        return result


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not validate_helper_args(args):
        print(json.dumps({"available": False, "error": "Invalid source setup command."}))
        return 2
    mode, source_id, scope = args[0], args[2], args[4]
    try:
        result = apply_source(source_id, scope, args[6]) if mode == "apply" else inspect_source(source_id, scope)
        print(json.dumps(result.to_dict(), sort_keys=True))
        return 0 if result.available else 1
    except _SOURCE_ERRORS:
        # Never expose request-controlled files, credentials or remote response bodies.
        print(json.dumps({"available": False, "error": "Source setup could not be verified. Inspect configuration and create a fresh review."}))
        return 1
