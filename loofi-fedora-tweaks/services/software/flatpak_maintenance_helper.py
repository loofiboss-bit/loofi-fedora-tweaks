"""Narrow libflatpak child process. Never run this helper as root."""
from __future__ import annotations

import configparser
import hashlib
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

from services.software.flatpak_maintenance import MAX_OUTPUT, REF_PATTERN, snapshot_digest, validate_helper_args

_EXPECTED_ERRORS: tuple[type[Exception], ...] = (OSError, RuntimeError, ValueError, TypeError, KeyError, configparser.Error)
_GLIB = None
_SAFE_ERROR_DOMAINS = {
    "flatpak-error-quark",
    "g-dbus-error-quark",
    "g-file-error-quark",
    "g-io-error-quark",
    "g-spawn-error-quark",
}


def load_api():
    global _EXPECTED_ERRORS, _GLIB
    import gi
    gi.require_version("Flatpak", "1.0")
    from gi.repository import Flatpak, Gio, GLib
    _GLIB = GLib
    _EXPECTED_ERRORS = (OSError, RuntimeError, ValueError, TypeError, KeyError, configparser.Error, GLib.Error)
    return Flatpak, Gio


def _safe_error_domain(error) -> str:
    domain = getattr(error, "domain", "")
    if not isinstance(domain, str):
        try:
            domain = _GLIB.quark_to_string(int(domain)) if _GLIB is not None else ""
        except (AttributeError, TypeError, ValueError):
            domain = ""
    return domain if domain in _SAFE_ERROR_DOMAINS else ""


def installation(api, name: str):
    if name == "user":
        return api.Installation.new_user(None)
    if name == "system":
        return api.Installation.new_system(None)
    return api.Installation.new_system_with_id(name, None)


def _record(item) -> dict[str, Any]:
    return {"ref": item.format_ref(), "commit": item.get_commit() or "", "size_bytes": item.get_installed_size()}


def _shared_dependencies(api, target, candidates: list[dict[str, Any]]) -> tuple[set[str], str]:
    """Conservatively protect dependencies across accessible installations.

    All foreign refs are roots, including their unused runtimes. Reading every
    installed node covers transitive runtime/SDK/extension dependencies without
    guessing that a foreign ref is safe to disregard.
    """
    own_path = target.get_path().get_path()
    user = api.Installation.new_user(None)
    installations = [("selected", target), ("user", user)]
    installations.extend((system.get_id() or "default", system) for system in api.get_system_installations(None)
                         if system.get_path().get_path() != own_path)
    evidence = []
    protected: set[str] = set()
    extension_ids: set[str] = set()
    for source, current in installations:
        current.drop_caches(None)
        refs = current.list_installed_refs(None)
        for item in refs:
            ref = item.format_ref()
            metadata_bytes = item.load_metadata(None).get_data()
            if len(metadata_bytes) > MAX_OUTPUT:
                raise ValueError("Dependency metadata exceeds the inspection limit.")
            metadata = configparser.ConfigParser(interpolation=None, strict=False)
            metadata.read_string(metadata_bytes.decode("utf-8"))
            evidence.append({"source": source, "ref": ref, "commit": item.get_commit(),
                             "metadata": hashlib.sha256(metadata_bytes).hexdigest()})
            if source == "selected":
                # libflatpak already resolved this installation's used roots.
                # Hash own metadata, but do not promote its unused refs to roots.
                continue
            protected.add(ref)
            for section, keys in (("Application", ("runtime", "sdk")), ("Runtime", ("runtime", "sdk")), ("ExtensionOf", ("ref",))):
                for key in keys:
                    value = metadata.get(section, key, fallback="")
                    if value:
                        dependency = value if value.startswith(("app/", "runtime/")) else "runtime/" + value
                        if not REF_PATTERN.fullmatch(dependency):
                            raise ValueError("Malformed installed dependency metadata.")
                        protected.add(dependency)
            for section in metadata.sections():
                if section.startswith("Extension "):
                    extension = section[len("Extension "):]
                    if not REF_PATTERN.fullmatch(f"runtime/{extension}/x86_64/stable"):
                        raise ValueError("Malformed installed extension metadata.")
                    extension_ids.add(extension)
    # Flatpak subdirectory extensions use child IDs. Protect every installed
    # architecture/branch conservatively instead of guessing conditional rules.
    protected.update(item["ref"] for item in candidates if any(item["ref"].split("/")[1] == extension
                     or item["ref"].split("/")[1].startswith(extension + ".") for extension in extension_ids))
    digest = hashlib.sha256(json.dumps(sorted(evidence, key=lambda item: (item["source"], item["ref"])), sort_keys=True).encode()).hexdigest()
    return protected, digest


