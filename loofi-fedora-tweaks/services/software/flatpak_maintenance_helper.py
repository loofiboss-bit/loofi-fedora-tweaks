"""Narrow libflatpak child process. Never run this helper as root."""
from __future__ import annotations

import configparser
import hashlib
import json
import os
import signal
import sys
from typing import Any

from services.software.flatpak_maintenance import MAX_OUTPUT, REF_PATTERN, snapshot_digest, validate_helper_args

_EXPECTED_ERRORS: tuple[type[Exception], ...] = (OSError, RuntimeError, ValueError, TypeError, KeyError, configparser.Error)


def load_api():
    global _EXPECTED_ERRORS
    import gi
    gi.require_version("Flatpak", "1.0")
    from gi.repository import Flatpak, Gio, GLib
    _EXPECTED_ERRORS = (OSError, RuntimeError, ValueError, TypeError, KeyError, configparser.Error, GLib.Error)
    return Flatpak, Gio


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


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not validate_helper_args(args):
        payload: dict[str, Any] = {"available": False, "error": "Invalid maintenance command."}
        status = 2
    elif args[0] == "apply" and os.geteuid() == 0:
        payload = {"available": False, "error": "Cleanup must use the invoking user and native Flatpak authorization."}
        status = 2
    else:
        try:
            api, gio = load_api()
            if args[0] == "installations":
                names = ["user", "system", *[item.get_id() for item in api.get_system_installations(None) if item.get_id() not in {None, "default", "system", "user"}]]
                payload = {"available": True, "installations": list(dict.fromkeys(names))}
            else:
                name = args[2]
                target = installation(api, name)
                if args[0] == "unused":
                    payload = inspect_unused(target, name, api)
                elif args[0] == "details":
                    payload = inspect_details(api, target, args[4], name)
                else:
                    payload = apply_cleanup(api, gio, target, name, args[4], args[6::2])
            status = 0 if payload.get("available") and payload.get("success", True) else 1
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
