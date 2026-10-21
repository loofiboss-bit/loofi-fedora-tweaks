"""Exact, review-bound RPM transactions; observation never authorizes mutation."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from core.actions.contracts import ActionRuntime, VerificationDecision
from services.software.installed_applications import InstalledApplicationService

HELPER = "/usr/bin/loofi-rpm-transaction"
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._:~^-]{0,255}$")
REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
CODEC_PACKAGES = ("ffmpeg", "gstreamer1-plugins-bad-freeworld", "gstreamer1-plugins-ugly")
CODEC_REPLACEMENTS = frozenset({"ffmpeg-free", "libavcodec-free", "libavdevice-free", "libavfilter-free", "libavformat-free",
                                "libavutil-free", "libpostproc-free", "libswresample-free", "libswscale-free"})
PROTECTED = frozenset({"loofi-fedora-tweaks", "dnf5", "libdnf5", "rpm", "rpm-libs", "systemd", "systemd-libs", "glibc", "bash",
                       "python3", "python3-libs", "python3-libdnf5", "python3-rpm", "python3-pyqt6", "polkit-libs",
                       "kernel", "kernel-core", "kernel-modules", "grub2-common", "grub2-tools", "shim-x64", "polkit", "NetworkManager",
                       "plasma-workspace", "plasma-desktop", "kwin", "kwin-wayland", "sddm", "gnome-shell", "gdm", "qt6-qtbase", "qt6-qtbase-gui"})
INBOUND = frozenset({"Install", "Upgrade", "Reinstall"})
OUTBOUND = frozenset({"Remove", "Replaced"})
ERROR_MESSAGES = {
    "rpm_transaction_unavailable": "The RPM transaction is unavailable. Refresh metadata and create a fresh review.",
    "backend_unavailable": "DNF5 Python support is unavailable. Install the supported application package before trying again.",
    "package_lock": "Another package operation holds the lock. Wait for it to finish, then create a fresh review.",
    "no_space": "The affected filesystem has insufficient free space. Free space, check its health, and create a fresh review.",
    "network_error": "The source could not be reached. Check the connection and configured source, then create a fresh review.",
    "signature_error": "Package signatures could not be verified with the trusted keys. Inspect Sources before trying again.",
    "transaction_drift": "Packages or sources changed after review. Create and approve a fresh transaction.",
    "operation_timeout": "The operation reached its time limit. Check its current result in Activity before trying again.",
    "protected_package": "This transaction would remove a protected system or desktop component and cannot run.",
}


def helper_command() -> str:
    """Checkout helpers can observe; privileged vectors always use HELPER."""
    source = Path(__file__).resolve().parents[3] / "scripts" / "loofi-rpm-transaction"
    return str(source) if source.is_file() else HELPER


def trusted_helpers() -> tuple[str, ...]:
    return tuple(dict.fromkeys((helper_command(), HELPER)))


def request_args(operation: str, packages: Sequence[str], repo_id: str = "", allow_replacements: bool = False) -> list[str]:
    if operation not in {"install", "remove", "codecs"} or not 1 <= len(packages) <= 64 or len(set(packages)) != len(packages):
        raise ValueError("Select a supported operation and exact package identifiers.")
    if any(not isinstance(item, str) or not TOKEN.fullmatch(item) for item in packages) or (repo_id and not REPO.fullmatch(repo_id)):
        raise ValueError("RPM package or repository identifier is invalid.")
    if not isinstance(allow_replacements, bool) or (allow_replacements and operation != "codecs"):
        raise ValueError("Package replacements require a separate codec review.")
    if operation == "codecs" and (tuple(packages) != CODEC_PACKAGES or repo_id):
        raise ValueError("Only the predefined multimedia recipe is supported.")
    args = ["--operation", operation]
    if repo_id:
        args.extend(("--repo", repo_id))
    if allow_replacements:
        args.append("--allow-replacements")
    for package in packages:
        args.extend(("--package", package))
    return args


def parse_args(args: Sequence[str]) -> tuple[str, str, tuple[str, ...], str, bool, str]:
    values = list(args)
    if values == ["sources"]:
        return "sources", "", (), "", False, ""
    if not values or values[0] not in {"preview", "apply"} or len(values) > 140:
        raise ValueError("Invalid RPM helper command.")
    mode = values.pop(0)
    if len(values) < 4 or values.pop(0) != "--operation":
        raise ValueError("Invalid RPM helper command.")
    operation = values.pop(0)
    repo_id, digest, replacements, packages = "", "", False, []
    if values[:1] == ["--repo"] and len(values) > 1:
        values.pop(0)
        repo_id = values.pop(0)
    if values[:1] == ["--allow-replacements"]:
        values.pop(0)
        replacements = True
    while len(values) >= 2 and values[0] == "--package":
        values.pop(0)
        packages.append(values.pop(0))
    if mode == "apply" and len(values) == 2 and values[0] == "--snapshot-digest" and DIGEST.fullmatch(values[1]):
        digest = values[1]
        values.clear()
    if values or (mode == "apply" and not digest):
        raise ValueError("Invalid RPM helper command.")
    request_args(operation, packages, repo_id, replacements)
    return mode, operation, tuple(packages), repo_id, replacements, digest


def validate_helper_args(args: Sequence[str]) -> bool:
    try:
        parse_args(args)
        return True
    except (ValueError, TypeError, IndexError):
        return False


def evidence_digest(payload: Mapping[str, Any]) -> str:
    content = json.dumps({key: value for key, value in payload.items() if key != "digest"}, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(content.encode()).hexdigest()


@dataclass(frozen=True)
class RpmTransactionPreview:
    available: bool = False
    error: str = "RPM transaction evidence is unavailable. Refresh metadata and review again."
    evidence_version: int = 1
    operation: str = "install"
    packages: tuple[str, ...] = ()
    repo_id: str = ""
    allow_replacements: bool = False
    operations: tuple[dict[str, Any], ...] = ()
    installed: tuple[str, ...] = ()
    repository_digest: str = ""
    digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        # JSON normalization keeps persisted and in-memory digests identical.
        return cast(dict[str, Any], json.loads(json.dumps(asdict(self))))

    def apply_vector(self) -> list[str]:
        preview_from_facts(self.to_dict())
        return [HELPER, "apply", *request_args(self.operation, self.packages, self.repo_id, self.allow_replacements), "--snapshot-digest", self.digest]


def preview_from_facts(payload: Any) -> RpmTransactionPreview:
    if not isinstance(payload, dict) or payload.get("evidence_version") != 1 or payload.get("available") is not True:
        raise ValueError("RPM evidence is missing or obsolete; create a fresh review.")
    fields = set(RpmTransactionPreview.__dataclass_fields__)
    if set(payload) != fields or not DIGEST.fullmatch(str(payload.get("digest", ""))) or evidence_digest(payload) != payload["digest"]:
        raise ValueError("RPM transaction evidence failed its integrity check.")
    request_args(payload["operation"], payload["packages"], payload["repo_id"], payload["allow_replacements"])
    operations, installed = payload["operations"], payload["installed"]
    if not isinstance(operations, list) or not 1 <= len(operations) <= 4096 or not isinstance(installed, list) or len(installed) > 20000:
        raise ValueError("RPM transaction evidence exceeded its bounds.")
    if len(set(installed)) != len(installed) or not DIGEST.fullmatch(str(payload["repository_digest"])) or any(not isinstance(item, str) or not TOKEN.fullmatch(item) for item in installed):
        raise ValueError("RPM inventory is invalid.")
    for item in operations:
        if (not isinstance(item, dict) or set(item) != {"action", "name", "nevra", "repo_id", "checksum"}
                or item["action"] not in INBOUND | OUTBOUND
                or any(not isinstance(item[key], str) or not TOKEN.fullmatch(item[key]) for key in ("name", "nevra"))
                or not isinstance(item["repo_id"], str) or len(item["repo_id"]) > 128
                or not isinstance(item["checksum"], str) or len(item["checksum"]) > 256):
            raise ValueError("RPM operation evidence is invalid.")
    return RpmTransactionPreview(**{**payload, "packages": tuple(payload["packages"]), "operations": tuple(operations), "installed": tuple(installed)})


class RpmTransactionService:
    def __init__(self, runtime: ActionRuntime | None = None) -> None:
        self.runtime = runtime

    def preview(self, operation: str, packages: tuple[str, ...], *, repo_id: str = "", allow_replacements: bool = False) -> RpmTransactionPreview:
        vector = [helper_command(), "preview", *request_args(operation, packages, repo_id, allow_replacements)]
        if self.runtime is not None:
            result = self.runtime.execute_read_only(vector, action_id="rpm-transaction-preview", timeout=90)
        else:
            result = InstalledApplicationService._probe(vector)
        try:
            complete = getattr(result, "structured_output", None)
            output = complete if isinstance(complete, str) else result.stdout
            if len(output) > 1024 * 1024:
                return RpmTransactionPreview()
            payload = json.loads(output)
            if not result.success or not payload.get("available"):
                return RpmTransactionPreview(error=ERROR_MESSAGES.get(payload.get("error_code"), ERROR_MESSAGES["rpm_transaction_unavailable"]))
            preview = preview_from_facts(payload)
            if (preview.operation, preview.packages, preview.repo_id, preview.allow_replacements) != (operation, packages, repo_id, allow_replacements):
                return RpmTransactionPreview()
            return preview
        except (ValueError, TypeError, AttributeError):
            return RpmTransactionPreview()


def verify_preview(preview: RpmTransactionPreview, runtime: ActionRuntime) -> VerificationDecision:
    """Read the complete RPM inventory independently, including after failures."""
    preview = preview_from_facts(preview.to_dict())
    result = runtime.execute_read_only(("rpm", "-qa", "--qf", "%{NAME}|%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\\n"),
                                       action_id="rpm-transaction-verify", timeout=30)
    complete = getattr(result, "structured_output", None)
    output = complete if isinstance(complete, str) else result.stdout
    if not result.success or len(output) > 1024 * 1024:
        return VerificationDecision.failed("RPM inventory could not be read; the result remains unverified.", evidence_status="unknown")
    rows = [line.split("|") for line in output.splitlines() if line.strip()]
    if any(len(row) != 2 for row in rows):
        return VerificationDecision.failed("RPM inventory has malformed rows; the result remains unverified.", evidence_status="unknown")
    # libdnf5 excludes the RPM keyring's pseudo-packages. Exclude only that
    # exact NAME from independent readback, never arbitrary malformed records.
    observed = tuple(row[1] for row in rows if row[0] != "gpg-pubkey")
    if not observed or any(not TOKEN.fullmatch(item) for item in observed):
        return VerificationDecision.failed("RPM inventory is incomplete; the result remains unverified.", evidence_status="unknown")
    outgoing = {item["nevra"] for item in preview.operations if item["action"] in OUTBOUND}
    incoming = {item["nevra"] for item in preview.operations if item["action"] in INBOUND}
    expected = (set(preview.installed) - outgoing) | incoming
    results = []
    for operation in preview.operations:
        inbound = operation["action"] in INBOUND
        present_expected = inbound or operation["nevra"] in incoming
        results.append({"nevra": operation["nevra"], "action": operation["action"], "status": "verified" if (operation["nevra"] in observed) == present_expected else "unverified"})
    if set(observed) != expected:
        return VerificationDecision.failed("RPM state differs from the complete approved transaction. Review Activity before another change.",
                                           evidence_status="partial" if any(item["status"] == "verified" for item in results) else "unknown", results=results)
    return VerificationDecision.succeeded("Every approved RPM operation and preservation of unrelated packages were verified.", results=results)