def inspect_unused(target, name: str, api=None) -> dict[str, Any]:
    target.drop_caches(None)
    installed = sorted((_record(item) for item in target.list_installed_refs(None)), key=lambda item: item["ref"])
    unused = sorted((_record(item) for item in target.list_unused_refs(None, None)), key=lambda item: item["ref"])
    if any(not item["ref"].startswith("runtime/") for item in unused):
        raise ValueError("Unexpected non-runtime cleanup candidate.")
    pins = sorted(item.format_ref() for item in target.list_pinned_refs(None, None))
    dependency_digest = ""
    if name != "user":
        if api is None:
            api, _gio = load_api()
        protected, dependency_digest = _shared_dependencies(api, target, unused)
        unused = [item for item in unused if item["ref"] not in protected]
    return {"available": True, "installation": name, "installed": installed, "refs": unused, "pins": pins,
            **({"dependency_digest": dependency_digest} if dependency_digest else {}),
            "digest": snapshot_digest(name, installed, unused, pins, dependency_digest)}


def inspect_details(api, target, ref: str, name: str) -> dict[str, Any]:
    target.drop_caches(None)
    installed = {item.format_ref(): item for item in target.list_installed_refs(None)}
    item = installed.get(ref)
    if item is None:
        return {"available": False, "error": "The selected ref is not installed in this installation."}
    metadata = configparser.ConfigParser(interpolation=None, strict=False)
    metadata.read_string(item.load_metadata(None).get_data().decode("utf-8"))
    runtime = metadata.get("Application", "runtime", fallback="")
    if runtime:
        runtime = "runtime/" + runtime
        if not REF_PATTERN.fullmatch(runtime):
            raise ValueError("Invalid runtime metadata.")
    runtime_item = installed.get(runtime)
    if runtime and runtime_item is None:
        # Apps can depend on a runtime in another public system installation.
        # Never inspect a private user installation for a shared app.
        own_path = target.get_path().get_path()
        systems = sorted((system for system in api.get_system_installations(None) if system.get_path().get_path() != own_path),
                         key=lambda system: system.get_priority(), reverse=True)
        for system in systems:
            system.drop_caches(None)
            runtime_item = next((item for item in system.list_installed_refs(None) if item.format_ref() == runtime), None)
            if runtime_item is not None:
                break
    return {"available": True, "ref": ref, "installation": name,
            "name": item.get_appdata_name() or item.get_name(), "version": item.get_appdata_version() or "",
            "origin": item.get_origin() or "", "runtime": runtime, "size_bytes": item.get_installed_size(),
            "eol": item.get_eol() or "", "eol_rebase": item.get_eol_rebase() or "",
            "runtime_eol": runtime_item.get_eol() or "" if runtime_item else "",
            "runtime_eol_rebase": runtime_item.get_eol_rebase() or "" if runtime_item else "",
            "runtime_missing": bool(runtime and runtime_item is None)}


