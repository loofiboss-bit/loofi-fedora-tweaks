"""Explicit, read-only update discovery; cached observations never authorize actions."""

from __future__ import annotations

import json
import os
import selectors
import time
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal
from threading import Event

from core.actions.catalog import SystemActionRuntime
from core.actions.contracts import ActionRuntime
from core.executor.action_result import ActionResult
from core.platform.profile import DeploymentBackend, PlatformProfile
from core.state.atomic_io import advisory_lock, atomic_write_json
from core.state.paths import StatePaths

Source = Literal["system", "flatpak", "firmware"]
Status = Literal["unchecked", "up_to_date", "available", "missing_tool", "unsupported", "error"]
SOURCES: tuple[Source, ...] = ("system", "flatpak", "firmware")
STATUSES = {"unchecked", "up_to_date", "available", "missing_tool", "unsupported", "error"}
MAX_ITEMS = 5000
MAX_BYTES = 4 * 1024 * 1024
STALE_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class UpdateItem:
    name: str
    version: str = ""
    old_version: str = ""


@dataclass(frozen=True)
class UpdateSourceResult:
    source: Source
    status: Status = "unchecked"
    checked_at: str = ""
    items: tuple[UpdateItem, ...] = ()
    reboot_required: bool | None = None
    error_code: str = ""
    stale: bool = True


@dataclass(frozen=True)
class UpdateOverviewSnapshot:
    sources: tuple[UpdateSourceResult, ...] = tuple(UpdateSourceResult(source) for source in SOURCES)
    system_mode: str = "unknown"
    storage_status: str = "ok"
    backend: str = DeploymentBackend.UNKNOWN.value
    support_status: str = "unknown"


class OverviewCancelled(Exception):
    """The application is closing; observations must not be persisted."""


