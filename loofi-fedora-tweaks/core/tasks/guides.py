"""Curated, navigation-only Fedora guides and their private progress store."""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, cast

from core.state.atomic_io import advisory_lock, atomic_write_json
from core.state.inventory import StateInventory


GUIDE_SCHEMA_ID = "loofi.user-guides"
GUIDE_SCHEMA_VERSION = 1
MAX_GUIDE_FILE_BYTES = 64 * 1024
MAX_PROGRESS_ENTRIES = 256
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:/-]{0,127}$")

ProgressStatus = Literal["in_progress", "reviewed", "skipped", "verified"]
EvidenceKind = Literal["action_run", "troubleshooting_session"]
EvidenceReferenceKind = EvidenceKind | Literal[""]


@dataclass(frozen=True)
class GuideTarget:
    """An inert navigation request; it never contains an executable action."""

    route_id: str
    task_id: str = ""
    tweak_id: str = ""
    context: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.route_id):
            raise ValueError("Guide target route is invalid.")
        for value in (self.task_id, self.tweak_id):
            if value and not _IDENTIFIER.fullmatch(value):
                raise ValueError("Guide target identifier is invalid.")
        allowed_context = {"run_id", "session_id", "update_source", "symptom"}
        keys = [key for key, _value in self.context]
        if len(keys) != len(set(keys)) or not set(keys).issubset(allowed_context):
            raise ValueError("Guide target context is invalid.")
        if any(not isinstance(value, str) or len(value) > 128 for _key, value in self.context):
            raise ValueError("Guide target context value is invalid.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "task_id": self.task_id,
            "tweak_id": self.tweak_id,
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class GuideStep:
    id: str
    title: str
    description: str
    target: GuideTarget
    keywords: tuple[str, ...] = ()
    evidence_kinds: tuple[EvidenceKind, ...] = ()

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.id) or not self.title.strip() or not self.description.strip():
            raise ValueError("Guide step metadata is invalid.")
        if any(kind not in {"action_run", "troubleshooting_session"} for kind in self.evidence_kinds):
            raise ValueError("Guide step evidence kind is invalid.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "target": self.target.to_dict(),
            "keywords": list(self.keywords),
            "evidence_kinds": list(self.evidence_kinds),
        }


@dataclass(frozen=True)
class GuideDefinition:
    id: str
    title: str
    description: str
    keywords: tuple[str, ...]
    steps: tuple[GuideStep, ...]

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.id) or not self.title.strip() or not self.steps:
            raise ValueError("Guide definition is invalid.")
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError(f"Guide {self.id} has duplicate step IDs.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "keywords": list(self.keywords),
            "steps": [step.to_dict() for step in self.steps],
        }


def _step(
    guide_id: str,
    step_id: str,
    title: str,
    description: str,
    route: str,
    *,
    task: str = "",
    tweak: str = "",
    context: Mapping[str, str] | None = None,
    keywords: tuple[str, ...] = (),
    evidence: tuple[EvidenceKind, ...] = (),
) -> GuideStep:
    return GuideStep(
        id=f"{guide_id}:{step_id}",
        title=title,
        description=description,
        target=GuideTarget(route, task, tweak, tuple(sorted((context or {}).items()))),
        keywords=keywords,
        evidence_kinds=evidence,
    )