def apply_cleanup(api, gio, target, name: str, expected_digest: str, refs: list[str]) -> dict[str, Any]:
    before = inspect_unused(target, name, api)
    candidates = {item["ref"] for item in before["refs"]}
    if before["digest"] != expected_digest or not set(refs).issubset(candidates):
        return {"available": True, "success": False, "review_required": True,
                "error": "Flatpak candidates, installed commits or pins changed; review a fresh snapshot."}
    cancellable = gio.Cancellable.new()
    previous_handlers = {}
    for signum in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[signum] = signal.signal(signum, lambda _s, _f: cancellable.cancel())
    previous_umask = os.umask(0o022) if name != "user" else None
    result: dict[str, Any] = {"available": True, "success": False, "removed_refs": [], "remaining_refs": refs,
                              "unexpected_missing_refs": [], "data_preserved": True}
    try:
        transaction = api.Transaction.new_for_installation(target, cancellable)
        transaction.set_disable_dependencies(True)
        transaction.set_disable_related(True)
        transaction.set_disable_prune(True)
        transaction.set_force_uninstall(False)
        # Native Flatpak/Polkit authorization is available; no privilege wrapper.
        transaction.set_no_interaction(False)
        transaction.connect("operation-error", lambda *_args: False)

        def ready(current) -> bool:
            fresh = inspect_unused(target, name, api)
            operations = current.get_operations()
            actual = [operation.get_ref() for operation in operations]
            valid = (fresh["digest"] == expected_digest and len(actual) == len(refs) and set(actual) == set(refs)
                     and all(operation.get_operation_type() == api.TransactionOperationType.UNINSTALL for operation in operations))
            if not valid:
                result["review_required"] = True
                result["error"] = "Transaction or Flatpak evidence changed; review again."
            return valid
        transaction.connect("ready", ready)
        for ref in refs:
            transaction.add_uninstall(ref)
        result["success"] = bool(transaction.run(cancellable))
    except _EXPECTED_ERRORS:
        # API errors may contain remote URLs or tokens: expose only bounded local context.
        result["error"] = "Flatpak transaction failed or authorization was declined."
    finally:
        if previous_umask is not None:
            os.umask(previous_umask)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        result["cancelled"] = cancellable.is_cancelled()
        try:
            after = inspect_unused(target, name, api)
            remaining = {item["ref"] for item in after["installed"]}
            before_refs = {item["ref"] for item in before["installed"]}
            result["removed_refs"] = sorted(set(refs) - remaining)
            result["remaining_refs"] = sorted(set(refs) & remaining)
            result["unexpected_missing_refs"] = sorted(before_refs - set(refs) - remaining)
            result["success"] = bool(result["success"] and not result["remaining_refs"] and not result["unexpected_missing_refs"])
        except _EXPECTED_ERRORS:
            result["success"] = False
            result["error"] = "The transaction result could not be inspected; review Activity and the installation."
    return result


def _update_candidate(item, name: str, expected_commit: str) -> dict[str, Any]:
    return {"installation": name, "ref": item.format_ref(), "origin": item.get_origin() or "",
            "installed_commit": item.get_commit() or "", "expected_commit": expected_commit,
            "name": item.get_appdata_name() or item.get_name(), "installed_version": item.get_appdata_version() or "", "available_version": ""}


