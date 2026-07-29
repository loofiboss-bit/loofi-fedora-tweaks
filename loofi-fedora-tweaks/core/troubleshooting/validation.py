"""Bounded, privacy-safe validation shared by troubleshooting contracts."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any


MAX_TEXT_LENGTH = 512
MAX_VALUE_TEXT_LENGTH = 256
MAX_PARAMETERS = 16
MAX_MAPPING_ITEMS = 32
MAX_SEQUENCE_ITEMS = 32
MAX_NESTING_DEPTH = 4
MAX_RESOURCES = 16
MAX_FINDINGS = 64
MAX_RELATED_CHANGES = 32
MAX_SESSIONS = 20
MAX_SESSION_FILE_BYTES = 512 * 1024

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")
_RESOURCE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,159}$")
_APPLICATION_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_FORBIDDEN_KEYS = frozenset(
    {
        "argv",
        "callback",
        "command",
        "command_preview",
        "command_vector",
        "credential",
        "executable",
        "password",
        "raw",
        "raw_output",
        "renderer",
        "runner",
        "secret",
        "stderr",
        "stdout",
        "token",
    }
)
_PERSONAL_PATH_FRAGMENTS = ("/home/", "/users/", "\\users\\")


def validate_identifier(value: str, *, field: str) -> str:
    """Return one stable lower-case identifier or reject it."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string identifier.")
    candidate = value
    if not _IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} must be a stable lower-case identifier.")
    return candidate


def validate_resource_identifier(value: str) -> str:
    """Reject paths and free-form resource values while allowing typed IDs."""
    if not isinstance(value, str):
        raise ValueError("Affected resources must be string identifiers.")
    candidate = value
    lowered = candidate.casefold()
    if (
        not _RESOURCE_IDENTIFIER.fullmatch(candidate)
        or candidate.startswith(("/", "\\"))
        or ".." in candidate
        or any(fragment in lowered for fragment in _PERSONAL_PATH_FRAGMENTS)
    ):
        raise ValueError("Affected resources must be privacy-safe typed identifiers.")
    return candidate


def validate_application_identifier(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("application_id must be a string.")
    candidate = value
    if not _APPLICATION_IDENTIFIER.fullmatch(candidate):
        raise ValueError("application_id must be a package name or Flatpak application ID.")
    return candidate


def validate_text(
    value: str,
    *,
    field: str,
    allow_empty: bool = False,
    maximum: int = MAX_TEXT_LENGTH,
) -> str:
    """Validate bounded display text without control characters."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")
    candidate = value
    if not allow_empty and not candidate.strip():
        raise ValueError(f"{field} is required.")
    if len(candidate) > maximum:
        raise ValueError(f"{field} exceeds the {maximum}-character limit.")
    if any(ord(character) < 32 and character not in "\t\n" for character in candidate):
        raise ValueError(f"{field} contains rejected control characters.")
    return candidate


def freeze_mapping(
    value: Mapping[str, Any] | None,
    *,
    field: str,
    max_items: int = MAX_MAPPING_ITEMS,
) -> tuple[tuple[str, Any], ...]:
    """Freeze a small JSON-like mapping after rejecting authority and secrets."""
    payload = value or {}
    if len(payload) > max_items:
        raise ValueError(f"{field} exceeds the {max_items}-item limit.")
    return tuple(
        (validate_identifier(str(key), field=f"{field} key"), _freeze(item, field=field, depth=1))
        for key, item in sorted(payload.items(), key=lambda pair: str(pair[0]))
        if _validate_key(str(key), field=field)
    )


def thaw(value: Any) -> Any:
    """Convert frozen JSON-like tuples back into plain serializable objects."""
    if isinstance(value, tuple):
        if all(
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], str)
            for item in value
        ):
            return {item[0]: thaw(item[1]) for item in value}
        return [thaw(item) for item in value]
    return value


def _validate_key(key: str, *, field: str) -> bool:
    lowered = key.casefold()
    if lowered in _FORBIDDEN_KEYS or any(part in _FORBIDDEN_KEYS for part in re.split(r"[-_.:]", lowered)):
        raise ValueError(f"{field} cannot contain authority, secret, or raw-output field '{key}'.")
    return True


def _freeze(value: Any, *, field: str, depth: int) -> Any:
    if depth > MAX_NESTING_DEPTH:
        raise ValueError(f"{field} exceeds the maximum nesting depth.")
    if callable(value):
        raise ValueError(f"{field} cannot contain callbacks or executable objects.")
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field} cannot contain non-finite numbers.")
        return value
    if isinstance(value, str):
        return validate_text(
            value,
            field=field,
            allow_empty=True,
            maximum=MAX_VALUE_TEXT_LENGTH,
        )
    if isinstance(value, Mapping):
        if len(value) > MAX_MAPPING_ITEMS:
            raise ValueError(f"{field} contains an oversized mapping.")
        return tuple(
            (
                validate_identifier(str(key), field=f"{field} key"),
                _freeze(item, field=field, depth=depth + 1),
            )
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if _validate_key(str(key), field=field)
        )
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
        if len(value) > MAX_SEQUENCE_ITEMS:
            raise ValueError(f"{field} contains an oversized sequence.")
        return tuple(_freeze(item, field=field, depth=depth + 1) for item in value)
    raise ValueError(f"{field} contains an unsupported value type.")
