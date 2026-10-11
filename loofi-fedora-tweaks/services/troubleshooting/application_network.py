"""Bounded, read-only application and network troubleshooting probes.

The application log query is deliberately opt-in: callers must pass the
explicit confirmation received after the user has attempted a launch.
Only normalized counts and booleans are returned; command output is transient.
"""

from __future__ import annotations

import json
import ipaddress
import os
import re
import selectors
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable


_RPM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]{0,127}$")
_FLATPAK_REF = re.compile(r"^app/([A-Za-z0-9][A-Za-z0-9._-]{1,255})/([A-Za-z0-9_-]+)/([A-Za-z0-9._-]+)$")
_INSTALLATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_OUTPUT_LIMIT = 65536
_COMMAND_LIMIT = 2.0


@dataclass(frozen=True)
class ApplicationIdentity:
    """Exact selected package identity, including Flatpak installation scope."""

    source: str
    identifier: str
    installation: str = "system"

    def __post_init__(self) -> None:
        if self.source == "rpm":
            if not _RPM_ID.fullmatch(self.identifier) or self.installation != "system":
                raise ValueError("Invalid RPM application identity.")
        elif self.source == "flatpak":
            if not _FLATPAK_REF.fullmatch(self.identifier) or not _INSTALLATION.fullmatch(self.installation):
                raise ValueError("Invalid Flatpak application identity.")
        else:
            raise ValueError("Application source must be rpm or flatpak.")

    @property
    def application_id(self) -> str:
        """Return the selected Flatpak app ID or the RPM package name."""
        match = _FLATPAK_REF.fullmatch(self.identifier) if self.source == "flatpak" else None
        return match.group(1) if match else self.identifier


@dataclass(frozen=True)
class ProbeResult:
    """Normalized observations plus per-fact availability/error information."""

    facts: dict[str, Any]
    availability: dict[str, str]
    errors: dict[str, str]
    state: str
    reason_code: str = ""