def _update_source_digest(target) -> str:
    """Bind relevant source configuration without exposing private locations."""
    from services.software.flatpak_maintenance import INSTALLATION_PATTERN

    def fingerprint(path: Path) -> str:
        with path.open("rb") as stream:
            content = stream.read(MAX_OUTPUT + 1)
        if len(content) > MAX_OUTPUT:
            raise ValueError("Flatpak source evidence exceeds its bound.")
        return hashlib.sha256(content).hexdigest()

    sources = []
    for remote in target.list_remotes(None):
        name = remote.get_name()
        if not isinstance(name, str) or not INSTALLATION_PATTERN.fullmatch(name):
            raise ValueError("Invalid Flatpak source identity.")
        source = {"name": name, "url": remote.get_url(), "gpg_verify": remote.get_gpg_verify(),
                  "disabled": remote.get_disabled(), "collection": remote.get_collection_id(),
                  "filter": remote.get_filter(), "nodeps": remote.get_nodeps(), "noenumerate": remote.get_noenumerate(),
                  "priority": remote.get_prio(), "default_branch": remote.get_default_branch(), "main_ref": remote.get_main_ref()}
        key = Path(target.get_path().get_path()) / "repo" / (name + ".trustedkeys.gpg")
        source["key_digest"] = fingerprint(key) if key.is_file() else ""
        source["filter_digest"] = fingerprint(Path(source["filter"])) if source["filter"] else ""
        sources.append(source)
    identity = os.path.realpath(target.get_path().get_path())
    config = Path(identity) / "repo" / "config"
    payload = {"installation_path": identity, "sources": sorted(sources, key=lambda item: item["name"]),
               "repo_config_digest": fingerprint(config) if config.is_file() else ""}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _system_source_commit_bound(target, origin: str) -> bool:
    """Exclude libflatpak's unpinned system-helper LOCAL_PULL path.

    Unsigned file remotes are reread by the privileged helper after ready,
    without the resolved checksum. Signed OSTree child repos and OCI images
    retain their reviewed content; ordinary unsigned network remotes are
    rejected by native Flatpak before deployment.
    """
    remote = next((item for item in target.list_remotes(None) if item.get_name() == origin), None)
    if remote is None:
        return False
    url = remote.get_url()
    if not isinstance(url, str) or not url:
        return False
    if not url.startswith("file:"):
        return True
    if remote.get_gpg_verify() is not True:
        return False
    try:
        path = Path(target.get_path().get_path()) / "repo" / "config"
        with path.open("r", encoding="utf-8") as stream:
            content = stream.read(MAX_OUTPUT + 1)
        if len(content) > MAX_OUTPUT:
            return False
        if _GLIB is None:
            return False
        # Match libostree's exact key names and group semantics. Python's
        # ConfigParser inherits DEFAULT and folds keys, unlike GLib.KeyFile.
        config = _GLIB.KeyFile.new()
        config.load_from_data(content, len(content.encode("utf-8")), _GLIB.KeyFileFlags.NONE)
        return config.get_boolean(f'remote "{origin}"', "gpg-verify-summary") is True
    except _EXPECTED_ERRORS:
        return False


def inspect_updates(target, name: str, refs: list[str]) -> dict[str, Any]:
    from services.software.flatpak_updates import update_digest
    target.drop_caches(None)
    if refs and not set(refs).issubset({item.format_ref() for item in target.list_installed_refs(None)}):
        raise ValueError("Selected Flatpak ref is no longer installed.")
    values = []
    for item in target.list_installed_refs_for_update(None):
        if refs and item.format_ref() not in refs:
            continue
        remote = target.fetch_remote_ref_sync(item.get_origin(), item.get_kind(), item.get_name(), item.get_arch(), item.get_branch(), None)
        values.append(_update_candidate(item, name, remote.get_commit() or ""))
    candidates = sorted((item for item in values if not refs or item["ref"] in refs), key=lambda item: item["ref"])
    sources = _update_source_digest(target)
    return {"available": True, "installation": name, "candidates": candidates, "operations": [], "source_digest": sources,
            "digest": update_digest(name, candidates, [], sources)}


