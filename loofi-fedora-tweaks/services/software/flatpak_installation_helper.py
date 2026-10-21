"""First-install mode for the existing native libflatpak transaction runner."""
from __future__ import annotations

from typing import Any

from services.software.flatpak_maintenance import DIGEST_PATTERN


def install_transaction(api, gio, target, installation: str, remote: str, ref: str, digest: str = "") -> dict[str, Any]:
    from services.software.flatpak_maintenance_helper import update_transaction

    target.drop_caches(None)
    if any(item.format_ref() == ref for item in target.list_installed_refs(None)):
        return {"available": False, "error": "The selected ref is already installed. Review again."}
    origin = next((item for item in target.list_remotes(None) if item.get_name() == remote), None)
    if origin is None or origin.get_disabled():
        return {"available": False, "error": "The selected configured remote is unavailable."}
    _, app, arch, branch = ref.split("/")
    target_ref = target.fetch_remote_ref_sync(remote, api.RefKind.APP, app, arch, branch, None)
    commit = target_ref.get_commit() or ""
    if not DIGEST_PATTERN.fullmatch(commit):
        return {"available": False, "error": "The selected remote commit is unavailable."}
    candidate = {"installation": installation, "ref": ref, "origin": remote, "installed_commit": "", "expected_commit": commit,
                 "name": app, "installed_version": "", "available_version": ""}
    result = update_transaction(api, gio, target, installation, [candidate], digest, installing=True)
    result.update(remote=remote, ref=ref)
    return result
