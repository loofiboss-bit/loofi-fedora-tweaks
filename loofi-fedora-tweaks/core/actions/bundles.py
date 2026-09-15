"""Versioned action bundles used by the v29 Install and Tune workflows.

The bundle contract deliberately contains *references* to audited Action Center
definitions rather than command vectors.  Commands are rendered and checked by
``ActionCenterOrchestrator`` at execution time, which keeps a saved bundle
safe when the host or the catalog changes between review and execution.

Two execution policies are intentionally supported:

``continue_on_error``
    Used for independent application installs.  A failed application does not
    prevent the remaining applications from being attempted.

``stop_on_error``
    Used for ordered Tune profiles.  The first failed or blocked operation
    stops the profile and the remaining operations are reported as skipped.

No bundle policy retries an operation, rolls it back, or reboots the host.
Those decisions remain explicit recovery steps in the operation controller.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Literal, Mapping, Sequence, cast


BUNDLE_SCHEMA = "loofi.action-bundle/v1"
BUNDLE_SCHEMA_VERSION = 1
# More discoverable aliases for callers that refer to this object as a change
# set rather than a bundle.
ACTION_BUNDLE_SCHEMA = BUNDLE_SCHEMA
ACTION_BUNDLE_SCHEMA_VERSION = BUNDLE_SCHEMA_VERSION
ACTION_CHANGE_SET_SCHEMA = BUNDLE_SCHEMA
ACTION_CHANGE_SET_SCHEMA_VERSION = BUNDLE_SCHEMA_VERSION
CHANGE_SET_SCHEMA = BUNDLE_SCHEMA
CHANGE_SET_SCHEMA_VERSION = BUNDLE_SCHEMA_VERSION

BundleKind = Literal["application_install", "tune_profile"]
BundleExecutionPolicy = Literal["continue_on_error", "stop_on_error"]

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_ITEM_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_MAX_ITEMS = 128
_MAX_TITLE_LENGTH = 160
_MAX_DESCRIPTION_LENGTH = 1000
_KIND_ALIASES = {
    "app": "application_install",
    "apps": "application_install",
    "application": "application_install",
    "applications": "application_install",
    "application-install": "application_install",
    "application_install": "application_install",
    "install": "application_install",
    "tune": "tune_profile",
    "tuning": "tune_profile",
    "profile": "tune_profile",
    "tune-profile": "tune_profile",
    "tune_profile": "tune_profile",
}


class ActionBundleError(ValueError):
    """Base class for malformed or unsafe action bundle data."""


class ActionBundleValidationError(ActionBundleError):
    """Raised when a bundle or item violates the closed v29 contract."""


class ActionBundleSchemaError(ActionBundleError):
    """Raised when a bundle uses an unsupported schema or future version."""


class ActionBundleIntegrityError(ActionBundleError):
    """Raised when a persisted bundle digest does not match its contents."""


# Names used by integrations that call the versioned object a change set.
BundleValidationError = ActionBundleValidationError
BundleSchemaError = ActionBundleSchemaError
BundleIntegrityError = ActionBundleIntegrityError


def _normalise_kind(value: Any) -> BundleKind:
    key = str(value or "").strip().lower().replace(" ", "_")
    normalised = _KIND_ALIASES.get(key)
    if normalised is None:
        raise ActionBundleValidationError(
            "Bundle kind must be application_install or tune_profile."
        )
    return normalised  # type: ignore[return-value]


def _normalise_policy(value: Any, kind: BundleKind) -> BundleExecutionPolicy:
    expected: BundleExecutionPolicy = (
        "continue_on_error" if kind == "application_install" else "stop_on_error"
    )
    if value in (None, "", "default"):
        return expected
    normalised = str(value).strip().lower().replace("-", "_")
    if normalised not in {"continue_on_error", "stop_on_error"}:
        raise ActionBundleValidationError(
            "Bundle execution policy must be continue_on_error or stop_on_error."
        )
    if normalised != expected:
        raise ActionBundleValidationError(
            f"{kind} bundles must use {expected}; arbitrary execution ordering is not supported."
        )
    return normalised  # type: ignore[return-value]


def _validate_json(value: Any, *, field_name: str) -> None:
    try:
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ActionBundleValidationError(
            f"Bundle {field_name} must contain JSON-compatible values."
        ) from exc


def _copy_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ActionBundleValidationError(f"Bundle {field_name} must be an object.")
    result = {str(key): item for key, item in value.items()}
    _validate_json(result, field_name=field_name)
    return result


@dataclass(frozen=True)
class ActionBundleItem:
    """One ordered reference to a stable Action Center action ID.

    ``action_id`` is intentionally the first field so small integrations can
    create items as ``ActionBundleItem("install-application", parameters)``.
    ``item_id`` is generated by :class:`ActionBundle` when omitted and is used
    to correlate per-item outcomes without changing the stable action ID.
    """

    action_id: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    item_id: str = ""
    title: str = ""
    position: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        action_id = str(self.action_id).strip()
        if not _ID_PATTERN.fullmatch(action_id):
            raise ActionBundleValidationError(
                "Bundle item action_id must be a bounded stable action ID."
            )
        item_id = str(self.item_id).strip()
        if item_id and not _ITEM_ID_PATTERN.fullmatch(item_id):
            raise ActionBundleValidationError(
                "Bundle item item_id must be a bounded identifier."
            )
        if not isinstance(self.position, int) or isinstance(self.position, bool) or self.position < 0:
            raise ActionBundleValidationError("Bundle item position must be a non-negative integer.")
        title = str(self.title)
        if len(title) > _MAX_TITLE_LENGTH:
            raise ActionBundleValidationError("Bundle item title is too long.")
        parameters = _copy_mapping(self.parameters, field_name="item parameters")
        metadata = _copy_mapping(self.metadata, field_name="item metadata")
        object.__setattr__(self, "action_id", action_id)
        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "metadata", metadata)

    @property
    def id(self) -> str:
        """Compatibility spelling for integrations using ``id``."""
        return self.item_id

    def with_position(self, position: int, *, item_id: str | None = None) -> "ActionBundleItem":
        return replace(
            self,
            position=position,
            item_id=self.item_id if item_id is None else item_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "action_id": self.action_id,
            "parameters": dict(self.parameters),
            "title": self.title,
            "position": self.position,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ActionBundleItem":
        if not isinstance(payload, Mapping):
            raise ActionBundleValidationError("Each bundle item must be an object.")
        if "action_id" not in payload:
            raise ActionBundleValidationError("Each bundle item requires action_id.")
        parameters = payload.get("parameters", payload.get("params", {}))
        return cls(
            action_id=str(payload.get("action_id", "")),
            parameters=parameters if isinstance(parameters, Mapping) else parameters,
            item_id=str(payload.get("item_id", payload.get("id", ""))),
            title=str(payload.get("title", "")),
            position=payload.get("position", payload.get("order", 0)),
            metadata=payload.get("metadata", {}),
        )


def _coerce_item(value: ActionBundleItem | Mapping[str, Any] | str) -> ActionBundleItem:
    if isinstance(value, ActionBundleItem):
        return value
    if isinstance(value, Mapping):
        return ActionBundleItem.from_dict(value)
    return ActionBundleItem(str(value))


@dataclass(frozen=True)
class ActionBundle:
    """Versioned, reviewable change set for independent or ordered actions."""

    kind: BundleKind | str
    items: Sequence[ActionBundleItem | Mapping[str, Any] | str]
    bundle_id: str = ""
    title: str = ""
    description: str = ""
    execution_policy: BundleExecutionPolicy | str | None = None
    created_at: float = field(default_factory=time.time)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = BUNDLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        kind = _normalise_kind(self.kind)
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool):
            raise ActionBundleSchemaError("Bundle schema_version must be an integer.")
        if self.schema_version != BUNDLE_SCHEMA_VERSION:
            raise ActionBundleSchemaError(
                f"Unsupported action bundle schema version: {self.schema_version}."
            )
        bundle_id = str(self.bundle_id).strip()
        if bundle_id and not _ID_PATTERN.fullmatch(bundle_id):
            raise ActionBundleValidationError("Bundle bundle_id must be a bounded identifier.")
        title = str(self.title)
        description = str(self.description)
        if len(title) > _MAX_TITLE_LENGTH:
            raise ActionBundleValidationError("Bundle title is too long.")
        if len(description) > _MAX_DESCRIPTION_LENGTH:
            raise ActionBundleValidationError("Bundle description is too long.")
        try:
            created_at = float(self.created_at)
        except (TypeError, ValueError) as exc:
            raise ActionBundleValidationError("Bundle created_at must be numeric.") from exc
        if created_at < 0:
            raise ActionBundleValidationError("Bundle created_at cannot be negative.")
        items = tuple(_coerce_item(item) for item in self.items)
        if not items:
            raise ActionBundleValidationError("An action bundle must contain at least one item.")
        if len(items) > _MAX_ITEMS:
            raise ActionBundleValidationError(f"An action bundle cannot contain more than {_MAX_ITEMS} items.")
        normalised_items: list[ActionBundleItem] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(items):
            item_id = item.item_id or f"item-{index + 1}"
            if item_id in seen_ids:
                raise ActionBundleValidationError(f"Bundle item IDs must be unique: {item_id}.")
            seen_ids.add(item_id)
            # The persisted order is canonicalized to the user's selection
            # order.  A caller-provided position is retained when it is
            # already a valid monotonic sequence, otherwise it is normalized.
            position = item.position if item.position == index else index
            normalised_items.append(item.with_position(position, item_id=item_id))
        metadata = _copy_mapping(self.metadata, field_name="metadata")
        policy = _normalise_policy(self.execution_policy, kind)
        if not bundle_id:
            # The content digest gives an anonymous bundle a stable correlation
            # ID without adding a random value to a reviewable change set.
            bundle_id = f"bundle-{self._digest_for(kind, normalised_items, title, description, metadata, policy)[:16]}"
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "bundle_id", bundle_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "execution_policy", policy)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "items", tuple(normalised_items))
        object.__setattr__(self, "metadata", metadata)

    @property
    def is_application_bundle(self) -> bool:
        return self.kind == "application_install"

    @property
    def is_tune_profile(self) -> bool:
        return self.kind == "tune_profile"

    @property
    def continue_on_error(self) -> bool:
        return self.execution_policy == "continue_on_error"

    @property
    def stop_on_error(self) -> bool:
        return self.execution_policy == "stop_on_error"

    @property
    def digest(self) -> str:
        items = cast(tuple[ActionBundleItem, ...], self.items)
        return self._digest_for(
            self.kind,
            items,
            self.title,
            self.description,
            self.metadata,
            str(self.execution_policy or ""),
        )

    @staticmethod
    def _digest_for(
        kind: str,
        items: Sequence[ActionBundleItem],
        title: str,
        description: str,
        metadata: Mapping[str, Any],
        execution_policy: str = "",
    ) -> str:
        canonical = json.dumps(
            {
                "kind": kind,
                "items": [item.to_dict() for item in items],
                "title": title,
                "description": description,
                # The policy is integrity-bound: changing an independent app
                # batch into an ordered Tune run must invalidate the review.
                "execution_policy": execution_policy,
                "metadata": dict(metadata),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def validate(self, *, known_action_ids: Iterable[str] | None = None) -> list[str]:
        """Return non-throwing semantic validation errors for UI review.

        Structural validation happens during construction.  A catalog is an
        optional argument because bundles are also used for importing and
        reviewing saved plans before a catalog is initialized.
        """
        errors: list[str] = []
        if known_action_ids is not None:
            known = {str(action_id) for action_id in known_action_ids}
            items = cast(tuple[ActionBundleItem, ...], self.items)
            for item in items:
                if item.action_id not in known:
                    errors.append(f"unknown_action:{item.action_id}")
        return errors

    def assert_valid(self, *, known_action_ids: Iterable[str] | None = None) -> None:
        errors = self.validate(known_action_ids=known_action_ids)
        if errors:
            raise ActionBundleValidationError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        items = cast(tuple[ActionBundleItem, ...], self.items)
        return {
            "schema": BUNDLE_SCHEMA,
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "bundle_id": self.bundle_id,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "execution_policy": self.execution_policy,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
            "items": [item.to_dict() for item in items],
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ActionBundle":
        if not isinstance(payload, Mapping):
            raise ActionBundleValidationError("Persisted action bundle must be an object.")
        schema = payload.get("schema", payload.get("contract", ""))
        if schema and str(schema) not in {
            BUNDLE_SCHEMA,
            "loofi.action-change-set/v1",
            "loofi.action-bundle",
        }:
            raise ActionBundleSchemaError(f"Unsupported action bundle schema: {schema}")
        raw_version = payload.get("schema_version", payload.get("version", BUNDLE_SCHEMA_VERSION))
        try:
            version = int(raw_version)
        except (TypeError, ValueError) as exc:
            raise ActionBundleSchemaError("Action bundle schema version is invalid.") from exc
        if version != BUNDLE_SCHEMA_VERSION:
            raise ActionBundleSchemaError(f"Unsupported action bundle schema version: {version}.")
        raw_items = payload.get("items", payload.get("actions", []))
        if not isinstance(raw_items, (list, tuple)):
            raise ActionBundleValidationError("Persisted action bundle items must be a list.")
        bundle = cls(
            kind=str(payload.get("kind", "")),
            items=tuple(raw_items),
            bundle_id=str(payload.get("bundle_id", payload.get("id", ""))),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            execution_policy=payload.get("execution_policy"),
            created_at=payload.get("created_at", 0.0),
            metadata=payload.get("metadata", {}),
            schema_version=version,
        )
        persisted_digest = payload.get("digest")
        if persisted_digest is not None and str(persisted_digest) != bundle.digest:
            raise ActionBundleIntegrityError("Action bundle digest validation failed.")
        return bundle

    @classmethod
    def applications(
        cls,
        items: Sequence[ActionBundleItem | Mapping[str, Any] | str],
        *,
        bundle_id: str = "",
        title: str = "Install applications",
        description: str = "Review and install the selected applications independently.",
        metadata: Mapping[str, Any] | None = None,
    ) -> "ActionBundle":
        return cls(
            "application_install",
            items,
            bundle_id=bundle_id,
            title=title,
            description=description,
            metadata=metadata or {},
        )

    @classmethod
    def tune_profile(
        cls,
        items: Sequence[ActionBundleItem | Mapping[str, Any] | str],
        *,
        bundle_id: str = "",
        title: str = "Tune profile",
        description: str = "Review and apply the selected tuning operations in order.",
        metadata: Mapping[str, Any] | None = None,
    ) -> "ActionBundle":
        return cls(
            "tune_profile",
            items,
            bundle_id=bundle_id,
            title=title,
            description=description,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class BundleItemResult:
    """Durable projection of one bundle item's operation result."""

    item_id: str
    action_id: str
    status: str
    message: str
    plan_id: str = ""
    run_id: str = ""
    correlation_id: str = ""
    skipped: bool = False
    data: Mapping[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status in {"succeeded", "completed_verified", "verified"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "action_id": self.action_id,
            "status": self.status,
            "message": self.message,
            "plan_id": self.plan_id,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "skipped": self.skipped,
            "data": dict(self.data),
        }


@dataclass(frozen=True)
class BundleOutcome:
    """Aggregate result preserving every item result and skipped tail."""

    bundle_id: str
    kind: BundleKind
    execution_policy: BundleExecutionPolicy
    status: str
    message: str
    items: tuple[BundleItemResult, ...] = ()
    digest: str = ""
    recovery_guidance: str = ""

    @property
    def success(self) -> bool:
        return self.status == "succeeded"

    @property
    def partial(self) -> bool:
        return self.status == "partial_failure"

    @property
    def failed_items(self) -> tuple[BundleItemResult, ...]:
        return tuple(item for item in self.items if not item.success and not item.skipped)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": BUNDLE_SCHEMA,
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "bundle_id": self.bundle_id,
            "kind": self.kind,
            "execution_policy": self.execution_policy,
            "status": self.status,
            "message": self.message,
            "items": [item.to_dict() for item in self.items],
            "digest": self.digest,
            "recovery_guidance": self.recovery_guidance,
        }


