"""Stable fingerprints for recurring maintenance problems."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from core.observability.privacy import redact_text


@dataclass(frozen=True)
class ProblemFingerprint:
    """A privacy-safe, stable problem identity."""

    id: str
    kind: str
    title: str
    summary: str
    source_id: str
    severity: str = "warning"
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "summary": self.summary,
            "source_id": self.source_id,
            "severity": self.severity,
            "evidence": dict(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProblemFingerprint":
        return cls(
            id=str(data.get("id", "")),
            kind=str(data.get("kind", "")),
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            source_id=str(data.get("source_id", "")),
            severity=str(data.get("severity", "warning")),
            evidence=dict(data.get("evidence", {}) if isinstance(data.get("evidence", {}), dict) else {}),
        )


def stable_fingerprint(kind: str, value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    digest = hashlib.sha256(f"{kind}:{normalized}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{digest}"


def normalize_journal_warning(line: str) -> str:
    """Normalize volatile journal fields before fingerprinting."""
    cleaned = redact_text(line)
    cleaned = re.sub(r"^\w{3}\s+\d+\s+\d+:\d+:\d+\s+", "", cleaned)
    cleaned = re.sub(r"\bpid=\d+\b", "pid=<n>", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[\d+\]", "[<n>]", cleaned)
    cleaned = re.sub(r"\b[0-9a-f]{8,}\b", "<hex>", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d+\b", "<n>", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _card_value(card: Any, attr: str, default: str = "") -> str:
    if isinstance(card, dict):
        return str(card.get(attr, default) or default)
    return str(getattr(card, attr, default) or default)


def _fingerprint_failed_services(card: Any) -> list[ProblemFingerprint]:
    details = _card_value(card, "details")
    items: list[ProblemFingerprint] = []
    for line in details.splitlines():
        parts = line.split()
        unit = next((part for part in parts if ".service" in part or ".timer" in part or ".socket" in part), "")
        if not unit:
            continue
        items.append(
            ProblemFingerprint(
                id=stable_fingerprint("failed-service", unit),
                kind="failed-service",
                title=f"Failed unit: {unit}",
                summary=f"{unit} is reported as failed.",
                source_id="failed-services",
                evidence={"unit": unit},
            )
        )
    return items


def _fingerprint_journal(card: Any) -> list[ProblemFingerprint]:
    details = _card_value(card, "details")
    normalized: dict[str, str] = {}
    for line in details.splitlines():
        line = line.strip()
        if not line:
            continue
        key = normalize_journal_warning(line)
        if key:
            normalized.setdefault(key, redact_text(line, limit=240))
    return [
        ProblemFingerprint(
            id=stable_fingerprint("journal-warning", key),
            kind="journal-warning",
            title="Recurring journal warning",
            summary="A normalized journal warning pattern was detected.",
            source_id="journal-warnings",
            evidence={"sample": sample},
        )
        for key, sample in normalized.items()
    ]


def _fingerprint_disk(card: Any) -> list[ProblemFingerprint]:
    details = _card_value(card, "details")
    for line in details.splitlines():
        match = re.search(r"\b(9[0-9]|100)%\b", line)
        if match:
            return [
                ProblemFingerprint(
                    id=stable_fingerprint("low-disk", "/"),
                    kind="low-disk",
                    title="Root filesystem is nearly full",
                    summary=f"Root filesystem usage is {match.group(0)}.",
                    source_id="disk-usage",
                    severity="warning",
                    evidence={"usage": match.group(0)},
                )
            ]
    return []


def fingerprints_from_cards(cards: Iterable[Any]) -> list[ProblemFingerprint]:
    """Build privacy-safe fingerprints from Daily Maintenance cards."""
    fingerprints: list[ProblemFingerprint] = []
    for card in cards:
        card_id = _card_value(card, "id")
        state = _card_value(card, "state", "success")
        if state in {"success", "preview_only", "unsupported"}:
            continue
        if card_id == "failed-services":
            fingerprints.extend(_fingerprint_failed_services(card))
        elif card_id == "journal-warnings":
            fingerprints.extend(_fingerprint_journal(card))
        elif card_id == "disk-usage":
            fingerprints.extend(_fingerprint_disk(card))
        elif card_id == "package-health":
            summary = _card_value(card, "summary")
            details = _card_value(card, "details")
            key = "dnf-lock" if "lock" in f"{summary} {details}".lower() else "package-health"
            fingerprints.append(
                ProblemFingerprint(
                    id=stable_fingerprint(key, summary or details or key),
                    kind=key,
                    title="Package manager health needs review",
                    summary=redact_text(summary or details or "Package manager health warning."),
                    source_id=card_id,
                    severity="blocked" if state == "blocked" else "warning",
                    evidence={"state": state},
                )
            )
        elif card_id == "rollback":
            fingerprints.append(
                ProblemFingerprint(
                    id=stable_fingerprint("missing-rollback", _card_value(card, "summary")),
                    kind="missing-rollback",
                    title="Rollback tool is not available",
                    summary=redact_text(_card_value(card, "summary")),
                    source_id=card_id,
                    evidence={"state": state},
                )
            )
        else:
            fingerprints.append(
                ProblemFingerprint(
                    id=stable_fingerprint(card_id or "maintenance-card", _card_value(card, "summary")),
                    kind=card_id or "maintenance-card",
                    title=_card_value(card, "title", "Maintenance issue"),
                    summary=redact_text(_card_value(card, "summary")),
                    source_id=card_id,
                    severity=state,
                    evidence={"state": state},
                )
            )
    deduped = {item.id: item for item in fingerprints}
    return list(deduped.values())
