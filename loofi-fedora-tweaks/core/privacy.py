"""Shared privacy helpers for persisted and exported domain evidence."""

from __future__ import annotations

import ipaddress
import os
import platform
import re
from typing import Any

_SECRET_KEY_RE = re.compile(r"(?i)(token|password|passwd|secret|api[_-]?key|private[_-]?key|access[_-]?key|credential)")
_SECRET_VALUE_RE = re.compile(r"(?i)(token|password|passwd|secret|api[_-]?key|private[_-]?key|access[_-]?key)=([^\s&]+)")
_HOME_RE = re.compile(r"/home/[^/\s]+")
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+)")
_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6_CANDIDATE_RE = re.compile(
    r"(?<![0-9A-Fa-f:])\[?[0-9A-Fa-f:]*:[0-9A-Fa-f:]+\]?(?![0-9A-Fa-f:])"
)
_MAC_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])")


def _hostname_tokens() -> set[str]:
    tokens = {platform.node(), os.environ.get("HOSTNAME", "")}
    return {token for token in tokens if token and len(token) > 2}


def _mask_ipv6_candidate(match: re.Match[str]) -> str:
    candidate = match.group(0)
    normalized = candidate.strip("[]")
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return candidate
    return "<masked-ip>" if address.version == 6 else candidate


def redact_text(text: str, *, limit: int = 6000) -> str:
    """Mask private values in free-form text."""
    masked = _HOME_RE.sub("/home/<user>", text or "")
    masked = _SECRET_VALUE_RE.sub(r"\1=<masked>", masked)
    masked = _EMAIL_RE.sub(r"\1***\2", masked)
    masked = _MAC_RE.sub("<masked-mac>", masked)
    masked = _IPV4_RE.sub("<masked-ip>", masked)
    masked = _IPV6_CANDIDATE_RE.sub(_mask_ipv6_candidate, masked)
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