# Public compatibility spellings used by consumers and tests.
ActionChangeSet = ActionBundle
ChangeSet = ActionBundle
ActionChangeSetItem = ActionBundleItem
ChangeSetItem = ActionBundleItem
ActionBundleResult = BundleOutcome


__all__ = [
    "ACTION_BUNDLE_SCHEMA",
    "ACTION_BUNDLE_SCHEMA_VERSION",
    "ACTION_CHANGE_SET_SCHEMA",
    "ACTION_CHANGE_SET_SCHEMA_VERSION",
    "ActionBundle",
    "ActionBundleError",
    "ActionBundleIntegrityError",
    "ActionBundleItem",
    "ActionBundleResult",
    "ActionBundleSchemaError",
    "ActionBundleValidationError",
    "ActionChangeSet",
    "ActionChangeSetItem",
    "BUNDLE_SCHEMA",
    "BUNDLE_SCHEMA_VERSION",
    "BundleExecutionPolicy",
    "BundleIntegrityError",
    "BundleItemResult",
    "BundleKind",
    "BundleOutcome",
    "BundleSchemaError",
    "BundleValidationError",
    "ChangeSet",
    "ChangeSetItem",
    "CHANGE_SET_SCHEMA",
    "CHANGE_SET_SCHEMA_VERSION",
]
