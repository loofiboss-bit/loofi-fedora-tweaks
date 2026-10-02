"""Structured fwupd candidate and history evidence (policy facts version 1)."""

from __future__ import annotations

import math
from typing import Any, Mapping

FIRMWARE_EVIDENCE_VERSION = 1


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return []
    return sorted({item.strip() for item in value if item.strip()})


def devices(payload: Any) -> list[Mapping[str, Any]]:
    """Accept only the documented device container, never recursive text matches."""
    raw = payload.get("Devices", []) if isinstance(payload, Mapping) else []
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def releases(device: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = device.get("Releases", [])
    if not raw and isinstance(device.get("Release"), Mapping):
        raw = [device["Release"]]
    return [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def candidates(payload: Any) -> list[dict[str, Any]]:
    """Bind the first fwupd update candidate to its device and release checksum."""
    records = []
    for device in devices(payload):
        identity = device.get("DeviceId", "")
        guids = _strings(device.get("Guid"))
        available = releases(device)
        if not isinstance(identity, str) or (not identity and not guids) or not available:
            raise ValueError("Firmware candidate identity or release is unavailable.")
        release = available[0]
        current = device.get("Version")
        target = release.get("Version")
        if not isinstance(current, str) or not current.strip() or not isinstance(target, str) or not target.strip() or current == target:
            raise ValueError("Firmware current or target version is unavailable or unchanged.")
        records.append({"device_id": identity, "guids": guids, "target_version": target,
                        "current_version": current, "checksums": _strings(release.get("Checksum", []))})
    return sorted(records, key=lambda item: (item["device_id"], item["guids"]))


def valid_facts(facts: Mapping[str, Any]) -> bool:
    records = facts.get("devices")
    if facts.get("firmware_evidence_version") != FIRMWARE_EVIDENCE_VERSION or not isinstance(records, list) or not records:
        return False
    for record in records:
        if not isinstance(record, Mapping):
            return False
        identity, guids = record.get("device_id"), record.get("guids")
        target, checksums = record.get("target_version"), record.get("checksums")
        current = record.get("current_version")
        if (not isinstance(identity, str) or not isinstance(guids, list) or guids != _strings(guids)
                or not (identity or guids) or not isinstance(target, str) or not target.strip()
                or not isinstance(current, str) or not current.strip() or current == target
                or not isinstance(checksums, list) or checksums != _strings(checksums)):
            return False
    return True


def history_status(record: Mapping[str, Any], payload: Any, *, started_at: float) -> str:
    """Require identity, release and update state on the same history device."""
    matched = []
    if not math.isfinite(started_at) or started_at <= 0:
        return "missing"

    def modified(device: Mapping[str, Any]) -> float:
        try:
            value = float(device.get("Modified", 0))
            return value if math.isfinite(value) else 0
        except (TypeError, ValueError):
            return 0

    for device in devices(payload):
        # fwupd records whole Unix seconds; missing/old evidence cannot prove this run.
        if modified(device) < math.floor(started_at):
            continue
        if record["device_id"]:
            identity_matches = device.get("DeviceId") == record["device_id"]
        else:
            identity_matches = bool(set(record["guids"]) & set(_strings(device.get("Guid"))))
        if not identity_matches:
            continue
        for release in releases(device):
            if release.get("Version") != record["target_version"]:
                continue
            if not set(record["checksums"]).issubset(_strings(release.get("Checksum", []))):
                continue
            matched.append(device)
            break
    if not matched:
        return "missing"
    # History may contain several attempts; a newer failure must not be hidden.

    latest = max(modified(device) for device in matched)
    states = {str(device.get("UpdateState", "unknown")).lower() for device in matched if modified(device) == latest}
    if states & {"3", "5", "failed", "failed-transient"}:
        return "failed"
    if states and states <= {"2", "success"}:
        return "success"
    return "pending"