def update_transaction(api, gio, target, name: str, candidates: list[dict[str, Any]], expected_digest: str = "", *, installing: bool = False) -> dict[str, Any]:
    """Resolve at ready-pre-auth; apply only an identical approved operation set."""
    from services.software.flatpak_updates import update_digest
    cancellable = gio.Cancellable.new()
    handlers = {number: signal.signal(number, lambda _s, _f: cancellable.cancel()) for number in (signal.SIGTERM, signal.SIGINT)}
    result: dict[str, Any] = {"available": True, "installation": name, "candidates": candidates, "operations": [], "success": False}
    previous_umask = os.umask(0o022) if expected_digest and name != "user" else None
    approved = {item["ref"]: item for item in candidates}
    operation_errors: list[dict[str, Any]] = []
    active_ref = ""
    preview_ready = False
    try:
        transaction = api.Transaction.new_for_installation(target, cancellable)
        transaction.set_no_interaction(not bool(expected_digest))
        transaction.set_disable_prune(True)
        transaction.add_default_dependency_sources()
        transaction.connect("add-new-remote", lambda *_args: False)
        transaction.connect("end-of-lifed-with-rebase", lambda *_args: False)

        def operation_error(_transaction, operation, error, details):
            try:
                ref = operation.get_ref() or ""
            except _EXPECTED_ERRORS:
                ref = ""
            try:
                code = int(error.code)
            except (AttributeError, TypeError, ValueError):
                code = -1
            try:
                detail_flags = int(details)
            except (TypeError, ValueError):
                detail_flags = -1
            operation_errors.append({"ref": ref, "domain": _safe_error_domain(error), "code": code,
                                     "details": detail_flags})
            return False

        def operation_started(_transaction, operation, _progress):
            nonlocal active_ref
            try:
                active_ref = operation.get_ref() or ""
            except _EXPECTED_ERRORS:
                active_ref = ""

        transaction.connect("new-operation", operation_started)
        transaction.connect("operation-error", operation_error)

        def resolved(current):
            nonlocal preview_ready
            target.drop_caches(None)
            installed = {item.format_ref(): item for item in target.list_installed_refs(None)}
            operations = []
            seen_refs: set[str] = set()
            for operation in current.get_operations():
                kind = operation.get_operation_type()
                if kind not in {api.TransactionOperationType.UPDATE, api.TransactionOperationType.INSTALL}:
                    raise ValueError("Unapproved transaction operation.")
                ref = operation.get_ref()
                existing = installed.get(ref)
                selected = approved.get(ref)
                if installing:
                    from services.software.flatpak_maintenance import DIGEST_PATTERN, INSTALLATION_PATTERN
                    if not isinstance(ref, str) or not REF_PATTERN.fullmatch(ref) or ref in seen_refs:
                        raise ValueError("Invalid or duplicate installation operation ref.")
                    seen_refs.add(ref)
                    origin = operation.get_remote()
                    before = existing.get_commit() if existing else ""
                    before_origin = existing.get_origin() if existing else ""
                    if (not isinstance(origin, str) or not INSTALLATION_PATTERN.fullmatch(origin)
                            or not isinstance(before, str) or (before and not DIGEST_PATTERN.fullmatch(before))
                            or not isinstance(before_origin, str) or (before_origin and not INSTALLATION_PATTERN.fullmatch(before_origin))
                            or (kind == api.TransactionOperationType.INSTALL and existing is not None)
                            or (kind == api.TransactionOperationType.UPDATE and existing is None)):
                        raise ValueError("Invalid previous installation operation state.")
                    if not isinstance(operation.get_commit(), str) or not DIGEST_PATTERN.fullmatch(operation.get_commit()):
                        raise ValueError("Invalid resolved installation commit.")
                if selected and installing and (existing is not None or kind != api.TransactionOperationType.INSTALL or operation.get_remote() != selected["origin"]):
                    raise ValueError("Selected first installation changed.")
                if selected and not installing and (existing is None or existing.get_commit() != selected["installed_commit"] or existing.get_origin() != selected["origin"]):
                    raise ValueError("Selected installed state changed.")
                operation_commit = operation.get_commit() or ""
                if selected and operation_commit != selected["expected_commit"]:
                    raise ValueError("Selected update commit changed.")
                if name != "user" and not _system_source_commit_bound(target, operation.get_remote() or ""):
                    result["available"] = False
                    result["error"] = ("This system source cannot guarantee the reviewed commit. "
                                       "Local sources require signed commits and signed summaries.")
                    return False
                operations.append({"installation": name, "ref": ref, "origin": operation.get_remote() or "",
                                   "installed_commit": existing.get_commit() if existing else "", "expected_commit": operation_commit,
                                   "name": (existing.get_appdata_name() or existing.get_name()) if existing else ref.split("/")[1],
                                   "installed_version": existing.get_appdata_version() or "" if existing else "", "available_version": "",
                                   "operation": "update" if kind == api.TransactionOperationType.UPDATE else "install", "selected": selected is not None})
                if installing:
                    operations[-1]["installed_origin"] = existing.get_origin() if existing else ""
            if not set(approved).issubset({item["ref"] for item in operations}):
                raise ValueError("Selected refs disappeared from transaction.")
            result["operations"] = sorted(operations, key=lambda item: item["ref"])
            result["source_digest"] = _update_source_digest(target)
            result["digest"] = update_digest(name, candidates, result["operations"], result["source_digest"])
            if expected_digest and result["digest"] != expected_digest:
                result["review_required"] = True
                return False
            preview_ready = True
            return bool(expected_digest)

        transaction.connect("ready-pre-auth" if not expected_digest else "ready", resolved)
        for candidate in candidates:
            # An explicit commit enables libflatpak's downgrade mode, which
            # system installations reject for unprivileged callers. Resolve
            # normally, then bind approval to get_commit() in resolved(). The
            # transaction executes that immutable resolved commit afterwards.
            if installing:
                transaction.add_install(candidate["origin"], candidate["ref"], None)
            else:
                transaction.add_update(candidate["ref"], None, None)
        if candidates:
            result["success"] = bool(transaction.run(cancellable))
            if operation_errors:
                result["operation_errors"] = operation_errors
        else:
            result["source_digest"] = _update_source_digest(target)
            result["digest"] = update_digest(name, [], [], result["source_digest"])
            preview_ready = True
    except _EXPECTED_ERRORS as exc:
        matches = getattr(exc, "matches", None)
        if callable(matches) and matches(gio.io_error_quark(), gio.IOErrorEnum.CANCELLED):
            cancellable.cancel()
        if expected_digest or not preview_ready:
            result["available"] = bool(expected_digest) and result["available"]
            result.setdefault("error", "Flatpak transaction failed, changed or authorization was declined.")
        if operation_errors:
            result["operation_errors"] = operation_errors
        elif active_ref:
            try:
                code = int(getattr(exc, "code", -1))
            except (AttributeError, TypeError, ValueError):
                code = -1
            result["operation_errors"] = [{
                "ref": active_ref,
                "domain": _safe_error_domain(exc),
                "code": code,
                "details": -1,
            }]
    finally:
        if previous_umask is not None:
            os.umask(previous_umask)
        for number, handler in handlers.items():
            signal.signal(number, handler)
        result["cancelled"] = cancellable.is_cancelled()
    if not expected_digest:
        result.pop("success", None)
        if not preview_ready:
            result["available"] = False
    else:
        try:
            target.drop_caches(None)
            installed = {item.format_ref(): item for item in target.list_installed_refs(None)}
            result["results"] = [{"installation": name, "ref": item["ref"], "expected_commit": item["expected_commit"],
                                  "observed_commit": installed[item["ref"]].get_commit() if item["ref"] in installed else "",
                                  "status": "verified" if item["ref"] in installed and installed[item["ref"]].get_commit() == item["expected_commit"] else "cancelled" if result["cancelled"] else "failed"}
                                 for item in result["operations"]]
            result["success"] = bool(result["success"] and all(item["status"] == "verified" for item in result["results"]))
        except _EXPECTED_ERRORS:
            result["success"] = False
            result["error"] = "Updated commits could not be verified."
    return result


