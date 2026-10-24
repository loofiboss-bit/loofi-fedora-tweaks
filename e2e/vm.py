"""Build and run isolated Fedora KDE GUI tests through libvirt's session URI.

The host side uses only QEMU/libvirt commands and the standard library. It does
not install packages or change host services, networks, accounts, or settings.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import hmac
import io
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr
from pathlib import Path
from typing import Any, Sequence

from e2e.console import execute as console_execute


ROOT = Path(__file__).resolve().parents[1]
VM_NAME = "loofi-fedora-tweaks-e2e"
LIBVIRT_URI = "qemu:///session"
FEDORA_RELEASE = "44"
MEMORY_MIB = 5120
VCPUS = 2
MIN_AVAILABLE_MIB = 6144
MIN_DISK_GIB = 40
GUEST_USER = "loofie2e"
GUEST_AGENT_TIMEOUT = 15
GUEST_RUN_TIMEOUT = 45 * 60
# Include the bounded native setup/offline work performed after desktop pytest,
# plus time for runtime qualification and report finalization.
GUEST_PHASE_TIMEOUTS = {
    "normal": GUEST_RUN_TIMEOUT + 120,
    "before-reboot": GUEST_RUN_TIMEOUT + 900 + 600 + 120,
    "after-reboot": GUEST_RUN_TIMEOUT + 300 + 120,
}
INSTALL_TIMEOUT = 90 * 60
PASSWORD_ITERATIONS = 600_000


def _credential_digest(password: str, salt: str) -> str:
    """Derive a salted integrity verifier with a bounded password KDF."""
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PASSWORD_ITERATIONS).hex()


class VMError(RuntimeError):
    """A safe, actionable E2E VM setup or execution failure."""


def _default_data_root() -> Path:
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data).expanduser() if xdg_data else Path.home() / ".local" / "share"
    return base / "loofi-fedora-tweaks" / "e2e"


def _run(
    args: Sequence[str],
    *,
    timeout: int = 30,
    input_text: str | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a host tool without a shell and with a finite timeout."""
    try:
        result = subprocess.run(
            list(args),
            input=input_text,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            timeout=timeout,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stderr or exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        details = str(output).strip()
        raise VMError(
            f"Command timed out after {timeout} seconds: {args[0]}" + (f"\n{details[-3000:]}" if details else "")
        ) from exc
    except OSError as exc:
        raise VMError(f"Could not run {args[0]}: {exc}") from exc
    if check and result.returncode:
        details = (result.stderr or result.stdout or "").strip()
        raise VMError(f"Command failed ({result.returncode}): {args[0]}" + (f"\n{details}" if details else ""))
    return result


def _available_memory_mib(meminfo: Path = Path("/proc/meminfo")) -> int:
    for line in meminfo.read_text(encoding="ascii").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    raise VMError(f"MemAvailable was not found in {meminfo}")


def preflight(data_root: Path | None = None) -> dict[str, Any]:
    """Check prerequisites without changing host state."""
    root = (data_root or _default_data_root()).expanduser()
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise VMError("Run just test-full as your normal desktop user; do not use sudo or pkexec.")
    release = platform.freedesktop_os_release()
    if release.get("ID") != "fedora":
        raise VMError("The VM runner must be a Fedora host with QEMU/KVM and libvirt installed.")

    missing = [
        name
        for name in ("virsh", "virt-install", "qemu-img", "qemu-system-x86_64", "rpmbuild", "openssl")
        if shutil.which(name) is None
    ]
    if missing:
        raise VMError("Missing host commands: " + ", ".join(missing) + ". Install approval is required before adding host packages.")

    kvm = Path("/dev/kvm")
    if not kvm.exists() or not os.access(kvm, os.R_OK | os.W_OK):
        raise VMError("/dev/kvm is not readable and writable by this user; enable KVM access before running the VM tests.")

    available_mib = _available_memory_mib()
    if available_mib < MIN_AVAILABLE_MIB:
        raise VMError(
            f"Only {available_mib} MiB RAM is currently available; test-full requires at least "
            f"{MIN_AVAILABLE_MIB} MiB free for a {MEMORY_MIB} MiB VM plus host headroom."
        )

    disk_probe = root.parent
    while not disk_probe.exists() and disk_probe != disk_probe.parent:
        disk_probe = disk_probe.parent
    usage = shutil.disk_usage(disk_probe)
    free_gib = usage.free // (1024**3)
    if free_gib < MIN_DISK_GIB:
        raise VMError(f"Only {free_gib} GiB is free below {disk_probe}; at least {MIN_DISK_GIB} GiB is required.")

    uri = _run(["virsh", "-c", LIBVIRT_URI, "uri"], timeout=10).stdout.strip()
    if uri != LIBVIRT_URI:
        raise VMError(f"Libvirt connected to unexpected URI {uri!r}; expected {LIBVIRT_URI!r}.")
    _run(["virsh", "-c", LIBVIRT_URI, "list", "--all"], timeout=10)
    return {
        "host_release": release.get("VERSION_ID", "unknown"),
        "available_memory_mib": available_mib,
        "free_disk_gib": free_gib,
        "data_root": str(root),
        "libvirt_uri": LIBVIRT_URI,
    }


def _domain_xml(uuid_value: str, disk_path: Path, name: str = VM_NAME) -> str:
    """Return the only supported domain shape: isolated user network, no shares."""
    return f"""<domain type='kvm'>
  <name>{name}</name>
  <uuid>{uuid_value}</uuid>
  <memory unit='MiB'>{MEMORY_MIB}</memory>
  <currentMemory unit='MiB'>{MEMORY_MIB}</currentMemory>
  <vcpu placement='static'>{VCPUS}</vcpu>
  <os><type arch='x86_64' machine='q35'>hvm</type><boot dev='hd'/></os>
  <features><acpi/><apic/></features>
  <cpu mode='host-passthrough'/>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff><on_reboot>restart</on_reboot><on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type='file' device='disk'><driver name='qemu' type='qcow2'/><source file={quoteattr(str(disk_path))}/><target dev='vda' bus='virtio'/></disk>
    <interface type='user'><model type='virtio'/><link state='down'/></interface>
    <controller type='usb' model='qemu-xhci'/>
    <input type='tablet' bus='usb'/>
    <graphics type='spice' autoport='yes'><listen type='address' address='127.0.0.1'/></graphics>
    <video><model type='qxl' ram='65536' vram='65536' heads='1'/></video>
    <serial type='pty'><target type='isa-serial' port='0'/></serial>
    <console type='pty'><target type='serial' port='0'/></console>
    <channel type='unix'><target type='virtio' name='org.qemu.guest_agent.0'/></channel>
  </devices>
</domain>
"""


def _memory_mib(element: ET.Element | None) -> int | None:
    if element is None or not element.text:
        return None
    multipliers = {"b": 1 / 1024**2, "bytes": 1 / 1024**2, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}
    multiplier = multipliers.get(element.get("unit", "KiB"))
    return int(int(element.text) * multiplier) if multiplier is not None else None


def _validate_graphics(xml: ET.Element) -> None:
    """Allow one local Spice endpoint or an explicitly disabled listener."""
    graphics = xml.findall("./devices/graphics")
    if len(graphics) != 1 or graphics[0].get("type") != "spice":
        raise VMError("The E2E VM requires exactly one isolated Spice graphics device.")
    graphics = graphics[0]
    listeners = graphics.findall(".//listen")
    if len(listeners) != 1 or len(graphics.findall("./listen")) != 1:
        raise VMError("The E2E VM graphics device must have exactly one explicit listener.")
    listener = listeners[0]
    local = listener.attrib == {"type": "address", "address": "127.0.0.1"}
    disabled = listener.attrib == {"type": "none"}
    if not (local or disabled) or "socket" in graphics.attrib or "address" in graphics.attrib or graphics.findall(".//socket"):
        raise VMError("The E2E VM graphics endpoint must use localhost or an explicit disabled listener without a socket.")
    if graphics.get("listen") not in (None, "127.0.0.1") or (disabled and any(
            name in graphics.attrib for name in ("listen", "port", "tlsPort", "websocket"))):
        raise VMError("The E2E VM graphics device has an unexpected additional endpoint.")
    gl = graphics.findall(".//gl")
    if len(gl) > 1 or any(node.get("enable") != "no" for node in gl):
        raise VMError("The E2E VM graphics device must not enable GL.")


def _qt_runtime_payload(manifest_path: Path) -> tuple[dict[str, Any], bytes, bytes]:
    """Validate the explicit source-built runtime before any guest starts."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be an object")
        expected_source = "5b2e00eccaf5a4d8c14134ffa0ea8dfd0a35ae1ffc7f8d87fa4305a1ed23cf22"
        if manifest.get("passed") is not True or type(manifest.get("exit_code")) is not int or manifest["exit_code"] != 0:
            raise ValueError("corrected runtime native regression did not pass")
        archive = manifest_path.parent / "qtbase-everywhere-src-6.11.2.tar.xz"
        with archive.open("rb") as source:
            source_hash = hashlib.file_digest(source, "sha256").hexdigest()
        patch_hash = hashlib.sha256((ROOT / "packaging/qt/qtbase-scroll-area-accessibility.patch").read_bytes()).hexdigest()
        if source_hash != expected_source or manifest.get("source_sha256") != expected_source:
            raise ValueError("official Qt source archive hash mismatch")
        if manifest.get("patch_sha256") != patch_hash:
            raise ValueError("runtime patch hash does not match the checked-in fix")
        library = Path(manifest["runtime_path"])
        if library.name != "libQt6Widgets.so.6.11.2" or library.stat().st_size > 32 * 1024**2:
            raise ValueError("unexpected corrected Widgets library")
        content = library.read_bytes()
        if not content.startswith(b"\x7fELF") or hashlib.sha256(content).hexdigest() != manifest.get("runtime_sha256"):
            raise ValueError("corrected Widgets library hash mismatch")
        probe = (manifest_path.parent / "qt-scroll-probe").read_bytes()
        if not probe.startswith(b"\x7fELF") or len(probe) > 2 * 1024**2:
            raise ValueError("invalid native regression executable")
        if not isinstance(manifest.get("installed_dependencies"), str):
            raise ValueError("installed dependency package identities must be text")
        packages = manifest["installed_dependencies"].splitlines()
        expected_packages = [next(value for value in packages if re.fullmatch(
            name + r"-6\.11\.2-[A-Za-z0-9.]+\.fc44\.x86_64", value)) for name in ("qt6-qtbase", "qt6-qtbase-gui")]
        dependencies = manifest["dependency_libraries"]
        for name in ("Core", "Gui"):
            if dependencies[name]["path"] != f"/usr/lib64/libQt6{name}.so.6.11.2" or not re.fullmatch(
                    r"[0-9a-f]{64}", dependencies[name]["sha256"]):
                raise ValueError("invalid expected Core/Gui library identity")
        return {"manifest": manifest, "expected_packages": expected_packages,
                "probe_sha256": hashlib.sha256(probe).hexdigest()}, content, probe
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        raise VMError(f"Invalid corrected Qt runtime manifest: {exc}") from exc


class FedoraE2E:
    """Own exactly one test VM in qemu:///session and its generated disks."""

    def __init__(self, data_root: Path | None = None, reports_dir: Path | None = None, *, name: str = VM_NAME, desktop: str = "x11", reboot_check: bool = False, qt_runtime_manifest: Path | None = None):
        if not re.fullmatch(r"loofi-fedora-tweaks-e2e(?:-[a-z0-9-]+)?", name) or desktop not in {"x11", "wayland"}:
            raise VMError("Invalid dedicated E2E VM name or desktop.")
        self.name = name
        self.desktop = desktop
        self.reboot_check = reboot_check
        self.qt_runtime_manifest = qt_runtime_manifest
        self._qt_runtime = _qt_runtime_payload(qt_runtime_manifest) if qt_runtime_manifest else None
        self.data_root = (data_root or _default_data_root()).expanduser().resolve()
        self.reports_dir = (reports_dir or ROOT / "test-results" / "e2e").resolve()
        self.base_disk = self.data_root / "fedora-kde-base.qcow2"
        self.overlay_disk = self.data_root / "fedora-kde-run.qcow2"
        self.domain_xml_path = self.data_root / "domain.xml"
        self.state_path = self.data_root / "state.json"
        self.password_path = self.data_root / "guest-password"
        self.lock_path = self.data_root / "run.lock"
        self._state: dict[str, Any] = {}
        self._started_here = False
        self._may_stop = False
        self._install_created_here = False
        self._interrupted = False

    def test_full(self) -> int:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            raise VMError("Run just test-full as your normal desktop user; do not use sudo or pkexec.")
        self.data_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data_root.chmod(0o700)
        with self.lock_path.open("a", encoding="utf-8") as lock_handle:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise VMError("Another E2E run owns the VM lock; wait for that run to finish.") from None
            os.chmod(self.lock_path, 0o600)
            self.reports_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            report_names = ["summary.json", "runner.log", "junit.xml", "pytest.log", "guest-result.json", "install.log", "application.log", "polkit-before.xml"]
            report_names.extend(["package-fixture.log", "offline-update-evidence.json", "application-action-evidence.json", "offline-activation.log", "reboot-checkpoint.json", "flatpak-update-evidence.json", "crash-diagnostics.json", "qt-runtime-host.json", "qt-runtime-evidence.json", "qt-runtime-applications.json"])
            report_names.extend(["setup-transactions.log", "setup-transactions-evidence.json", "flatpak-install-evidence.json"])
            report_names.extend(Path(name).stem + "-after-reboot" + Path(name).suffix for name in tuple(report_names) if name not in {"summary.json", "runner.log"})
            report_names.extend(path.name for path in self.reports_dir.glob("*-accessibility.xml"))
            for name in report_names:
                (self.reports_dir / name).unlink(missing_ok=True)
            facts: dict[str, Any] = {}
            completed = False
            code = 2
            try:
                self._recover_abandoned_run()
                facts = preflight(self.data_root)
                self._load_state()
                print("Building the current RPM...", flush=True)
                rpm = self._build_rpm()
                self._rpm_evidence = {"filename": rpm.name, "sha256": hashlib.sha256(rpm.read_bytes()).hexdigest(), "artifact_path": str(rpm)}
                self._ensure_base()
                self._validate_domain(verify_overlay=False)
                self._reset_overlay()
                print("Starting the isolated Fedora KDE guest (5 GiB / 2 vCPU, offline)...", flush=True)
                self._start()
                self._wait_for_agent(300)
                self._wait_for_desktop(600)
                print("Installing the local RPM and staging native GUI tests...", flush=True)
                self._prepare_payload(rpm)
                print("Running pytest in the guest desktop...", flush=True)
                code = self._run_guest_tests("before-reboot" if self.reboot_check else "normal")
                self._collect_reports()
                if code == 0 and self.reboot_check:
                    self._reboot_guest()
                    code = self._run_guest_tests("after-reboot")
                    self._collect_reports(suffix="-after-reboot")
                completed = True
                return code
            except Exception as exc:
                if not self._interrupted and self._may_stop and self._domain_exists():
                    try:
                        self._collect_reports(suffix="-after-reboot" if getattr(self, "_reboot_evidence", None) else "")
                    except (VMError, OSError):
                        pass
                self._write_failure(exc, facts)
                raise
            finally:
                try:
                    if self._started_here and self._domain_exists():
                        print("Stopping the guest and discarding test changes...", flush=True)
                        self._stop_owned_domain(force=self._interrupted)
                        if self.base_disk.exists():
                            self._reset_overlay()
                    if self._install_created_here and not self._state.get("provisioned") and not self.base_disk.exists():
                        self._discard_partial_install()
                except Exception as cleanup_error:
                    self._write_failure(cleanup_error, facts)
                    raise
                if completed:
                    self._write_summary(code, facts)

    def _recover_abandoned_run(self) -> None:
        """After acquiring the lock, release only an owned disposable guest.

        Recovery precedes the memory check because an abandoned guest may be
        using the memory needed by the next run. Never recover unmarked guests.
        """
        if not self.state_path.is_file():
            return
        self._load_state()
        if not self._state.get("provisioned") or not self._domain_exists():
            return
        self._validate_domain(verify_overlay=False)
        state = _run(["virsh", "-c", LIBVIRT_URI, "domstate", self.name], timeout=10).stdout.strip().lower()
        if state != "shut off":
            print("Recovering the owned disposable VM after an interrupted run.", flush=True)
            self._stop_owned_domain(force=True)
            # QEMU holds the overlay lock while running. Inspect its backing
            # metadata only after stopping the UUID/shape-validated guest.
            self._validate_overlay()
            self._reset_overlay()
        else:
            self._validate_overlay()

    def _interrupt(self, signum: int, _frame: Any) -> None:
        self._interrupted = True
        # A second cancellation signal must not interrupt the bounded cleanup.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        raise VMError(f"E2E run interrupted by signal {signum}.")

    def reset(self) -> int:
        """Remove only the VM and generated files named by this runner's marker."""
        if not self.data_root.exists():
            print("No E2E VM data directory exists; nothing to reset.")
            return 0
        if not self.state_path.is_file():
            raise VMError("No E2E ownership marker exists; refusing to remove VM data.")
        with self.lock_path.open("a", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            os.chmod(self.lock_path, 0o600)
            self._load_reset_state()
            if self._domain_exists():
                if self._state.get("provisioned"):
                    self._validate_domain(verify_overlay=False)
                else:
                    self._validate_partial_domain()
                self._stop_owned_domain()
                _run(["virsh", "-c", LIBVIRT_URI, "undefine", self.name], timeout=30)

            for path in (
                self.base_disk,
                self.overlay_disk,
                self.data_root / "fedora-kde-install.qcow2",
                self.domain_xml_path,
                self.data_root / "ks.cfg",
                self.password_path,
                self.state_path,
            ):
                path.unlink(missing_ok=True)
            print(f"Removed the owned Fedora E2E VM and generated files from {self.data_root}.")
            return 0

    def _load_reset_state(self) -> None:
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VMError("VM state file is invalid; refusing to reset the VM data.") from exc
        if not isinstance(state, dict) or (
            state.get("name") != self.name
            or state.get("desktop", "x11") != self.desktop
            or state.get("uri") != LIBVIRT_URI
            or state.get("fedora_release") != FEDORA_RELEASE
            or not isinstance(state.get("uuid"), str)
            or not isinstance(state.get("provisioned"), bool)
        ):
            raise VMError("The saved VM state does not prove ownership; refusing to reset it.")
        try:
            if str(uuid.UUID(state["uuid"])) != state["uuid"]:
                raise ValueError("non-canonical UUID")
        except ValueError as exc:
            raise VMError("The saved VM UUID is invalid; refusing to reset it.") from exc
        self._state = state

    def _validate_partial_domain(self) -> None:
        """Validate the disposable install domain before a recovery reset."""
        domain_uuid = _run(["virsh", "-c", LIBVIRT_URI, "domuuid", self.name], timeout=10).stdout.strip()
        if domain_uuid != self._state.get("uuid"):
            raise VMError("The partial VM name belongs to a different UUID; refusing to stop or remove it.")
        xml = ET.fromstring(_run(["virsh", "-c", LIBVIRT_URI, "dumpxml", self.name], timeout=10).stdout)
        if xml.findtext("name") != self.name or xml.findtext("uuid") != domain_uuid:
            raise VMError("The partial VM identity does not match its saved ownership marker.")
        memory = xml.find("memory")
        current_memory = xml.find("currentMemory")
        if _memory_mib(memory) != MEMORY_MIB or _memory_mib(current_memory) != MEMORY_MIB:
            raise VMError("The partial VM has unexpected memory; refusing to reset it.")
        if xml.findtext("vcpu") != str(VCPUS):
            raise VMError("The partial VM has an unexpected CPU count; refusing to reset it.")
        interfaces = xml.findall("./devices/interface")
        if len(interfaces) != 1 or interfaces[0].get("type") != "user" or xml.findall("./devices/interface/portForward"):
            raise VMError("The partial VM network is not isolated; refusing to reset it.")
        if xml.findall("./devices/filesystem") or xml.findall("./devices/hostdev"):
            raise VMError("The partial VM contains host shares or passthrough devices; refusing to reset it.")
        if len(xml.findall("./devices/disk")) != 1:
            raise VMError("The partial VM has unexpected disks; refusing to reset it.")
        source = xml.find("./devices/disk/source")
        expected_disk = self._state.get("install_disk")
        if not isinstance(expected_disk, str) or Path(expected_disk).resolve() != (self.data_root / "fedora-kde-install.qcow2").resolve():
            raise VMError("The install disk path is missing from the ownership marker; refusing to reset it.")
        if source is None or Path(source.get("file", "")).resolve() != Path(expected_disk).resolve():
            raise VMError("The partial VM disk does not match the owned install disk.")
        _validate_graphics(xml)

    def _load_state(self) -> None:
        if self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise VMError(f"VM state file is invalid: {self.state_path}") from exc
            if not isinstance(state, dict):
                raise VMError(f"VM state file is invalid: {self.state_path}")
            if (
                state.get("name") != self.name
                or state.get("desktop", "x11") != self.desktop
                or state.get("uri") != LIBVIRT_URI
                or state.get("fedora_release") != FEDORA_RELEASE
                or not isinstance(state.get("provisioned"), bool)
            ):
                raise VMError("The saved VM state belongs to a different domain or libvirt connection; refusing to change it.")
            try:
                if str(uuid.UUID(state.get("uuid", ""))) != state.get("uuid"):
                    raise ValueError("non-canonical UUID")
            except (AttributeError, TypeError, ValueError) as exc:
                raise VMError("The saved VM UUID is invalid; refusing to change it.") from exc
            self._state = state
            return
        if self._domain_exists():
            raise VMError(f"A VM named {self.name} already exists without this runner's ownership marker; refusing to touch it.")
        if self.password_path.exists() or self.base_disk.exists() or self.overlay_disk.exists():
            raise VMError("Unregistered E2E VM data already exists; refusing to overwrite it.")
        self._state = {
            "name": self.name,
            "desktop": self.desktop,
            "uri": LIBVIRT_URI,
            "uuid": str(uuid.uuid4()),
            "fedora_release": FEDORA_RELEASE,
            "provisioned": False,
        }
        self._save_state()

    def _save_state(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._state, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.state_path)

    def _domain_exists(self) -> bool:
        result = _run(["virsh", "-c", LIBVIRT_URI, "dominfo", self.name], timeout=10, check=False)
        return result.returncode == 0

    def _validate_domain(self, *, verify_overlay: bool = True) -> None:
        if not self._domain_exists():
            if self._state.get("provisioned"):
                raise VMError("The registered E2E VM is missing from qemu:///session; refusing to recreate it implicitly.")
            return
        domain_uuid = _run(["virsh", "-c", LIBVIRT_URI, "domuuid", self.name], timeout=10).stdout.strip()
        if domain_uuid != self._state.get("uuid"):
            raise VMError("The VM name now belongs to a different UUID; refusing to stop or replace it.")
        if not self._state.get("provisioned"):
            raise VMError("A partially installed VM exists; use the documented reset command before retrying provisioning.")
        xml = ET.fromstring(_run(["virsh", "-c", LIBVIRT_URI, "dumpxml", self.name], timeout=10).stdout)
        name = xml.findtext("name")
        if name != self.name or xml.findtext("uuid") != domain_uuid:
            raise VMError("The registered domain identity does not match the test VM marker.")
        memory = xml.find("memory")
        current_memory = xml.find("currentMemory")
        vcpu = xml.findtext("vcpu")

        if _memory_mib(memory) != MEMORY_MIB or _memory_mib(current_memory) != MEMORY_MIB or vcpu != str(VCPUS):
            raise VMError("The existing VM no longer matches the required 5 GiB / 2 vCPU configuration.")
        interfaces = xml.findall("./devices/interface")
        if len(interfaces) != 1 or interfaces[0].get("type") != "user":
            raise VMError("The existing VM does not have the required isolated user-mode network.")
        if xml.findall("./devices/interface/portForward"):
            raise VMError("The E2E VM has a forwarded inbound port; refusing to boot it.")
        link = interfaces[0].find("link")
        if link is None or link.get("state") != "down":
            raise VMError("The reusable E2E VM must have its network link down; tests run offline.")
        disks = xml.findall("./devices/disk")
        sources = [node.get("file") for node in xml.findall("./devices/disk/source")]
        if len(disks) != 1 or disks[0].get("device") != "disk" or sources != [str(self.overlay_disk)]:
            raise VMError("The existing VM disk is not the E2E overlay; refusing to boot it.")
        if xml.findall("./devices/filesystem") or xml.findall("./devices/hostdev"):
            raise VMError("The E2E VM contains a host filesystem or device passthrough; refusing to boot it.")
        _validate_graphics(xml)
        if len(xml.findall("./devices/channel/target[@name='org.qemu.guest_agent.0']")) != 1:
            raise VMError("The E2E VM is missing its required guest-agent channel.")
        if verify_overlay:
            self._validate_overlay()
        self._may_stop = True

    def _validate_overlay(self) -> None:
        if not self.base_disk.is_file() or not self.overlay_disk.is_file():
            raise VMError("The E2E base disk or run overlay is missing.")
        if self.base_disk.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
            raise VMError("The Fedora base disk is writable; refusing to use it as an immutable test image.")
        info = json.loads(_run(["qemu-img", "info", "--output=json", str(self.overlay_disk)], timeout=30).stdout)
        backing = info.get("backing-filename")
        if info.get("format") != "qcow2" or not backing:
            raise VMError("The E2E run disk is not a QCOW2 overlay with a backing image.")
        backing_path = Path(backing)
        if not backing_path.is_absolute():
            backing_path = self.overlay_disk.parent / backing_path
        if backing_path.resolve() != self.base_disk.resolve():
            raise VMError("The E2E run overlay does not reference this runner's immutable Fedora base disk.")

    def _build_rpm(self) -> Path:
        result = _run(["bash", "scripts/build_rpm.sh"], timeout=20 * 60, check=False)
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode:
            raise VMError("RPM build failed:\n" + output[-6000:])
        marker = next((line.removeprefix("RPM_PATH=").strip() for line in output.splitlines() if line.startswith("RPM_PATH=")), None)
        if not marker:
            raise VMError("RPM build did not report its output path.")
        rpm = Path(marker).resolve()
        if not rpm.is_file() or rpm.parent != (ROOT / "rpmbuild" / "RPMS" / "noarch").resolve():
            raise VMError("RPM build returned a missing or unexpected output path.")
        return self._retain_candidate(rpm)

    def _retain_candidate(self, rpm: Path) -> Path:
        """Retain the exact build while potentially lengthy provisioning runs."""
        content = rpm.read_bytes()
        directory = Path(tempfile.mkdtemp(prefix="candidate-", dir=self.reports_dir))
        retained = directory / rpm.name
        retained.write_bytes(content)
        retained.chmod(0o400)
        return retained

    def _discard_partial_install(self) -> None:
        """Remove only the incomplete install created during this invocation."""
        if self._state.get("provisioned") or self.base_disk.exists():
            raise VMError("Refusing partial-install cleanup after the reusable base image was created.")
        install_disk = self.data_root / "fedora-kde-install.qcow2"
        marked_disk = self._state.get("install_disk")
        if marked_disk is not None and Path(marked_disk).resolve() != install_disk.resolve():
            raise VMError("The partial-install disk path does not match this runner's data directory.")
        if self._domain_exists():
            self._validate_partial_domain()
            self._stop_owned_domain()
            _run(["virsh", "-c", LIBVIRT_URI, "undefine", self.name], timeout=30)
        for path in (install_disk, self.data_root / "ks.cfg", self.password_path, self.state_path):
            path.unlink(missing_ok=True)
        print("Removed the owned incomplete Fedora E2E install; test-full can provision it again.", flush=True)

    def _kickstart(self, password_hash: str) -> str:
        updates_repository = (
            f'repo --name=loofi-e2e-fedora-updates --metalink="https://mirrors.fedoraproject.org/metalink?repo=updates-released-f{FEDORA_RELEASE}&arch=x86_64"\n'
            if self.qt_runtime_manifest is not None else ""
        )
        wayland_packages = ""
        wayland_build = ""
        if self.desktop == "wayland":
            wayland_packages = """cmake
make
gcc-c++
extra-cmake-modules
qt6-qtbase-private-devel
qt6-qtwayland-devel
kf6-kwindowsystem-devel
kf6-kcoreaddons-devel
kwayland-devel
kpipewire-devel
plasma-wayland-protocols-devel
wayland-devel
libxkbcommon-devel
curl
"""
            wayland_build = """# Build only guest automation helpers from the same pinned KDE source.
curl --fail --location --max-time 180 --output /var/tmp/selenium.tar.gz https://codeload.github.com/KDE/selenium-webdriver-at-spi/tar.gz/50e41aa9913b16e5d0a6fec921c963485aa125b4
printf '8e71bfbd93a5760f08b87ae437087847d2ec376bd88858bee5a4e228f1fcaba0  /var/tmp/selenium.tar.gz\\n' | sha256sum --check
mkdir -p /var/tmp/selenium-source
tar --extract --gzip --file /var/tmp/selenium.tar.gz --directory /var/tmp/selenium-source --strip-components=1
cmake -S /var/tmp/selenium-source -B /var/tmp/selenium-build -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build /var/tmp/selenium-build --parallel 2 --target selenium-webdriver-at-spi-inputsynth selenium-webdriver-at-spi-screenshotter
install -m 0755 /var/tmp/selenium-build/bin/selenium-webdriver-at-spi-inputsynth /usr/local/bin/
install -m 0755 /var/tmp/selenium-build/bin/selenium-webdriver-at-spi-screenshotter /usr/local/bin/
install -m 0644 /var/tmp/selenium-build/inputsynth/org.kde.selenium-webdriver-at-spi-inputsynth.desktop /usr/share/applications/
install -m 0644 /var/tmp/selenium-build/screenshotter/org.kde.selenium-webdriver-at-spi-screenshotter.desktop /usr/share/applications/
rm -rf /var/tmp/selenium-source /var/tmp/selenium-build /var/tmp/selenium.tar.gz
"""
        return f"""text
lang en_US.UTF-8
keyboard us
timezone Etc/UTC --utc
network --device=link --bootproto=dhcp --activate
rootpw --lock
ignoredisk --only-use=vda
zerombr
clearpart --all --initlabel --drives=vda
autopart --type=lvm --nohome
bootloader --location=mbr --boot-drive=vda
user --name={GUEST_USER} --groups=wheel --password={password_hash} --iscrypted
selinux --enforcing
firewall --enabled
services --enabled=NetworkManager,qemu-guest-agent
{updates_repository}%packages
@^kde-desktop-environment
plasma-workspace-x11
xorg-x11-drv-qxl
sddm
polkit-kde
python3-pyqt6
python3-gobject-base
flatpak
flatpak-libs
gnupg2
rpm-build
rpm-sign
createrepo_c
python3-keyring
python3-defusedxml
python3-pytest
python3-selenium
python3-flask
python3-numpy
python3-lxml
python3-pyatspi
python3-xlib
qemu-guest-agent
dolphin
plasma-discover
dnf5
dnf5-plugins
python3-libdnf5
{wayland_packages}%end
%post --interpreter=/bin/bash
set -euo pipefail
{wayland_build}mkdir -p /etc/sddm.conf.d
cat > /etc/sddm.conf.d/loofi-e2e.conf <<'EOF'
[Autologin]
User={GUEST_USER}
Session={"plasmax11" if self.desktop == "x11" else "plasma"}
Relogin=false
EOF
printf 'loofi-fedora-tweaks-e2e\\n' > /etc/loofi-e2e-guest
# Skip Plasma's first-run account setup so the test account reaches the desktop.
touch /etc/plasma-setup-done
install -d -m 0700 -o {GUEST_USER} -g {GUEST_USER} /home/{GUEST_USER}/.config
printf '[Daemon]\nAutolock=false\n' > /home/{GUEST_USER}/.config/kscreenlockerrc
chown {GUEST_USER}:{GUEST_USER} /home/{GUEST_USER}/.config/kscreenlockerrc
printf '\nQT_LINUX_ACCESSIBILITY_ALWAYS_ON=1\n' >> /etc/environment
systemctl --root=/ set-default graphical.target
systemctl --root=/ disable plasmalogin.service
systemctl --root=/ enable qemu-guest-agent.service sddm.service
# Keep authenticated test administration available after the installer reboot.
grubby --update-kernel=ALL --args=console=ttyS0,115200n8
systemctl --root=/ enable serial-getty@ttyS0.service
%end
reboot
"""

    def _ensure_base(self) -> None:
        if self._state.get("provisioned") and self.base_disk.is_file() and self.domain_xml_path.is_file():
            return
        if self._state.get("provisioned"):
            raise VMError("The saved VM base disk or domain XML is missing; refusing silent reprovisioning.")

        install_disk = self.data_root / "fedora-kde-install.qcow2"
        if install_disk.is_file() and self._domain_exists() and not self.base_disk.exists() and not self.overlay_disk.exists():
            self._validate_partial_domain()
            print("Resuming the owned Fedora installation; existing disk data is retained.", flush=True)
            state = _run(["virsh", "-c", LIBVIRT_URI, "domstate", self.name], timeout=10).stdout.lower()
            if "shut off" in state:
                _run(["virsh", "-c", LIBVIRT_URI, "start", self.name], timeout=30)
            self._started_here = True
            self._may_stop = True
            self._wait_for_agent(300)
            self._wait_for_desktop(300)
            self._promote_base(install_disk)
            return
        if any(path.exists() for path in (self.base_disk, self.overlay_disk, install_disk)):
            raise VMError("Partial VM disk data cannot be safely resumed; refusing to overwrite it.")
        self._install_created_here = True
        password = secrets.token_urlsafe(24)
        self.password_path.write_text(password + "\n", encoding="utf-8")
        os.chmod(self.password_path, 0o600)
        password_hash = _run(["openssl", "passwd", "-6", "-stdin"], timeout=10, input_text=password + "\n").stdout.strip()
        self._state["password_salt"] = secrets.token_hex(16)
        self._state["password_verifier"] = _credential_digest(password, self._state["password_salt"])
        self._save_state()

        _run(["qemu-img", "create", "-f", "qcow2", str(install_disk), "32G"], timeout=20)
        ks_file = self.data_root / "ks.cfg"
        ks_file.write_text(self._kickstart(password_hash), encoding="utf-8")
        os.chmod(ks_file, 0o600)
        install_url = f"https://download.fedoraproject.org/pub/fedora/linux/releases/{FEDORA_RELEASE}/Everything/x86_64/os/"
        command = [
            "virt-install",
            "--connect", LIBVIRT_URI,
            "--name", self.name,
            "--uuid", self._state["uuid"],
            "--memory", str(MEMORY_MIB),
            "--vcpus", str(VCPUS),
            "--machine", "q35",
            "--disk", f"path={install_disk},format=qcow2,bus=virtio",
            "--network", "user,model=virtio",
            "--graphics", "spice,listen=127.0.0.1",
            "--video", "qxl",
            "--channel", "unix,target.type=virtio,name=org.qemu.guest_agent.0",
            "--location", install_url,
            "--initrd-inject", str(ks_file),
            "--extra-args", "inst.ks=file:/ks.cfg console=ttyS0,115200n8",
            "--noautoconsole",
        ]
        self._state["install_disk"] = str(install_disk)
        self._save_state()
        _run(command, timeout=15 * 60, check=True)
        self._assert_owned_domain()
        self._started_here = True
        self._may_stop = True
        self._wait_for_agent(INSTALL_TIMEOUT, restart_if_powered_off=True)
        self._wait_for_desktop(900)
        self._promote_base(install_disk)

    def _promote_base(self, install_disk: Path) -> None:
        self._validate_partial_domain()
        self._stop_owned_domain()
        _run(["virsh", "-c", LIBVIRT_URI, "undefine", self.name], timeout=30)
        _run(["qemu-img", "convert", "-O", "qcow2", str(install_disk), str(self.base_disk)], timeout=15 * 60)
        _run(["qemu-img", "check", str(self.base_disk)], timeout=60)
        os.chmod(self.base_disk, 0o400)
        install_disk.unlink()
        self.overlay_disk.unlink(missing_ok=True)
        self._create_overlay()
        xml = _domain_xml(self._state["uuid"], self.overlay_disk, self.name)
        self.domain_xml_path.write_text(xml, encoding="utf-8")
        os.chmod(self.domain_xml_path, 0o600)
        _run(["virsh", "-c", LIBVIRT_URI, "define", str(self.domain_xml_path)], timeout=30)
        self._state["provisioned"] = True
        self._state.pop("install_disk", None)
        self._save_state()

    def _create_overlay(self) -> None:
        if not self.base_disk.is_file():
            raise VMError("The immutable Fedora base disk is missing.")
        _run(
            ["qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", str(self.base_disk), str(self.overlay_disk)],
            timeout=30,
        )
        os.chmod(self.overlay_disk, 0o600)

    def _reset_overlay(self) -> None:
        if not self._domain_exists():
            raise VMError("The test domain is missing; refusing to recreate a disk it cannot own.")
        state = _run(["virsh", "-c", LIBVIRT_URI, "domstate", self.name], timeout=10).stdout.strip().lower()
        if "shut off" not in state:
            raise VMError(f"Cannot reset the E2E overlay while domain state is {state!r}.")
        self._validate_domain(verify_overlay=False)
        if not self.base_disk.is_file() or self.base_disk.stat().st_mode & 0o222:
            raise VMError("The immutable Fedora base disk is missing or writable; refusing to reset the VM.")
        self.overlay_disk.unlink(missing_ok=True)
        self._create_overlay()
        self._validate_overlay()

    def _start(self) -> None:
        self._validate_domain()
        state = _run(["virsh", "-c", LIBVIRT_URI, "domstate", self.name], timeout=10).stdout.strip().lower()
        if "shut off" not in state:
            raise VMError(f"The E2E VM must be shut off before this run; current state is {state!r}.")
        _run(["virsh", "-c", LIBVIRT_URI, "start", self.name], timeout=30)
        self._started_here = True

    def _stop_owned_domain(self, *, force: bool = False) -> None:
        self._assert_owned_domain()
        state = _run(["virsh", "-c", LIBVIRT_URI, "domstate", self.name], timeout=10).stdout.strip().lower()
        if "shut off" in state:
            self._started_here = False
            return
        if force:
            _run(["virsh", "-c", LIBVIRT_URI, "destroy", self.name], timeout=5)
            self._started_here = False
            return
        _run(["virsh", "-c", LIBVIRT_URI, "shutdown", self.name], timeout=30, check=False)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = _run(["virsh", "-c", LIBVIRT_URI, "domstate", self.name], timeout=10, check=False).stdout.strip().lower()
            if "shut off" in state:
                self._started_here = False
                return
            time.sleep(2)
        # This hard stop is limited to the UUID-validated disposable E2E guest.
        self._assert_owned_domain()
        _run(["virsh", "-c", LIBVIRT_URI, "destroy", self.name], timeout=30)
        self._started_here = False

    def _assert_owned_domain(self) -> None:
        if not self._domain_exists():
            return
        domain_uuid = _run(["virsh", "-c", LIBVIRT_URI, "domuuid", self.name], timeout=10).stdout.strip()
        if domain_uuid != self._state.get("uuid"):
            raise VMError("The VM name no longer belongs to this runner; refusing to stop it.")

    def _qga(self, command: dict[str, Any], *, timeout: int = GUEST_AGENT_TIMEOUT) -> Any:
        # Use stdin: file-transfer payloads include a private guest credential
        # and must not appear in the host process list.
        request = shlex.join(["qemu-agent-command", self.name, "--timeout", str(timeout), "--cmd", json.dumps(command)])
        try:
            response = _run(["virsh", "--quiet", "-c", LIBVIRT_URI], input_text=request + "\nquit\n",
                            timeout=timeout + 5, check=False)
        except VMError:
            raise VMError("The QEMU Guest Agent request timed out or disconnected.") from None
        if response.returncode or response.stderr.strip():
            raise VMError("The QEMU Guest Agent request failed: " + response.stderr.strip())
        # virsh echoes interactive input even with --quiet. Never log that
        # input; the agent's JSON response occupies its own line.
        lines = [line for line in response.stdout.splitlines() if line.startswith("{")]
        try:
            result = json.loads(lines[-1])
        except (IndexError, json.JSONDecodeError):
            raise VMError("QEMU Guest Agent returned no valid JSON response.") from None
        if "error" in result:
            raise VMError(f"QEMU Guest Agent error: {result['error']}")
        return result.get("return", {})

    def _wait_for_agent(self, timeout: int, *, restart_if_powered_off: bool = False) -> None:
        deadline = time.monotonic() + timeout
        last_error = "agent has not responded"
        restarted = False
        while time.monotonic() < deadline:
            try:
                self._qga({"execute": "guest-ping"}, timeout=5)
                return
            except VMError as exc:
                last_error = str(exc)
            if restart_if_powered_off:
                state = _run(["virsh", "-c", LIBVIRT_URI, "domstate", self.name], timeout=10, check=False)
                if state.returncode == 0 and "shut off" in state.stdout.strip().lower():
                    if restarted:
                        raise VMError("The Fedora installer shut down the owned VM more than once; refusing an automatic boot loop.")
                    self._validate_partial_domain()
                    print("Fedora installation powered off the owned VM; starting its installed system.", flush=True)
                    _run(["virsh", "-c", LIBVIRT_URI, "start", self.name], timeout=30)
                    self._started_here = True
                    self._may_stop = True
                    restarted = True
            time.sleep(5)
        raise VMError(f"Timed out waiting for the VM guest agent: {last_error}")

    def _validated_password(self) -> str:
        password = self.password_path.read_text(encoding="utf-8").strip()
        salt = self._state.get("password_salt")
        verifier = self._state.get("password_verifier")
        if (not password or not isinstance(salt, str) or not re.fullmatch(r"[0-9a-f]{32}", salt)
                or not isinstance(verifier, str) or not re.fullmatch(r"[0-9a-f]{64}", verifier)):
            raise VMError("The private guest credential integrity metadata is missing or invalid.")
        if not hmac.compare_digest(_credential_digest(password, salt), verifier):
            raise VMError("The private guest credential does not match its ownership marker.")
        return password

    def _guest_exec(self, path: str, args: Sequence[str], *, timeout: int = GUEST_RUN_TIMEOUT) -> tuple[int, str, str]:
        self._assert_owned_domain()
        password = self._validated_password()
        try:
            return console_execute(LIBVIRT_URI, self.name, GUEST_USER, password, [path, *args], timeout)
        except (OSError, RuntimeError) as exc:
            raise VMError(str(exc)) from exc

    def _write_guest_file(self, remote_path: str, content: bytes) -> None:
        handle = self._qga({"execute": "guest-file-open", "arguments": {"path": remote_path, "mode": "wb"}})
        if not isinstance(handle, int):
            raise VMError(f"Could not open guest file {remote_path}.")
        try:
            for offset in range(0, len(content), 48 * 1024):
                chunk = content[offset:offset + 48 * 1024]
                result = self._qga({"execute": "guest-file-write", "arguments": {"handle": handle, "buf-b64": base64.b64encode(chunk).decode("ascii")}})
                if result.get("count") != len(chunk):
                    raise VMError(f"Guest file transfer was short at {remote_path}.")
        finally:
            self._qga({"execute": "guest-file-close", "arguments": {"handle": handle}})

    def _read_guest_file(self, remote_path: str) -> bytes:
        handle = self._qga({"execute": "guest-file-open", "arguments": {"path": remote_path, "mode": "rb"}})
        if not isinstance(handle, int):
            raise VMError(f"Could not open guest report {remote_path}.")
        chunks: list[bytes] = []
        try:
            while True:
                result = self._qga({"execute": "guest-file-read", "arguments": {"handle": handle, "count": 48 * 1024}})
                chunks.append(base64.b64decode(result.get("buf-b64") or ""))
                if result.get("eof"):
                    break
        finally:
            self._qga({"execute": "guest-file-close", "arguments": {"handle": handle}})
        return b"".join(chunks)

    def _wait_for_desktop(self, timeout: int) -> None:
        deadline = time.monotonic() + timeout
        last_status = "desktop session not started"
        while time.monotonic() < deadline:
            code, stdout, stderr = self._guest_exec(
                "/usr/bin/python3",
                [
                    "-c",
                    "import glob,os,pwd; p=pwd.getpwnam('loofie2e'); print(os.path.exists(f'/run/user/{p.pw_uid}/bus') and bool(glob.glob("
                    + ("'/tmp/.X11-unix/X*'" if self.desktop == "x11" else "f'/run/user/{p.pw_uid}/wayland-*'") + ")))",
                ],
                timeout=20,
            )
            last_status = (stdout + stderr).strip()
            if code == 0 and "True" in stdout:
                return
            time.sleep(5)
        raise VMError(f"Timed out waiting for the Plasma {self.desktop} auto-login: {last_status}")

    def _build_fixture(self) -> bytes:
        """Build an inert, dependency-free local package solely for the guest."""
        with tempfile.TemporaryDirectory(prefix="loofi-e2e-fixture-") as directory:
            root = Path(directory)
            spec = root / "fixture.spec"
            spec.write_text("""Name: loofi-e2e-fixture
Version: 1.0
Release: 1
Summary: Inert disposable VM package fixture
License: MIT
BuildArch: noarch
%description
Contains a single probe file for isolated package lifecycle tests.
%install
mkdir -p %{buildroot}/usr/share/loofi-e2e-fixture
printf 'loofi-e2e-fixture\\n' > %{buildroot}/usr/share/loofi-e2e-fixture/probe.txt
%files
/usr/share/loofi-e2e-fixture/probe.txt
""", encoding="utf-8")
            _run(["rpmbuild", "-bb", "--define", f"_topdir {root}", str(spec)], timeout=120)
            candidates = list((root / "RPMS" / "noarch").glob("loofi-e2e-fixture-*.rpm"))
            if len(candidates) != 1:
                raise VMError("Fixture RPM build did not produce exactly one inert package.")
            return candidates[0].read_bytes()

    def _prepare_payload(self, rpm: Path) -> None:
        candidate = rpm.read_bytes()
        expected = getattr(self, "_rpm_evidence", None)
        if expected is not None and hashlib.sha256(candidate).hexdigest() != expected["sha256"]:
            raise VMError("The retained candidate RPM changed before staging; refusing mismatched qualification evidence.")
        code, _, _ = self._guest_exec("/usr/bin/bash", ["-c", "mkdir -p /var/tmp/loofi-e2e && chcon -t virt_qemu_ga_log_t /var/tmp/loofi-e2e"])
        if code:
            raise VMError("Could not prepare the guest-only SELinux staging directory.")
        revision = "50e41aa9913b16e5d0a6fec921c963485aa125b4"
        for name, digest in {
            "selenium-webdriver-at-spi.py": "c0d317af690afe2c9625830f4452abce5f8e54dda3e294394abf155cba666fbd",
            "app_roles.py": "9d845a17539f388eaea89c89ae17b897dadad9f4a484a0e5c6e3299b61df70fd",
        }.items():
            cache = self.data_root / (revision + "-" + name)
            if not cache.is_file():
                url = f"https://raw.githubusercontent.com/KDE/selenium-webdriver-at-spi/{revision}/{name}"
                with urllib.request.urlopen(url, timeout=60) as response:
                    content = response.read(1024 * 1024)
                if hashlib.sha256(content).hexdigest() != digest:
                    raise VMError("The pinned KDE driver download did not match its checksum.")
                cache.write_bytes(content)
                cache.chmod(0o600)
            content = cache.read_bytes()
            if hashlib.sha256(content).hexdigest() != digest:
                raise VMError("The cached KDE driver did not match its checksum.")
            self._write_guest_file("/var/tmp/loofi-e2e/" + name, content)
        self._write_guest_file("/var/tmp/loofi-e2e/build.rpm", candidate)
        self._write_guest_file("/var/tmp/loofi-e2e/loofi-e2e-fixture.rpm", self._build_fixture())
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as bundle:
            for path in sorted((ROOT / "e2e" / "tests").rglob("*.py")):
                bundle.add(path, arcname=path.relative_to(ROOT).as_posix())
        self._write_guest_file("/var/tmp/loofi-e2e/tests.tar.gz", archive.getvalue())
        self._write_guest_file("/var/tmp/loofi-e2e/runner.py", (ROOT / "e2e" / "guest" / "runner.py").read_bytes())
        password = self._validated_password()
        payload = json.dumps({"user": GUEST_USER, "password": password}, separators=(",", ":")).encode("utf-8")
        self._write_guest_file("/var/tmp/loofi-e2e/credentials.json", payload)
        if self._qt_runtime is not None:
            self._stage_qt_runtime()
        code, stdout, stderr = self._guest_exec(
            "/usr/bin/python3",
            ["/var/tmp/loofi-e2e/runner.py", "--install", "/var/tmp/loofi-e2e/build.rpm", "/var/tmp/loofi-e2e/tests.tar.gz", "/var/tmp/loofi-e2e/credentials.json"],
            timeout=GUEST_RUN_TIMEOUT,
        )
        self._runner_output = stdout + stderr
        self._runner_exit = code
        if code:
            raise VMError(f"Guest RPM installation or test staging failed with exit code {code}.")

    def _stage_qt_runtime(self) -> None:
        """Transfer only to the disposable guest; compatibility is checked there."""
        assert self._qt_runtime is not None
        payload, library, probe = self._qt_runtime
        directory = "/var/tmp/loofi-e2e/qt-runtime"
        code, _, _ = self._guest_exec("/usr/bin/mkdir", ["-p", directory], timeout=30)
        if code:
            raise VMError("Could not create the guest-only Qt runtime directory.")
        self._write_guest_file(directory + "/libQt6Widgets.so.6.11.2", library)
        self._write_guest_file(directory + "/qt-scroll-probe", probe)
        self._write_guest_file("/var/tmp/loofi-e2e/qt-runtime-request.json", json.dumps(payload).encode())
        (self.reports_dir / "qt-runtime-host.json").write_text(json.dumps(payload, indent=2) + "\n")
        code, stdout, stderr = self._guest_exec(
            "/usr/bin/python3", ["/var/tmp/loofi-e2e/runner.py", "--qualify-qt-runtime"], timeout=120)
        self._runner_output = getattr(self, "_runner_output", "") + stdout + stderr
        if code:
            raise VMError("Corrected Qt runtime guest compatibility/regression failed; see qt-runtime-evidence.json. " + (stdout + stderr)[-2000:])

    def _reboot_guest(self) -> None:
        """Reboot only the validated disposable domain and prove a new kernel boot."""
        self._validate_domain(verify_overlay=False)
        code, before, _ = self._guest_exec("/usr/bin/cat", ["/proc/sys/kernel/random/boot_id"], timeout=20)
        before = before.strip()
        if code or not re.fullmatch(r"[0-9a-f-]{36}", before):
            raise VMError("Could not record the guest boot identity before reboot.")
        code, _, error = self._guest_exec("/usr/bin/python3", ["/var/tmp/loofi-e2e/runner.py", "--activate-offline"], timeout=30)
        if code:
            raise VMError(f"Could not activate the prepared update through Action Center: {error}")
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                code, after, _ = self._guest_exec("/usr/bin/cat", ["/proc/sys/kernel/random/boot_id"], timeout=20)
                after = after.strip()
                if code == 0 and re.fullmatch(r"[0-9a-f-]{36}", after) and after != before:
                    self._wait_for_agent(300)
                    self._wait_for_desktop(600)
                    self._reboot_evidence = {"before_boot_id": before, "after_boot_id": after}
                    # First phase removes its private credential after pytest.
                    payload = json.dumps({"user": GUEST_USER, "password": self._validated_password()}).encode()
                    self._write_guest_file("/var/tmp/loofi-e2e/credentials.json", payload)
                    code, _, _ = self._guest_exec("/usr/bin/python3", ["-c", "import os,pwd; p=pwd.getpwnam('loofie2e'); f='/var/tmp/loofi-e2e/credentials.json'; os.chown(f,p.pw_uid,p.pw_gid); os.chmod(f,0o600)"], timeout=20)
                    if code:
                        raise VMError("Could not protect the restored guest test credential.")
                    return
            except VMError:
                pass
            time.sleep(5)
        raise VMError("Guest reboot did not produce a new boot identity within 300 seconds.")

    def _run_guest_tests(self, phase: str = "normal") -> int:
        code, stdout, stderr = self._guest_exec(
            "/usr/bin/python3",
            ["/var/tmp/loofi-e2e/runner.py", "--run", "--phase", phase],
            timeout=GUEST_PHASE_TIMEOUTS[phase],
        )
        self._runner_output = getattr(self, "_runner_output", "") + stdout + stderr
        self._runner_exit = code
        return code

    def _collect_reports(self, suffix: str = "") -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.reports_dir, 0o700)
        reports = [
            ("/var/tmp/loofi-e2e/junit.xml", "junit.xml"),
            ("/var/tmp/loofi-e2e/pytest.log", "pytest.log"),
            ("/var/tmp/loofi-e2e/result.json", "guest-result.json"),
            ("/var/tmp/loofi-e2e/install.log", "install.log"),
            ("/var/tmp/loofi-e2e/application.log", "application.log"),
            ("/var/tmp/loofi-e2e/package-fixture.log", "package-fixture.log"),
            ("/var/tmp/loofi-e2e/flatpak-update-evidence.json", "flatpak-update-evidence.json"),
            ("/var/tmp/loofi-e2e/flatpak-install-evidence.json", "flatpak-install-evidence.json"),
            ("/var/tmp/loofi-e2e/crash-diagnostics.json", "crash-diagnostics.json"),
            ("/var/tmp/loofi-e2e/setup-transactions.log", "setup-transactions.log"),
            ("/var/tmp/loofi-e2e/setup-transactions/evidence.json", "setup-transactions-evidence.json"),
            ("/var/tmp/loofi-e2e/qt-runtime-evidence.json", "qt-runtime-evidence.json"),
            ("/var/tmp/loofi-e2e/qt-runtime-applications.json", "qt-runtime-applications.json"),
            ("/var/tmp/loofi-e2e/reboot-checkpoint.json", "reboot-checkpoint.json"),
            ("/var/tmp/loofi-e2e/offline-update-evidence.json", "offline-update-evidence.json"),
            ("/var/tmp/loofi-e2e/application-action-evidence.json", "application-action-evidence.json"),
            ("/var/tmp/loofi-e2e/offline-activation.log", "offline-activation.log"),
        ]
        try:
            artifacts = json.loads(self._read_guest_file("/var/tmp/loofi-e2e/failure-artifacts.json"))
            if isinstance(artifacts, list):
                for name in artifacts[:100]:
                    if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,160}-accessibility\.xml", name):
                        reports.append(("/var/tmp/loofi-e2e/" + name, name))
        except (VMError, ValueError):
            pass
        for remote, local in reports:
            try:
                content = self._read_guest_file(remote)
            except VMError:
                continue
            target = self.reports_dir / (Path(local).stem + suffix + Path(local).suffix)
            password = self.password_path.read_text(encoding="utf-8").strip().encode()
            target.write_bytes(content.replace(password, b"[redacted]"))
            os.chmod(target, 0o600)
        log = self.reports_dir / "runner.log"
        log.write_text(getattr(self, "_runner_output", ""), encoding="utf-8")
        os.chmod(log, 0o600)

    def _write_summary(self, code: int, facts: dict[str, Any]) -> None:
        summary = {
            "vm": self.name,
            "libvirt_uri": LIBVIRT_URI,
            "fedora_release": FEDORA_RELEASE,
            "desktop": self.desktop,
            "reboot": getattr(self, "_reboot_evidence", None),
            "memory_mib": MEMORY_MIB,
            "vcpus": VCPUS,
            "exit_code": code,
            "status": "passed" if code == 0 else "failed",
            "preflight": facts,
            "rpm": getattr(self, "_rpm_evidence", None),
            "corrected_qt_runtime": self._qt_runtime[0] if self._qt_runtime else None,
        }
        target = self.reports_dir / "summary.json"
        target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        os.chmod(target, 0o600)
        print(f"Fedora KDE E2E {summary['status']} (exit {code}). Reports: {self.reports_dir}", flush=True)
        if code:
            suffix = "-after-reboot" if getattr(self, "_reboot_evidence", None) else ""
            log_path = self.reports_dir / f"pytest{suffix}.log"
            try:
                # Reports are credential-redacted during collection. Bound the
                # terminal excerpt independently of the guest log's size.
                with log_path.open("rb") as log:
                    log.seek(0, os.SEEK_END)
                    log.seek(max(0, log.tell() - 8192))
                    excerpt = log.read(8192).decode("utf-8", errors="replace")
                print("\n".join(excerpt.splitlines()[-40:]), flush=True)
            except OSError:
                print(f"Guest pytest log unavailable; inspect {target} and runner.log.", flush=True)

    def _write_failure(self, exc: Exception, facts: dict[str, Any]) -> None:
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.reports_dir, 0o700)
            runner_log = self.reports_dir / "runner.log"
            runner_log.write_text(getattr(self, "_runner_output", ""), encoding="utf-8")
            os.chmod(runner_log, 0o600)
            target = self.reports_dir / "summary.json"
            target.write_text(json.dumps({"vm": self.name, "status": "failed", "error": str(exc), "preflight": facts,
                                          "corrected_qt_runtime": self._qt_runtime[0] if self._qt_runtime else None,
                                          "rpm": getattr(self, "_rpm_evidence", None), "desktop": self.desktop}, indent=2) + "\n", encoding="utf-8")
            os.chmod(target, 0o600)
        except OSError:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run isolated Fedora KDE desktop end-to-end tests.")
    parser.add_argument("command", choices=("preflight", "test-full", "reset"), nargs="?", default="test-full")
    parser.add_argument("--vm-name", default=VM_NAME, help="Explicit dedicated domain name for resetting a saved fresh artifact.")
    parser.add_argument("--fresh", action="store_true", help="Provision a separate empty-disk qualification artifact; preserve the reusable base.")
    parser.add_argument("--desktop", choices=("x11", "wayland"), default="x11")
    parser.add_argument("--qt-runtime-manifest", type=Path, help="Explicit corrected Qt runtime manifest; disposable test-full only.")
    parser.add_argument("--reboot-check", action="store_true", help="Verify checkpoint persistence across a real guest reboot.")
    parser.add_argument("--data-root", type=Path, default=_default_data_root())
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "test-results" / "e2e")
    args = parser.parse_args(argv)
    try:
        if args.qt_runtime_manifest and args.command != "test-full":
            raise VMError("--qt-runtime-manifest is only valid with test-full.")
        if args.command == "preflight":
            print(json.dumps(preflight(args.data_root), indent=2))
            return 0
        if args.fresh and args.command != "test-full":
            raise VMError("--fresh is only valid with test-full.")
        name = args.vm_name
        if args.fresh:
            artifact = f"fresh-{args.desktop}-{uuid.uuid4().hex[:12]}"
            args.data_root = args.data_root / artifact
            args.reports_dir = args.reports_dir / artifact
            name += "-" + artifact
            print(f"Fresh qualification data: {args.data_root}; reports: {args.reports_dir}", flush=True)
        elif args.desktop != "x11" and args.vm_name == VM_NAME:
            args.data_root = args.data_root / args.desktop
            args.reports_dir = args.reports_dir / args.desktop
            name += "-" + args.desktop
        vm = FedoraE2E(args.data_root, args.reports_dir, name=name, desktop=args.desktop, reboot_check=args.reboot_check, qt_runtime_manifest=args.qt_runtime_manifest)
        if args.command == "reset":
            return vm.reset()
        previous = {sig: signal.signal(sig, vm._interrupt) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            return vm.test_full()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    except (VMError, BlockingIOError) as exc:
        print(f"E2E VM error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