GUIDES: tuple[GuideDefinition, ...] = (
    GuideDefinition(
        "make-fedora-yours",
        "Make Fedora yours",
        "Find settings that suit you, review a change, and save your preferences.",
        ("personalize", "appearance", "keyboard", "pointer", "desktop", "profile", "tweak"),
        (
            _step("make-fedora-yours", "find-settings", "Find a setting or preset", "Search desktop controls and inspect the available presets.", "tune", task="tune:tweaks", keywords=("find setting", "appearance", "input")),
            _step("make-fedora-yours", "review-change", "Review a desktop change", "Open a setting or preset and review its exact scope before applying it.", "tune", task="tune:tweaks", keywords=("review", "apply", "change")),
            _step("make-fedora-yours", "verify-change", "Verify a change", "Check the saved value and its Activity record after a change.", "activity", evidence=("action_run",), keywords=("verify", "readback", "undo")),
            _step("make-fedora-yours", "save-profile", "Save a personal profile", "Save supported preferences as a profile for later review or sharing.", "tune", task="tune:profile-library", keywords=("save profile", "export", "share")),
        ),
    ),
    GuideDefinition(
        "choose-and-manage-apps",
        "Choose and manage apps",
        "Find applications and inspect an installation before deciding what to do.",
        ("apps", "applications", "install", "flatpak", "rpm", "permissions", "compare"),
        (
            _step("choose-and-manage-apps", "find-app", "Find an application", "Search the curated catalog or inspect applications already installed.", "install", task="install:applications", keywords=("search apps", "installed", "discover")),
            _step("choose-and-manage-apps", "compare-installations", "Compare installations", "Compare exact installed sources and inspect application details where available.", "install", task="install:applications", keywords=("compare", "rpm", "flatpak", "size")),
            _step("choose-and-manage-apps", "review-app-change", "Review an app change", "Open the existing installation or exact removal review when you choose to make a change.", "install", task="install:applications", evidence=("action_run",), keywords=("install app", "remove flatpak", "review")),
            _step("choose-and-manage-apps", "inspect-app-access", "Inspect app access", "Review declared Flatpak access and use the native permissions tool for changes.", "install", task="install:installed", keywords=("permissions", "access", "flatseal", "default app")),
        ),
    ),
    GuideDefinition(
        "maintain-your-system",
        "Maintain your system",
        "Review update sources, available updates, storage observations, and recorded work.",
        ("maintain", "updates", "dnf", "storage", "disk space", "restart", "activity"),
        (
            _step("maintain-your-system", "review-sources", "Review software sources", "Inspect locally configured DNF sources and their recorded status.", "install", task="install:repositories", keywords=("dnf sources", "repositories")),
            _step("maintain-your-system", "review-updates", "Review updates", "Check sources explicitly, then review the exact updates before installation.", "maintenance:updates", evidence=("action_run",), keywords=("update", "upgrade packages")),
            _step("maintain-your-system", "restart-advice", "Check restart advice", "Read the bounded DNF5 restart recommendation; it never restarts the computer.", "maintenance:updates", keywords=("restart", "reboot")),
            _step("maintain-your-system", "storage-guide", "Review storage", "Inspect measured filesystem, cache, and journal use before choosing any cleanup.", "health", context={"symptom": "storage_full"}, keywords=("free space", "cleanup", "cache")),
            _step("maintain-your-system", "activity", "Review recorded work", "Open Activity to inspect verified results and any recovery guidance.", "activity", keywords=("history", "changes", "results")),
        ),
    ),
    GuideDefinition(
        "solve-a-problem",
        "Solve a problem",
        "Choose a symptom, run a bounded check, and decide what to do with its findings.",
        ("troubleshoot", "health", "diagnose", "fix", "sound", "bluetooth", "internet", "storage", "battery", "screen", "printer", "display", "dock"),
        (
            _step("solve-a-problem", "choose-symptom", "Choose a symptom", "Select the problem that best matches what you observe.", "health", task="fix", keywords=("symptom", "issue")),
            _step("solve-a-problem", "run-check", "Run a read-only check", "Start one explicit diagnostic check and review its available evidence.", "health", evidence=("troubleshooting_session",), keywords=("diagnostic", "inspect")),
            _step("solve-a-problem", "review-findings", "Review findings and next steps", "Use the suggested route or prepare one reviewed action; navigation alone changes nothing.", "health", keywords=("findings", "next step", "repair")),
            _step("solve-a-problem", "check-again", "Check again after a change", "Start a new check after returning from settings or a reviewed operation.", "health", keywords=("recheck", "compare", "follow up")),
            _step("solve-a-problem", "support-question", "Compare or prepare a support question", "Compare saved sessions or export an editable, redacted support question locally.", "health", keywords=("support", "export", "unresolved")),
        ),
    ),
)

GUIDES_BY_ID = {guide.id: guide for guide in GUIDES}
GUIDE_STEPS_BY_ID = {step.id: step for guide in GUIDES for step in guide.steps}


@dataclass(frozen=True)
class GuideStepProgress:
    state: ProgressStatus
    updated_at: float
    evidence_kind: EvidenceReferenceKind = ""
    evidence_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GuideProgress:
    active_guide: str
    active_step: str
    steps: Mapping[str, GuideStepProgress]
    revision: int
    writable: bool = True
    reason_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": GUIDE_SCHEMA_ID,
            "schema_version": GUIDE_SCHEMA_VERSION,
            "revision": self.revision,
            "active_guide": self.active_guide,
            "active_step": self.active_step,
            "writable": self.writable,
            "reason_code": self.reason_code,
            "steps": {key: value.to_dict() for key, value in sorted(self.steps.items())},
        }


# Preserve the descriptive adapter name while exposing the stable domain model.
GuideProgressSnapshot = GuideProgress


class UnsupportedFutureGuideSchema(ValueError):
    """Raised when an unknown future guide-progress file cannot be changed."""