class ApplicationNetworkProbe:
    """Collect one application or network snapshot without changing the host."""

    def __init__(
        self,
        *,
        runner: Callable[..., Any] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
        read_text: Callable[..., str] | None = None,
        bounded_runner: Callable[..., Any] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.runner = runner
        self.which = which
        self.read_text = read_text or _read_text
        self.bounded_runner = bounded_runner or _bounded_subprocess_run
        self.monotonic = monotonic

    def collect_application(
        self,
        identity: ApplicationIdentity,
        *,
        launch_attempted: bool,
        cancellation: Any,
        budget: float = 8.0,
    ) -> ProbeResult:
        """Check the selected installation and, only after user confirmation, its recent logs."""
        if not isinstance(identity, ApplicationIdentity):
            raise TypeError("An exact ApplicationIdentity is required.")
        deadline = self.monotonic() + min(max(0.0, budget), 8.0)
        facts: dict[str, Any] = {
            "installed": None,
            "recent_error_count": None,
            "recent_warning_count": None,
            "recent_matching_entry_count": None,
            "recent_metadata_match_count": None,
            "recent_message_match_count": None,
        }
        availability: dict[str, str] = {key: "unknown" for key in facts}
        errors: dict[str, str] = {}

        if identity.source == "rpm":
            vector = ["rpm", "-q", "--qf", "%{NAME}\\n", identity.identifier]
        else:
            # A successful, scoped inventory lets us distinguish an absent exact
            # ref from an inaccessible or failed Flatpak query (which also exits 1).
            vector = ["flatpak", _flatpak_installation_option(identity.installation), "list", "--app", "--columns=ref"]
        installation_parser = _installation_status if identity.source == "rpm" else lambda output: _flatpak_inventory_has_ref(output, identity.identifier)
        self._run_fact(
            "installed", vector, installation_parser, deadline, cancellation,
            facts, availability, errors,
            missing_exit_identifier=identity.identifier if identity.source == "rpm" else None,
        )

        if launch_attempted:
            self._run_fact(
                "recent_error_count",
                ["journalctl", "--user", "-b", "--since=-5min", "--lines=100", "--no-pager",
                 "--output=json", "--output-fields=PRIORITY,_COMM,_EXE,_SYSTEMD_USER_UNIT,SYSLOG_IDENTIFIER,MESSAGE",
                 f"--grep={re.escape(identity.application_id)}"],
                lambda output: _journal_summary(output, identity.application_id),
                deadline, cancellation, facts, availability, errors,
                paired_fact="recent_matching_entry_count", bounded_output=True,
            )
        else:
            availability["recent_error_count"] = "not_requested"
            availability["recent_warning_count"] = "not_requested"
            availability["recent_matching_entry_count"] = "not_requested"
            availability["recent_metadata_match_count"] = "not_requested"
            availability["recent_message_match_count"] = "not_requested"
        return _result(facts, availability, errors)

    def collect_network(self, *, cancellation: Any, budget: float = 8.0) -> ProbeResult:
        """Report separate local link, default-route, resolver and cached NM facts."""
        deadline = self.monotonic() + min(max(0.0, budget), 8.0)
        facts: dict[str, Any] = {
            "active_link": None,
            "default_route": None,
            "default_route_ipv4": None,
            "default_route_ipv6": None,
            "resolver_configured": None,
            "networkmanager_connectivity": None,
        }
        availability = {key: "unknown" for key in facts}
        errors: dict[str, str] = {}
        self._run_fact(
            "active_link", ["nmcli", "-g", "STATE", "device", "status"],
            _active_link, deadline, cancellation, facts, availability, errors,
        )
        self._run_fact(
            "default_route_ipv4", ["ip", "-j", "route", "show", "default"], _default_route,
            deadline, cancellation, facts, availability, errors,
        )
        self._run_fact(
            "default_route_ipv6", ["ip", "-6", "-j", "route", "show", "default"], _default_route,
            deadline, cancellation, facts, availability, errors,
        )
        ipv4_route, ipv6_route = facts["default_route_ipv4"], facts["default_route_ipv6"]
        if ipv4_route is True or ipv6_route is True:
            facts["default_route"] = True
            availability["default_route"] = "available"
        elif availability["default_route_ipv4"] == availability["default_route_ipv6"] == "available":
            facts["default_route"] = False
            availability["default_route"] = "available"
        else:
            facts["default_route"] = None
            availability["default_route"] = "unknown"
            errors["default_route"] = errors.get("default_route_ipv4", errors.get("default_route_ipv6", "probe-failed"))
        if cancellation.is_cancelled():
            availability["resolver_configured"] = "unknown"
            errors["resolver_configured"] = "cancelled"
        elif self.monotonic() >= deadline:
            availability["resolver_configured"] = "unknown"
            errors["resolver_configured"] = "timed-out"
        else:
            try:
                contents = self.read_text("/etc/resolv.conf", encoding="utf-8", errors="replace")
                if len(contents) > _OUTPUT_LIMIT:
                    raise ValueError
                facts["resolver_configured"] = _resolver_configured(contents)
                availability["resolver_configured"] = "available"
            except OSError:
                availability["resolver_configured"] = "unknown"
                errors["resolver_configured"] = "read-failed"
            except (TypeError, ValueError):
                availability["resolver_configured"] = "unknown"
                errors["resolver_configured"] = "invalid-response"
        self._run_fact(
            "networkmanager_connectivity", ["nmcli", "-t", "-f", "CONNECTIVITY", "general"],
            _connectivity, deadline, cancellation, facts, availability, errors,
        )
        return _result(facts, availability, errors)

    def _run_fact(
        self,
        key: str,
        vector: list[str],
        parser: Callable[[str], Any],
        deadline: float,
        cancellation: Any,
        facts: dict[str, Any],
        availability: dict[str, str],
        errors: dict[str, str],
        *,
        missing_exit_identifier: str | None = None,
        paired_fact: str | None = None,
        bounded_output: bool = False,
    ) -> None:
        if cancellation.is_cancelled():
            errors[key], availability[key] = "cancelled", "unknown"
            if paired_fact:
                errors[paired_fact], availability[paired_fact] = "cancelled", "unknown"
            return
        remaining = deadline - self.monotonic()
        if remaining <= 0:
            errors[key], availability[key] = "timed-out", "unknown"
            if paired_fact:
                errors[paired_fact], availability[paired_fact] = "timed-out", "unknown"
            return
        resolved = self.which(vector[0])
        if not resolved:
            errors[key], availability[key] = "tool-unavailable", "unknown"
            if paired_fact:
                errors[paired_fact], availability[paired_fact] = "tool-unavailable", "unknown"
            return
        try:
            command = [resolved, *vector[1:]]
            if bounded_output or self.runner is subprocess.run:
                result = self.bounded_runner(
                    command, capture_output=True, text=True, check=False,
                    timeout=min(_COMMAND_LIMIT, remaining), max_output_bytes=_OUTPUT_LIMIT,
                    cancellation=cancellation, monotonic=self.monotonic,
                    env={**os.environ, "LC_ALL": "C"},
                )
            else:
                result = self.runner(
                    command, capture_output=True, text=True, check=False,
                    timeout=min(_COMMAND_LIMIT, remaining), env={**os.environ, "LC_ALL": "C"},
                )
            if result.returncode != 0:
                if missing_exit_identifier and result.returncode == 1 and (
                    _rpm_reports_missing(result.stdout, missing_exit_identifier)
                    or _rpm_reports_missing(result.stderr, missing_exit_identifier)
                ):
                    facts[key], availability[key] = False, "available"
                    return
                raise _ProbeFailure("probe-failed")
            if len(result.stdout) > _OUTPUT_LIMIT:
                raise _ProbeFailure("invalid-response")
            parsed = parser(result.stdout)
            if paired_fact:
                facts[key], facts[paired_fact] = parsed["error_count"], parsed["entry_count"]
                availability[key] = "available"
                availability[paired_fact] = "available"
                for fact_key, parsed_key in (
                    ("recent_warning_count", "warning_count"),
                    ("recent_metadata_match_count", "metadata_match_count"),
                    ("recent_message_match_count", "message_match_count"),
                ):
                    facts[fact_key] = parsed[parsed_key]
                    availability[fact_key] = "available"
            else:
                facts[key] = parsed
            availability[key] = "available"
        except subprocess.TimeoutExpired:
            _mark_error(key, "timed-out", availability, errors)
            if paired_fact:
                _mark_error(paired_fact, "timed-out", availability, errors)
        except _ProbeFailure as failure:
            _mark_error(key, failure.reason, availability, errors)
            if paired_fact:
                _mark_error(paired_fact, failure.reason, availability, errors)
        except (OSError, subprocess.SubprocessError):
            _mark_error(key, "probe-failed", availability, errors)
            if paired_fact:
                _mark_error(paired_fact, "probe-failed", availability, errors)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            _mark_error(key, "invalid-response", availability, errors)
            if paired_fact:
                _mark_error(paired_fact, "invalid-response", availability, errors)


class _ProbeFailure(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _mark_error(key: str, reason: str, availability: dict[str, str], errors: dict[str, str]) -> None:
    keys = (
        ("recent_error_count", "recent_warning_count", "recent_matching_entry_count",
         "recent_metadata_match_count", "recent_message_match_count")
        if key.startswith("recent_") else (key,)
    )
    for fact_key in keys:
        if fact_key in availability:
            availability[fact_key], errors[fact_key] = "unknown", reason


def _result(facts: dict[str, Any], availability: dict[str, str], errors: dict[str, str]) -> ProbeResult:
    usable = any(state == "available" for state in availability.values())
    state = "partial" if usable and errors else "completed" if usable else "unavailable"
    reason = "cancelled" if "cancelled" in errors.values() else "timed-out" if "timed-out" in errors.values() else next(iter(errors.values()), "")
    return ProbeResult(facts, availability, errors, state, reason)


def _installation_status(output: str) -> bool:
    # RPM query output is the exact selected package name.
    if not _RPM_ID.fullmatch(output.strip()):
        raise ValueError("Unexpected RPM installation response.")
    return True


def _rpm_reports_missing(output: str, package_name: str) -> bool:
    """Recognize only RPM's exact absent-package response, regardless of stream."""
    return output.strip() == f"package {package_name} is not installed"


def _flatpak_inventory_has_ref(output: str, expected_ref: str) -> bool:
    if len(output) > _OUTPUT_LIMIT:
        raise ValueError("Flatpak inventory exceeds the bounded limit.")
    refs = output.splitlines()
    if len(refs) > 4096 or any(not _FLATPAK_REF.fullmatch(ref) for ref in refs):
        raise ValueError("Flatpak returned an invalid installation inventory.")
    return expected_ref in refs


def _flatpak_installation_option(installation: str) -> str:
    if installation in {"user", "system"}:
        return f"--{installation}"
    if not _INSTALLATION.fullmatch(installation):
        raise ValueError("Invalid Flatpak installation identifier.")
    return f"--installation={installation}"


def _journal_summary(output: str, application_id: str) -> dict[str, int]:
    entries = output.splitlines()
    if len(entries) > 100:
        raise ValueError("Journal response exceeds the bounded limit.")
    errors = 0
    warnings = 0
    metadata_matches = 0
    for line in entries:
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError("Invalid journal record.")
        priority = record.get("PRIORITY")
        if not isinstance(priority, str) or not priority.isdigit() or not 0 <= int(priority) <= 7:
            raise ValueError("Journal entry has no valid priority.")
        errors += int(int(priority) <= 3)
        warnings += int(int(priority) == 4)
        metadata = " ".join(record[field] for field in (
            "_COMM", "_EXE", "_SYSTEMD_USER_UNIT", "SYSLOG_IDENTIFIER",
        ) if isinstance(record.get(field), str))
        metadata_matches += int(application_id.casefold() in metadata.casefold())
    return {
        "entry_count": len(entries),
        "error_count": errors,
        "warning_count": warnings,
        "metadata_match_count": metadata_matches,
        "message_match_count": len(entries) - metadata_matches,
    }


def _active_link(output: str) -> bool:
    lines = output.splitlines()
    if len(lines) > 128:
        raise ValueError("Network device response exceeds the bounded limit.")
    connected = False
    for line in lines:
        state = line.strip()
        if not state or not any(state == item or state.startswith(item + " (") for item in ("connected", "disconnected", "connecting", "unavailable", "unmanaged")):
            raise ValueError("Invalid NetworkManager device response.")
        connected = connected or state == "connected" or state.startswith("connected (")
    return connected


def _default_route(output: str) -> bool:
    routes = json.loads(output)
    if not isinstance(routes, list) or len(routes) > 256:
        raise ValueError("Invalid default route response.")
    if any(not isinstance(route, dict) or route.get("dst") != "default" for route in routes):
        raise ValueError("Invalid default route entry.")
    return bool(routes)


def _resolver_configured(output: str) -> bool:
    for line in output.splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) == 2 and fields[0] == "nameserver":
            try:
                ipaddress.ip_address(fields[1])
                return True
            except ValueError:
                continue
    return False


def _connectivity(output: str) -> str:
    value = output.strip()
    if value not in {"unknown", "none", "portal", "limited", "full"}:
        raise ValueError("Invalid cached NetworkManager connectivity state.")
    return value


def _read_text(path: str, **kwargs: Any) -> str:
    with open(path, "r", **kwargs) as stream:
        return str(stream.read(_OUTPUT_LIMIT + 1))


def _bounded_subprocess_run(
    command: list[str],
    *,
    timeout: float,
    max_output_bytes: int,
    cancellation: Any,
    monotonic: Callable[[], float],
    env: dict[str, str],
    **_kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Read child stdout incrementally and terminate it before exceeding the byte cap."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    output = bytearray()
    deadline = monotonic() + timeout
    registered = True
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while True:
            if cancellation.is_cancelled():
                raise _ProbeFailure("cancelled")
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            events = selector.select(min(0.05, remaining)) if registered else ()
            if events:
                chunk = os.read(process.stdout.fileno(), min(4096, max_output_bytes - len(output) + 1))
                if not chunk:
                    selector.unregister(process.stdout)
                    registered = False
                else:
                    output.extend(chunk)
                    if len(output) > max_output_bytes:
                        raise _ProbeFailure("output-too-large")
            if not registered:
                if process.poll() is not None:
                    break
                time.sleep(min(0.01, remaining))
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        returncode = process.wait(timeout=remaining)
        return subprocess.CompletedProcess(command, returncode, output.decode("utf-8"), "")
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
        process.stdout.close()
