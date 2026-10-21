"""Commit-bound first installation previews with complete dependency evidence."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.actions.contracts import VerificationDecision

from services.software.flatpak_maintenance import DIGEST_PATTERN, INSTALLATION_PATTERN, REF_PATTERN, FlatpakMaintenanceService, helper_command
from services.software.flatpak_updates import update_digest


@dataclass(frozen=True)
class FlatpakInstallationPreview:
    available: bool = False
    error: str = "Flatpak installation evidence is unavailable. Review again."
    installation: str = ""
    remote: str = ""
    ref: str = ""
    operations: tuple[dict[str, Any], ...] = ()
    digest: str = ""
    source_digest: str = ""
    candidates: tuple[dict[str, Any], ...] = ()

    def review_facts(self) -> dict[str, Any]:
        return {"evidence_version": 1, "installation": self.installation, "remote": self.remote, "ref": self.ref,
                "operations": list(self.operations), "candidates": list(self.candidates), "digest": self.digest, "source_digest": self.source_digest}

    def apply_vector(self) -> list[str]:
        if not self.available:
            raise ValueError(self.error)
        return [helper_command(), "install-apply", "--installation", self.installation, "--remote", self.remote, "--ref", self.ref, "--snapshot-digest", self.digest]


def preview_from_facts(value: Any) -> FlatpakInstallationPreview:
    try:
        if not isinstance(value, dict) or value.get("evidence_version") != 1:
            raise ValueError("Fresh install evidence required")
        name, remote, ref = (value[key] for key in ("installation", "remote", "ref"))
        if not all(isinstance(item, str) and INSTALLATION_PATTERN.fullmatch(item) for item in (name, remote)) or not isinstance(ref, str) or not REF_PATTERN.fullmatch(ref) or not ref.startswith("app/"):
            raise ValueError("Invalid install identity")
        operations, candidates = value["operations"], value["candidates"]
        if not isinstance(operations, (list, tuple)) or not 1 <= len(operations) <= 256 or not isinstance(candidates, (list, tuple)) or len(candidates) != 1:
            raise ValueError("Invalid transaction")
        selected = candidates[0]
        if not isinstance(selected, dict) or selected.get("installation") != name or selected.get("ref") != ref or selected.get("origin") != remote or selected.get("installed_commit") != "":
            raise ValueError("Invalid selected install")
        if not DIGEST_PATTERN.fullmatch(str(selected.get("expected_commit", ""))):
            raise ValueError("Invalid target commit")
        seen = set()
        for operation in operations:
            if not isinstance(operation, dict) or operation.get("installation") != name or not isinstance(operation.get("ref"), str) or not REF_PATTERN.fullmatch(operation["ref"]) or operation["ref"] in seen:
                raise ValueError("Invalid operation identity")
            seen.add(operation["ref"])
            if operation.get("operation") not in {"install", "update"} or not INSTALLATION_PATTERN.fullmatch(str(operation.get("origin", ""))) or not DIGEST_PATTERN.fullmatch(str(operation.get("expected_commit", ""))):
                raise ValueError("Invalid operation authority")
            before_origin = operation.get("installed_origin", "")
            if not isinstance(before_origin, str) or (before_origin and not INSTALLATION_PATTERN.fullmatch(before_origin)) or (operation["operation"] == "install" and before_origin) or (operation["operation"] == "update" and not before_origin):
                raise ValueError("Invalid previous source")
            before = operation.get("installed_commit")
            if not isinstance(before, str) or (before and not DIGEST_PATTERN.fullmatch(before)) or (operation["operation"] == "install" and before) or (operation["operation"] == "update" and not before):
                raise ValueError("Invalid previous commit")
            if operation["ref"] == ref and (operation.get("origin") != remote or operation.get("operation") != "install" or operation.get("expected_commit") != selected["expected_commit"] or operation.get("selected") is not True):
                raise ValueError("Selected install changed")
        if ref not in seen or not DIGEST_PATTERN.fullmatch(str(value["source_digest"])) or update_digest(name, candidates, operations, value["source_digest"]) != value["digest"]:
            raise ValueError("Transaction digest changed")
        return FlatpakInstallationPreview(True, "", name, remote, ref, tuple(dict(item) for item in operations), value["digest"], value["source_digest"], tuple(dict(item) for item in candidates))
    except (KeyError, TypeError, ValueError):
        return FlatpakInstallationPreview()


class FlatpakInstallationService:
    def __init__(self, runtime=None, *, probe=None) -> None:
        self.runtime = runtime
        self.probe = probe

    def verify(self, preview: FlatpakInstallationPreview):
        return verify_preview(preview, self.runtime, probe=self.probe)

    def preview(self, installation: str, remote: str, ref: str) -> FlatpakInstallationPreview:
        if not all(isinstance(item, str) and INSTALLATION_PATTERN.fullmatch(item) for item in (installation, remote)) or not REF_PATTERN.fullmatch(ref) or not ref.startswith("app/"):
            return FlatpakInstallationPreview()
        vector = [helper_command(), "install-preview", "--installation", installation, "--remote", remote, "--ref", ref]
        if self.probe is not None:
            payload = self.probe(vector)
        elif self.runtime is not None:
            result = self.runtime.execute_read_only(vector, action_id="flatpak-install-preview", timeout=90)
            try:
                complete = getattr(result, "structured_output", None)
                output = complete if isinstance(complete, str) else result.stdout
                payload = json.loads(output) if result.success and len(output) <= 1024 * 1024 else {}
            except (TypeError, ValueError):
                payload = {}
        else:
            payload = FlatpakMaintenanceService._probe(vector)
        if not isinstance(payload, dict) or payload.get("available") is not True or payload.get("installation") != installation:
            return FlatpakInstallationPreview()
        return preview_from_facts({**payload, "evidence_version": 1, "remote": remote, "ref": ref})


def verify_preview(preview: FlatpakInstallationPreview, runtime=None, *, probe=None) -> VerificationDecision:
    """Independently read each exact installed ref, origin and resolved commit."""
    checked = preview_from_facts(preview.review_facts()) if preview.available else FlatpakInstallationPreview()
    if not checked.available:
        return VerificationDecision.failed("Fresh installation-bound transaction evidence is required.")
    results = []
    for operation in checked.operations:
        vector = [helper_command(), "update-state", "--installation", checked.installation, "--ref", operation["ref"]]
        try:
            if probe is not None:
                payload = probe(vector)
            elif runtime is not None:
                result = runtime.execute_read_only(vector, action_id="flatpak-install-verify", timeout=20)
                payload = json.loads(result.stdout) if result.success else {}
            else:
                payload = FlatpakMaintenanceService._probe(vector)
        except (OSError, RuntimeError, TypeError, ValueError):
            payload = {}
        valid = (isinstance(payload, dict) and payload.get("available") is True and payload.get("installation") == checked.installation
                 and payload.get("ref") == operation["ref"] and payload.get("commit") == operation["expected_commit"] and payload.get("origin") == operation["origin"])
        results.append({"installation": checked.installation, "ref": operation["ref"], "expected_commit": operation["expected_commit"],
                        "expected_origin": operation["origin"], "observed_commit": payload.get("commit", "") if isinstance(payload, dict) else "",
                        "observed_origin": payload.get("origin", "") if isinstance(payload, dict) else "", "status": "verified" if valid else "unverified"})
    if any(item["status"] != "verified" for item in results):
        return VerificationDecision.failed("Some installed Flatpak commits or origins could not be verified.", results=results)
    return VerificationDecision.succeeded("Every reviewed Flatpak ref, origin and dependency commit was verified.", results=results)