def apply_updates(api, gio, args: list[str]) -> dict[str, Any]:
    scopes, index = [], 1
    while index < len(args):
        name, digest = args[index + 1], args[index + 3]
        index += 4
        selected = {}
        while index < len(args) and args[index] == "--ref":
            selected[args[index + 1]] = args[index + 3]
            index += 4
        scopes.append((name, digest, selected))
    prepared = []
    # Resolve every installation before starting the first mutation.
    for name, digest, selected in scopes:
        target = installation(api, name)
        candidates = inspect_updates(target, name, list(selected))["candidates"]
        if {item["ref"]: item["expected_commit"] for item in candidates} != selected:
            return {"available": True, "success": False, "review_required": True, "error": "Update candidates changed. Review again."}
        preview = update_transaction(api, gio, target, name, candidates)
        if preview.get("cancelled"):
            return {"available": True, "success": False, "cancelled": True, "installations": [preview]}
        if not preview.get("available") or preview.get("digest") != digest:
            return {"available": True, "success": False, "review_required": True, "error": "Update transaction changed. Review again."}
        prepared.append((target, name, digest, candidates))
    results = []
    for target, name, digest, candidates in prepared:
        result = update_transaction(api, gio, target, name, candidates, digest)
        results.append(result)
        if not result.get("success"):
            break
    return {"available": True, "success": len(results) == len(scopes) and all(item.get("success") for item in results), "installations": results,
            "cancelled": any(item.get("cancelled", False) for item in results)}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not validate_helper_args(args):
        payload: dict[str, Any] = {"available": False, "error": "Invalid maintenance command."}
        status = 2
    elif args[0] in {"apply", "update-apply", "install-apply"} and os.geteuid() == 0:
        payload = {"available": False, "error": "Cleanup must use the invoking user and native Flatpak authorization."}
        status = 2
    else:
        try:
            api, gio = load_api()
            if args[0] == "installations":
                names = ["user", "system", *[item.get_id() for item in api.get_system_installations(None) if item.get_id() not in {None, "default", "system", "user"}]]
                payload = {"available": True, "installations": list(dict.fromkeys(names))}
            elif args[0] == "update-apply":
                payload = apply_updates(api, gio, args)
            elif args[0] in {"install-preview", "install-apply"}:
                from services.software.flatpak_installation_helper import install_transaction
                payload = install_transaction(api, gio, installation(api, args[2]), args[2], args[4], args[6], args[8] if args[0] == "install-apply" else "")
            else:
                name = args[2]
                target = installation(api, name)
                if args[0] in {"updates", "update-preview"}:
                    payload = inspect_updates(target, name, args[4::2])
                    if args[0] == "update-preview":
                        payload = update_transaction(api, gio, target, name, payload["candidates"])
                elif args[0] == "unused":
                    payload = inspect_unused(target, name, api)
                elif args[0] == "update-state":
                    target.drop_caches(None)
                    item = next((item for item in target.list_installed_refs(None) if item.format_ref() == args[4]), None)
                    payload = {"available": True, "installation": name, "ref": args[4], "commit": item.get_commit() if item else "", "origin": item.get_origin() if item else ""}
                elif args[0] == "details":
                    payload = inspect_details(api, target, args[4], name)
                else:
                    payload = apply_cleanup(api, gio, target, name, args[4], args[6::2])
            status = 126 if payload.get("cancelled") else 0 if payload.get("available") and payload.get("success", True) else 1
        except (ImportError, ValueError):
            payload = {"available": False, "error": "Local Flatpak support is unavailable. Optional PyGObject and libflatpak are required."}
            status = 1
        except _EXPECTED_ERRORS:
            payload = {"available": False, "error": "The selected Flatpak installation could not be inspected."}
            status = 1
    output = json.dumps(payload, sort_keys=True)
    if len(output.encode()) > MAX_OUTPUT:
        output = json.dumps({"available": False, "error": "Flatpak evidence exceeded the output limit."})
        status = 1
    print(output, flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