class GuideProgressStore:
    """Private, bounded, atomic guide state that preserves unknown schemas."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or StateInventory().get("user_guides").path

    def read(self) -> GuideProgressSnapshot:
        if self.path.is_symlink():
            raise ValueError("Guide progress must not be a symbolic link.")
        if not self.path.exists():
            return GuideProgressSnapshot("", "", {}, 0)
        try:
            if self.path.stat().st_size > MAX_GUIDE_FILE_BYTES:
                raise ValueError("Guide progress exceeds the bounded file size.")
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Guide progress is unreadable; preserve the file before recovery.") from exc
        if not isinstance(payload, Mapping) or payload.get("schema_id") != GUIDE_SCHEMA_ID:
            raise ValueError("Guide progress has an unsupported schema ID.")
        version = payload.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("Guide progress schema version is invalid.")
        if version > GUIDE_SCHEMA_VERSION:
            return GuideProgressSnapshot("", "", {}, 0, False, "future-schema-read-only")
        if version != GUIDE_SCHEMA_VERSION:
            raise ValueError("Guide progress schema version is unsupported.")
        revision = payload.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ValueError("Guide progress revision is invalid.")
        active_guide = payload.get("active_guide", "")
        active_step = payload.get("active_step", "")
        raw_steps = payload.get("steps", {})
        if not isinstance(active_guide, str) or (active_guide and active_guide not in GUIDES_BY_ID):
            raise ValueError("Guide progress active guide is invalid.")
        if not isinstance(active_step, str) or (active_step and active_step not in GUIDE_STEPS_BY_ID):
            raise ValueError("Guide progress active step is invalid.")
        if not isinstance(raw_steps, Mapping) or len(raw_steps) > MAX_PROGRESS_ENTRIES:
            raise ValueError("Guide progress entries are invalid or exceed the bounded limit.")
        entries: dict[str, GuideStepProgress] = {}
        for key, raw in raw_steps.items():
            if not isinstance(key, str) or key not in GUIDE_STEPS_BY_ID or not isinstance(raw, Mapping):
                raise ValueError("Guide progress contains an unknown step or malformed entry.")
            state = raw.get("state")
            updated_at = raw.get("updated_at")
            evidence_kind = raw.get("evidence_kind", "")
            evidence_id = raw.get("evidence_id", "")
            if state not in {"in_progress", "reviewed", "skipped", "verified"}:
                raise ValueError("Guide progress contains an unsupported step state.")
            if isinstance(updated_at, bool) or not isinstance(updated_at, (int, float)):
                raise ValueError("Guide progress timestamp is invalid.")
            try:
                finite_timestamp = math.isfinite(float(updated_at))
            except OverflowError:
                finite_timestamp = False
            if not finite_timestamp or updated_at <= 0:
                raise ValueError("Guide progress timestamp is invalid.")
            if not isinstance(evidence_kind, str) or not isinstance(evidence_id, str):
                raise ValueError("Guide progress evidence reference is invalid.")
            if state == "verified":
                if evidence_kind not in {"action_run", "troubleshooting_session"} or not _IDENTIFIER.fullmatch(evidence_id):
                    raise ValueError("Guide progress verified evidence is invalid.")
                if evidence_kind not in GUIDE_STEPS_BY_ID[key].evidence_kinds:
                    raise ValueError("Guide progress evidence does not match its step.")
            elif evidence_kind or evidence_id:
                raise ValueError("Only verified steps may contain evidence references.")
            entries[key] = GuideStepProgress(
                cast(ProgressStatus, state),
                float(updated_at),
                cast(EvidenceReferenceKind, evidence_kind),
                evidence_id,
            )
        return GuideProgressSnapshot(active_guide, active_step, entries, revision)

    def select(self, guide_id: str, step_id: str = "") -> GuideProgressSnapshot:
        guide = GUIDES_BY_ID.get(guide_id)
        if guide is None:
            raise ValueError("Unknown guide.")
        if step_id and step_id not in {step.id for step in guide.steps}:
            raise ValueError("Unknown step for this guide.")
        return self._write(active_guide=guide_id, active_step=step_id)

    def clear_active(self) -> GuideProgressSnapshot:
        """Clear the resume pointer while retaining reviewed step history."""
        return self._write(active_guide="", active_step="")

    def update_step(
        self,
        guide_id: str,
        step_id: str,
        state: ProgressStatus,
        *,
        evidence_kind: EvidenceKind = "action_run",
        evidence_id: str = "",
    ) -> GuideProgressSnapshot:
        if guide_id not in GUIDES_BY_ID or step_id not in {step.id for step in GUIDES_BY_ID[guide_id].steps}:
            raise ValueError("Unknown guide step.")
        if state not in {"in_progress", "reviewed", "skipped", "verified"}:
            raise ValueError("Unsupported guide step state.")
        if state == "verified":
            step = GUIDE_STEPS_BY_ID[step_id]
            if evidence_kind not in step.evidence_kinds or not _IDENTIFIER.fullmatch(evidence_id):
                raise ValueError("A compatible exact evidence reference is required.")
            if not guide_evidence_exists(evidence_kind, evidence_id):
                raise ValueError("The selected verified result is no longer available.")
        else:
            evidence_kind, evidence_id = "action_run", ""
        with advisory_lock(self.path):
            snapshot = self.read()
            if not snapshot.writable:
                raise UnsupportedFutureGuideSchema("Future guide progress is read-only.")
            entries = dict(snapshot.steps)
            entries[step_id] = GuideStepProgress(state, time.time(), evidence_kind if state == "verified" else "", evidence_id)
            self._write_unlocked(snapshot.revision + 1, guide_id, step_id, entries)
        return self.read()

    def _write(self, *, active_guide: str, active_step: str) -> GuideProgressSnapshot:
        with advisory_lock(self.path):
            snapshot = self.read()
            if not snapshot.writable:
                raise UnsupportedFutureGuideSchema("Future guide progress is read-only.")
            self._write_unlocked(snapshot.revision + 1, active_guide, active_step, snapshot.steps)
        return self.read()

    def _write_unlocked(
        self,
        revision: int,
        active_guide: str,
        active_step: str,
        entries: Mapping[str, GuideStepProgress],
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write_json(
            self.path,
            {
                "schema_id": GUIDE_SCHEMA_ID,
                "schema_version": GUIDE_SCHEMA_VERSION,
                "revision": revision,
                "active_guide": active_guide,
                "active_step": active_step,
                "steps": {key: value.to_dict() for key, value in sorted(entries.items())},
            },
            mode=0o600,
        )


@dataclass(frozen=True)
class GuideEvidence:
    kind: EvidenceKind
    id: str
    label: str
    timestamp: float


def guide_evidence(kind: EvidenceKind, limit: int = 30) -> tuple[GuideEvidence, ...]:
    """List actual successful action runs or completed inspections, read-only."""
    bounded_limit = max(1, min(int(limit), 100))
    try:
        if kind == "action_run":
            from core.actions.stores import ActionRunStore

            runs = ActionRunStore().list_read_only(limit=100, strict=True)
            return tuple(
                GuideEvidence(kind, run.run_id, f"{run.action_id} · {run.state}", run.completed_at or run.started_at)
                for run in reversed(runs)
                if run.state == "succeeded" and run.run_id and run.completed_at is not None
            )[:bounded_limit]
        if kind == "troubleshooting_session":
            from core.troubleshooting.storage import TroubleshootingSessionStore

            snapshot = TroubleshootingSessionStore().read()
            return tuple(
                GuideEvidence(kind, session.session_id, f"{session.profile_id} · {session.state}", session.completed_at or session.started_at)
                for session in snapshot.sessions
                if session.state == "completed" and session.completed_at is not None
            )[:bounded_limit]
    except (OSError, ValueError, RuntimeError, TypeError):
        return ()
    return ()


def guide_evidence_exists(kind: EvidenceReferenceKind, evidence_id: str) -> bool:
    """Re-read exact terminal evidence before accepting a verified link."""
    if kind not in {"action_run", "troubleshooting_session"}:
        return False
    return any(item.id == evidence_id for item in guide_evidence(cast(EvidenceKind, kind), limit=100))


def guide_progress_payload(guide_id: str, snapshot: GuideProgressSnapshot) -> dict[str, Any]:
    """Return one guide with honest, current evidence availability."""
    guide = GUIDES_BY_ID.get(guide_id)
    if guide is None:
        raise ValueError("Unknown guide.")
    steps: list[dict[str, Any]] = []
    for step in guide.steps:
        entry = snapshot.steps.get(step.id)
        status: str = entry.state if entry else "not_started"
        evidence_available = False
        if entry and entry.state == "verified":
            evidence_available = guide_evidence_exists(entry.evidence_kind, entry.evidence_id)
            if not evidence_available:
                status = "evidence_missing"
        steps.append({
            **step.to_dict(),
            "status": status,
            "updated_at": entry.updated_at if entry else None,
            "evidence_kind": entry.evidence_kind if entry else "",
            "evidence_id": entry.evidence_id if entry else "",
            "evidence_available": evidence_available,
        })
    return {
        "id": guide.id,
        "title": guide.title,
        "description": guide.description,
        "steps": steps,
        "active": snapshot.active_guide == guide.id,
        "writable": snapshot.writable,
        "reason_code": snapshot.reason_code,
    }


__all__ = [
    "GUIDE_SCHEMA_ID",
    "GUIDE_SCHEMA_VERSION",
    "GUIDES",
    "GUIDES_BY_ID",
    "GUIDE_STEPS_BY_ID",
    "GuideDefinition",
    "GuideEvidence",
    "GuideProgress",
    "GuideProgressSnapshot",
    "GuideProgressStore",
    "GuideStep",
    "GuideStepProgress",
    "GuideTarget",
    "guide_evidence",
    "guide_evidence_exists",
    "guide_progress_payload",
]