class OverviewRuntime(SystemActionRuntime):
    """Closed query vectors with bounded pipe reads and a deterministic locale."""

    _QUERIES = {
        ("dnf", "check-update", "--quiet"),
        ("dnf5", "check-update", "--quiet"),
        ("rpm-ostree", "upgrade", "--preview"),
        ("flatpak", "remote-ls", "--updates", "--columns=ref,commit"),
        ("fwupdmgr", "get-updates", "--json"),
    }

    def __init__(self, facade, system_manager=None, *, cancelled: Event | None = None):
        super().__init__(facade, system_manager)
        self.cancelled = cancelled or Event()

    def _check_cancelled(self) -> None:
        if self.cancelled.is_set():
            raise OverviewCancelled()

    def execute_read_only(self, vector, *, action_id: str, timeout: int = 30) -> ActionResult:
        if tuple(vector) not in self._QUERIES:
            return ActionResult(False, "Unsupported overview query", exit_code=126, action_id=action_id)
        self._check_cancelled()
        output = {"stdout": bytearray(), "stderr": bytearray()}
        process = None
        try:
            process = subprocess.Popen(
                list(vector), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            )
            assert process.stdout is not None and process.stderr is not None
            deadline = time.monotonic() + max(1, min(timeout, 120))
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                while selector.get_map():
                    self._check_cancelled()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(vector, timeout)
                    for key, _ in selector.select(min(remaining, 0.2)):
                        limit = MAX_BYTES if key.data == "stdout" else 65536
                        chunk = os.read(key.fd, min(65536, limit - len(output[key.data]) + 1))
                        if not chunk:
                            selector.unregister(key.fileobj)
                        else:
                            output[key.data].extend(chunk)
                            if len(output[key.data]) > limit:
                                return ActionResult(False, "Overview output limit exceeded", exit_code=-2, action_id=action_id)
                while True:
                    self._check_cancelled()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(vector, timeout)
                    try:
                        code = process.wait(timeout=min(0.2, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        continue
            return ActionResult(
                code == 0, "Overview query completed", code,
                stdout=output["stdout"].decode("utf-8", errors="replace"),
                stderr=output["stderr"].decode("utf-8", errors="replace"),
                action_id=action_id,
            )
        except subprocess.TimeoutExpired:
            return ActionResult(False, "Overview query timed out", exit_code=-1, action_id=action_id)
        except FileNotFoundError:
            return ActionResult(False, "Overview tool missing", exit_code=127, action_id=action_id)
        except OSError:
            return ActionResult(False, "Overview query failed", exit_code=1, action_id=action_id)
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                for pipe in (process.stdout, process.stderr):
                    if pipe is not None:
                        pipe.close()


class UpdateOverviewService:
    """Load without probes; check all sources independently only on explicit request."""

    def __init__(
        self,
        runtime: ActionRuntime | None = None,
        path: Path | None = None,
        clock: Callable[[], datetime] | None = None,
        which: Callable[[str], str | None] | None = None,
    ):
        self._cancelled = Event()
        self._runtime = runtime
        if isinstance(runtime, OverviewRuntime):
            runtime.cancelled = self._cancelled
        self.path = path if path is not None else StatePaths.from_environment().cache / "update-overview.json"
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._which = which or shutil.which

    def cancel(self) -> None:
        """Cooperatively stop the current check on application shutdown."""
        self._cancelled.set()

    def reset_cancel(self) -> None:
        """Allow a deliberate new check after a previous check was cancelled."""
        self._cancelled.clear()

    def _check_cancelled(self) -> None:
        if self._cancelled.is_set():
            raise OverviewCancelled()

    def _read(self) -> dict:
        with self.path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Oversized overview")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Invalid overview")
        return payload

    def load(self) -> UpdateOverviewSnapshot:
        """Return persisted observations, including freshness, without creating files."""
        try:
            payload = self._read()
            version = payload.get("schema_version")
            if type(version) is not int:
                raise ValueError("Invalid schema")
            if version > 2:
                return UpdateOverviewSnapshot(storage_status="future_schema")
            if version not in {1, 2} or payload.get("system_mode") not in {"traditional", "atomic", "bootc", "unknown"}:
                raise ValueError("Invalid schema")
            records = payload.get("sources")
            if not isinstance(records, list) or len(records) != len(SOURCES):
                raise ValueError("Invalid sources")
            sources = tuple(self._decode_source(record) for record in records)
            if tuple(source.source for source in sources) != SOURCES:
                raise ValueError("Invalid source order")
            if version == 1:
                # v27 caches contain useful observations but no trustworthy
                # backend identity. Keep them visible while requiring a new
                # check before they can unlock an update review.
                sources = tuple(replace(source, stale=True) for source in sources)
                return UpdateOverviewSnapshot(
                    sources=sources,
                    system_mode=payload["system_mode"],
                    storage_status="legacy_schema",
                    backend=DeploymentBackend.UNKNOWN.value,
                    support_status="unknown",
                )
            backend = payload.get("backend", DeploymentBackend.UNKNOWN.value)
            if backend not in {item.value for item in DeploymentBackend}:
                raise ValueError("Invalid backend")
            support_status = payload.get("support_status", "unknown")
            if support_status not in {"supported", "preview", "unknown"}:
                raise ValueError("Invalid support status")
            return UpdateOverviewSnapshot(
                sources=sources,
                system_mode=payload["system_mode"],
                backend=str(backend),
                support_status=str(support_status),
            )
        except FileNotFoundError:
            return UpdateOverviewSnapshot()
        except (OSError, ValueError, TypeError, KeyError):
            return UpdateOverviewSnapshot(storage_status="unavailable")

    def _decode_source(self, record: dict) -> UpdateSourceResult:
        if not isinstance(record, dict) or record.get("source") not in SOURCES or record.get("status") not in STATUSES:
            raise ValueError("Invalid source")
        items = record.get("items")
        if not isinstance(items, list) or len(items) > MAX_ITEMS:
            raise ValueError("Invalid items")
        parsed = []
        for item in items:
            if not isinstance(item, dict) or set(item) != {"name", "version", "old_version"}:
                raise ValueError("Invalid item")
            if any(not isinstance(value, str) or len(value) > 512 for value in item.values()):
                raise ValueError("Invalid item text")
            parsed.append(UpdateItem(**item))
        checked = record.get("checked_at", "")
        if not isinstance(checked, str) or len(checked) > 64:
            raise ValueError("Invalid timestamp")
        reboot = record.get("reboot_required")
        if reboot is not None and type(reboot) is not bool:
            raise ValueError("Invalid reboot state")
        error = record.get("error_code", "")
        if not isinstance(error, str) or len(error) > 64:
            raise ValueError("Invalid error")
        if (record["status"] == "available") != bool(parsed):
            raise ValueError("Inconsistent candidate status")
        return UpdateSourceResult(record["source"], record["status"], checked, tuple(parsed), reboot, error, self._stale(checked))

    def _stale(self, checked: str) -> bool:
        if not checked:
            return True
        timestamp = datetime.fromisoformat(checked)
        if timestamp.tzinfo is None:
            raise ValueError("Timezone required")
        age = (self._clock() - timestamp).total_seconds()
        return age < 0 or age >= STALE_SECONDS

    def _resolve_backend(self) -> tuple[DeploymentBackend, object | None, bool]:
        """Resolve one typed backend; the bool marks the legacy test fallback."""
        assert self._runtime is not None
        profile_reader = getattr(self._runtime, "platform_profile", None)
        if callable(profile_reader):
            try:
                profile = profile_reader()
            except (OSError, RuntimeError, TypeError, ValueError):
                profile = None
            raw_backend = getattr(profile, "deployment_backend", None)
            if isinstance(raw_backend, DeploymentBackend):
                return raw_backend, profile, False
            if isinstance(raw_backend, str):
                try:
                    return DeploymentBackend(raw_backend), profile, False
                except ValueError:
                    pass
        try:
            return (
                DeploymentBackend.RPM_OSTREE
                if bool(self._runtime.is_atomic())
                else self._legacy_dnf_backend(),
                None,
                True,
            )
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            return DeploymentBackend.UNKNOWN, None, True

    def _legacy_dnf_backend(self) -> DeploymentBackend:
        runtime = self._runtime
        assert runtime is not None
        manager = str(runtime.package_manager()).strip().lower()
        if manager in {"dnf", "dnf5"}:
            return DeploymentBackend.DNF5
        if manager == "rpm-ostree":
            return DeploymentBackend.RPM_OSTREE
        if manager == "bootc":
            return DeploymentBackend.BOOTC
        return DeploymentBackend.UNKNOWN

    @staticmethod
    def _system_mode(backend: DeploymentBackend) -> str:
        return {
            DeploymentBackend.DNF5: "traditional",
            DeploymentBackend.RPM_OSTREE: "atomic",
            DeploymentBackend.BOOTC: "bootc",
            DeploymentBackend.UNKNOWN: "unknown",
        }[backend]

    def check(
        self,
        *,
        sources: tuple[Source, ...] = SOURCES,
        on_source_result: Callable[[UpdateOverviewSnapshot], None] | None = None,
    ) -> UpdateOverviewSnapshot:
        """Refresh sources independently and publish each completed result.

        Real platform runtimes use at most three concurrent read-only probes.
        Legacy injected runtimes stay sequential for compatibility with older
        integrations and deterministic tests.
        """
        self._check_cancelled()
        if self._runtime is None:
            from core.executor.command_facade import CommandFacade

            self._runtime = OverviewRuntime(CommandFacade(), cancelled=self._cancelled)
        backend, profile, legacy_runtime = self._resolve_backend()
        mode = self._system_mode(backend)
        support_status = (
            "supported"
            if legacy_runtime
            else str(getattr(profile, "support_status", "unknown"))
        )
        if support_status not in {"supported", "preview", "unknown"}:
            support_status = "unknown"
        previous = self.load()
        results = {item.source: item for item in previous.sources}
        storage_status = "ok"

        def publish(source_result: UpdateSourceResult) -> None:
            nonlocal storage_status
            previous_result = results.get(source_result.source)
            if (
                source_result.status in {"error", "missing_tool", "unsupported"}
                and previous_result is not None
                and previous_result.items
            ):
                # A failed probe is not evidence that a previously observed
                # candidate disappeared. Keep that observation visible while
                # exposing the current failure status to the UI and callers.
                source_result = replace(
                    source_result,
                    items=previous_result.items,
                    reboot_required=previous_result.reboot_required,
                )
            results[source_result.source] = source_result
            candidate = UpdateOverviewSnapshot(
                sources=tuple(results[source] for source in SOURCES),
                system_mode=mode,
                storage_status=storage_status,
                backend=backend.value,
                support_status=support_status,
            )
            if not legacy_runtime:
                saved = self._persist(candidate)
                if saved.storage_status != "ok":
                    storage_status = saved.storage_status
                    candidate = replace(candidate, storage_status=storage_status)
            if on_source_result is not None:
                try:
                    on_source_result(candidate)
                except (RuntimeError, TypeError, ValueError):
                    pass

        selected_sources = tuple(source for source in SOURCES if source in sources)
        if legacy_runtime:
            for source in selected_sources:
                self._check_cancelled()
                publish(
                    self._check_source(
                        source,
                        backend,
                        profile=profile,
                        support_status=support_status,
                    )
                )
        else:
            with ThreadPoolExecutor(max_workers=min(3, max(1, len(selected_sources)))) as executor:
                futures = {
                    executor.submit(
                        self._check_source,
                        source,
                        backend,
                        profile=profile,
                        support_status=support_status,
                    ): source
                    for source in selected_sources
                }
                for future in as_completed(futures):
                    self._check_cancelled()
                    publish(future.result())
        self._check_cancelled()
        snapshot = UpdateOverviewSnapshot(
            sources=tuple(results[source] for source in SOURCES),
            system_mode=mode,
            storage_status=storage_status,
            backend=backend.value,
            support_status=support_status,
        )
        return self._persist(snapshot) if legacy_runtime else snapshot

    def _persist(self, snapshot: UpdateOverviewSnapshot) -> UpdateOverviewSnapshot:
        """Write one schema-versioned snapshot without replacing future data."""
        try:
            with advisory_lock(self.path):
                self._check_cancelled()
                try:
                    payload = self._read()
                except FileNotFoundError:
                    payload = {}
                if isinstance(payload.get("schema_version"), int) and payload["schema_version"] > 2:
                    return replace(snapshot, storage_status="future_schema")
                if payload.get("schema_version") == 2 and (
                    "backend" not in payload or "sources" not in payload
                ):
                    return replace(snapshot, storage_status="future_schema")
                saved = {
                    "schema_version": 2,
                    "backend": snapshot.backend,
                    "support_status": snapshot.support_status,
                    "system_mode": snapshot.system_mode,
                    "sources": [asdict(source) for source in snapshot.sources],
                }
                if len(json.dumps(saved, indent=2, sort_keys=True).encode("utf-8")) > MAX_BYTES:
                    return replace(snapshot, storage_status="unavailable")
                self._check_cancelled()
                atomic_write_json(self.path, saved)
        except (OSError, ValueError, TypeError):
            return replace(snapshot, storage_status="unavailable")
        return snapshot

    def _check_source(
        self,
        source: Source,
        backend: DeploymentBackend | str,
        *,
        profile: object | None = None,
        support_status: str = "supported",
    ) -> UpdateSourceResult:
        if not isinstance(backend, DeploymentBackend):
            try:
                backend = DeploymentBackend(str(backend))
            except ValueError:
                backend = DeploymentBackend.UNKNOWN
        checked = self._clock().isoformat()
        base = UpdateSourceResult(source, checked_at=checked, stale=False)
        try:
            assert self._runtime is not None
            if source == "system":
                if support_status == "unknown":
                    return replace(base, status="unsupported", error_code="fedora_release_unknown")
                if backend is DeploymentBackend.UNKNOWN:
                    return replace(base, status="unsupported", error_code="backend_unknown")
                if backend is DeploymentBackend.BOOTC:
                    return replace(base, status="unsupported", error_code="bootc_manual_guidance")
                if backend is DeploymentBackend.RPM_OSTREE:
                    tool = "rpm-ostree"
                elif isinstance(profile, PlatformProfile):
                    tool = profile.package_manager_name
                elif profile is not None:
                    tool = str(
                        getattr(profile, "package_manager_command", "")
                        or getattr(profile, "package_manager_name", "dnf5")
                    )
                else:
                    tool = str(self._runtime.package_manager())
                if tool not in {"dnf", "dnf5", "rpm-ostree"}:
                    return replace(base, status="unsupported", error_code="package_manager_unsupported")
                vector = [tool, "upgrade", "--preview"] if backend is DeploymentBackend.RPM_OSTREE else [tool, "check-update", "--quiet"]
            elif source == "flatpak":
                tool = "flatpak"
                vector = [tool, "remote-ls", "--updates", "--columns=ref,commit"]
            else:
                tool = "fwupdmgr"
                vector = [tool, "get-updates", "--json"]
            if not self._which(tool):
                return replace(base, status="missing_tool", error_code="missing_tool")
            self._check_cancelled()
            result = self._runtime.execute_read_only(vector, action_id=f"update-overview-{source}", timeout=120 if source == "system" else 90)
            if result.exit_code == -2:
                return replace(base, status="error", error_code="output_truncated")
            if len(result.stdout.encode("utf-8")) > MAX_BYTES:
                raise ValueError("Oversized output")
            if result.exit_code == 127:
                return replace(base, status="missing_tool", error_code="missing_tool")
            if result.exit_code == -1:
                return replace(base, status="error", error_code="timeout")
            if source == "firmware":
                return self._firmware(base, result)
            accepted = {0, 100} if source == "system" and backend is DeploymentBackend.DNF5 else {0}
            if result.exit_code not in accepted and not (result.exit_code is None and result.success):
                return replace(base, status="error", error_code="timeout" if result.exit_code == -1 else "query_failed")
            reboot: bool | None
            if source == "flatpak":
                items = self._flatpak(result.stdout)
                reboot = False
            elif backend is DeploymentBackend.RPM_OSTREE:
                items = self._atomic(result.stdout)
                reboot = True if items else None
            else:
                items = self._dnf(result.stdout)
                if result.exit_code == 100 and not items:
                    raise ValueError("Missing DNF candidates")
                reboot = None
            self._validate_items(items)
            return replace(base, status="available" if items else "up_to_date", items=tuple(items), reboot_required=reboot)
        except FileNotFoundError:
            return replace(base, status="missing_tool", error_code="missing_tool")
        except (TimeoutError, subprocess.TimeoutExpired):
            return replace(base, status="error", error_code="timeout")
        except (ValueError, TypeError, KeyError):
            return replace(base, status="error", error_code="invalid_output")
        except (OSError, RuntimeError):
            return replace(base, status="error", error_code="query_failed")

    @staticmethod
    def _validate_items(items: list[UpdateItem]) -> None:
        if len(items) > MAX_ITEMS or any(not item.name or any(len(value) > 512 for value in (item.name, item.version, item.old_version)) for item in items):
            raise ValueError("Invalid candidates")

    @staticmethod
    def _dnf(output: str) -> list[UpdateItem]:
        items = []
        for line in output.splitlines():
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) != 3 or not re.fullmatch(r"[A-Za-z0-9_+.:~-]+\.[A-Za-z0-9_]+", fields[0]):
                raise ValueError("Invalid DNF candidate")
            items.append(UpdateItem(fields[0], fields[1]))
        return items

    @staticmethod
    def _flatpak(output: str) -> list[UpdateItem]:
        items = []
        for line in output.splitlines():
            if not line.strip():
                continue
            fields = line.split("\t")
            if len(fields) != 2 or not re.fullmatch(r"(?:app|runtime)/[^/\s]+/[^/\s]+/[^/\s]+", fields[0]) or not re.fullmatch(r"[a-fA-F0-9]{8,64}", fields[1]):
                raise ValueError("Invalid Flatpak candidate")
            # Commit identifies the exact target when semantic version is absent.
            items.append(UpdateItem(fields[0], fields[1]))
        return items

    @staticmethod
    def _atomic(output: str) -> list[UpdateItem]:
        items = []
        section = ""
        known_empty = False
        for line in output.splitlines():
            value = line.strip()
            if not value:
                continue
            if value in {"No upgrade available.", "No updates available.", "No upgrade available", "No updates available"}:
                known_empty = True
                continue
            if value in {"Upgraded:", "Downgraded:", "Added:", "Removed:"}:
                section = value[:-1]
                continue
            match = re.fullmatch(r"(?:(Upgraded|Downgraded)\s+)?(\S+)\s+(\S+)\s+->\s+(\S+)", value)
            if match and (match[1] or section in {"Upgraded", "Downgraded"}):
                items.append(UpdateItem(match[2], match[4], match[3]))
                continue
            match = re.fullmatch(r"(?:(Added|Removed)\s+)?(\S+)\s+(\S+)", value)
            if match and (match[1] or section in {"Added", "Removed"}):
                action = match[1] or section
                items.append(UpdateItem(match[2], match[3] if action == "Added" else "", match[3] if action == "Removed" else ""))
                continue
            if value.startswith(("Checking", "Receiving", "Downloading", "Resolving", "Enabled rpm-md", "Updating metadata", "Importing", "AvailableUpdate:", "Version:", "Commit:", "GPGSignature:", "Diff:", "=")):
                continue
            raise ValueError("Unknown Atomic preview format")
        if not items and not known_empty:
            raise ValueError("Atomic preview did not establish an outcome")
        return items

    def _firmware(self, base: UpdateSourceResult, result: ActionResult) -> UpdateSourceResult:
        # fwupd's NOTHING_TO_DO (2) is a valid empty result, never a blanket
        # success for arbitrary output or transport/daemon errors.
        if result.exit_code not in {0, 2, None} or (result.exit_code is None and not result.success):
            return replace(base, status="error", error_code="query_failed")
        try:
            payload = json.loads(result.stdout)
        except ValueError:
            message = (result.stdout + "\n" + result.stderr).strip().lower().rstrip(".")
            if result.exit_code == 2 and message in {"no updates available", "no upgrades for device", "no updatable devices"}:
                return replace(base, status="up_to_date")
            if result.exit_code == 2 and message == "no supported devices found":
                return replace(base, status="unsupported", error_code="no_supported_devices")
            raise
        if not isinstance(payload, dict) or not isinstance(payload.get("Devices"), list):
            raise ValueError("Invalid firmware payload")
        items = []
        for device in payload["Devices"]:
            if not isinstance(device, dict) or not isinstance(device.get("Releases", []), list):
                raise ValueError("Invalid firmware device")
            for release in device.get("Releases", []):
                if not isinstance(release, dict) or not release.get("Version"):
                    raise ValueError("Invalid firmware release")
                name = device.get("Name") or device.get("DeviceId")
                if not isinstance(name, str):
                    raise ValueError("Missing firmware identity")
                items.append(UpdateItem(name, str(release["Version"]), str(device.get("Version", ""))))
                break  # fwupd orders applicable releases newest first.
        self._validate_items(items)
        return replace(base, status="available" if items else "up_to_date", items=tuple(items))
