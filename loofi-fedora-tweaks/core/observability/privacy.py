"""Privacy helpers for persisted and exported health snapshots."""

from __future__ import annotations

import os
import platform
import re
from typing import Any

_SECRET_KEY_RE = re.compile(r"(?i)(token|password|passwd|secret|api[_-]?key|private[_-]?key|access[_-]?key|credential)")
_SECRET_VALUE_RE = re.compile(r"(?i)(token|password|passwd|secret|api[_-]?key|private[_-]?key|access[_-]?key)=([^\s&]+)")
_HOME_RE = re.compile(r"/home/[^/\s]+")
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+)")


def _hostname_tokens() -> set[str]:
    tokens = {platform.node(), os.environ.get("HOSTNAME", "")}
    return {token for token in tokens if token and len(token) > 2}


def redact_text(text: str, *, limit: int = 6000) -> str:
    """Mask private values in free-form text."""
    masked = _HOME_RE.sub("/home/<user>", text or "")
    masked = _SECRET_VALUE_RE.sub(r"\1=<masked>", masked)
    masked = _EMAIL_RE.sub(r"\1***\2", masked)
    for hostname in _hostname_tokens():
        masked = masked.replace(hostname, "<masked-host>")
    return masked[:limit]


def redact_payload(value: Any, key_name: str = "") -> Any:
    """Recursively mask private values while preserving JSON shape."""
    if _SECRET_KEY_RE.search(key_name):
        return "<masked>"
    if isinstance(value, dict):
        return {str(key): redact_payload(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item, key_name) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item, key_name) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
