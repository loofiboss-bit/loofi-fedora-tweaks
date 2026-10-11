"""Host-side contracts for safe, repeatable Fedora KDE VM tests."""

from __future__ import annotations

import re
import json
import signal
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from e2e.vm import (
    FEDORA_RELEASE,
    LIBVIRT_URI,
    MEMORY_MIB,
    MIN_AVAILABLE_MIB,
    VMError,
    VM_NAME,
    VCPUS,
    FedoraE2E,
    _domain_xml,
    _memory_mib,
    _run,
    preflight,
)


ROOT = Path(__file__).resolve().parents[1]


def test_host_tools_use_stable_locale_with_swedish_parent() -> None:
    with patch.dict("os.environ", {"LANG": "sv_SE.UTF-8", "LC_ALL": "sv_SE.UTF-8"}), patch(
        "e2e.vm.subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="shut off", stderr="")
    ) as run:
        _run(["virsh", "domstate", VM_NAME])
    assert run.call_args.kwargs["env"]["LC_ALL"] == "C"


def test_serial_console_uses_stable_locale_without_password_in_environment() -> None:
    from e2e.console import execute

    process = Mock()
    process.poll.return_value = 1
    with patch.dict("os.environ", {"LC_ALL": "sv_SE.UTF-8"}), patch("e2e.console.subprocess.Popen", return_value=process) as popen:
        with pytest.raises(RuntimeError, match="disconnected"):
            execute(LIBVIRT_URI, VM_NAME, "guest", "private-password", ["true"], 5)
    assert popen.call_args.kwargs["env"]["LC_ALL"] == "C"
    assert "private-password" not in str(popen.call_args)


def test_serial_console_refreshes_a_lost_initial_newline() -> None:
    from e2e.console import execute

    process = Mock()
    process.poll.return_value = None
    chunks = [b"Escape character is ^]\r\n", b"login:", b"Password:", b"\n$ ", b"LOOFI_fixed# ", b"LOOFI_fixed_EXIT:0\r\n"]
    with patch("e2e.console.pty.openpty", return_value=(30, 31)), patch("e2e.console.subprocess.Popen", return_value=process), patch(
        "e2e.console.os.close"
    ), patch("e2e.console.os.write") as write, patch("e2e.console.os.read", side_effect=chunks), patch(
        "e2e.console.select.select", side_effect=[([30], [], []), ([], [], []), *[([30], [], [])] * 5]
    ), patch("e2e.console.time.monotonic", side_effect=range(1000)), patch("e2e.console.secrets.token_hex", return_value="fixed"):
        assert execute(LIBVIRT_URI, VM_NAME, "guest", "private-password", ["true"], 100) == (0, "", "")
    assert sum(call.args == (30, b"\n") for call in write.call_args_list) == 2


def test_interrupt_requests_fast_cleanup_and_ignores_followup_signals(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    with patch("e2e.vm.signal.signal") as handler:
        with pytest.raises(VMError, match="interrupted"):
            vm._interrupt(signal.SIGTERM, None)
    assert vm._interrupted
    handler.assert_any_call(signal.SIGTERM, signal.SIG_IGN)
    handler.assert_any_call(signal.SIGINT, signal.SIG_IGN)


def test_abandoned_run_is_stopped_only_after_ownership_validation(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    vm.state_path.write_text("{}")
    vm._state = {"provisioned": True}
    events = []
    with patch.object(vm, "_load_state"), patch.object(vm, "_domain_exists", return_value=True), patch.object(
        vm, "_validate_domain", side_effect=lambda **kw: events.append(("validated", kw))
    ), patch("e2e.vm._run", return_value=subprocess.CompletedProcess([], 0, stdout="running", stderr="")), patch.object(
        vm, "_stop_owned_domain", side_effect=lambda **kw: events.append(("stop", kw))
    ), patch.object(vm, "_validate_overlay", side_effect=lambda: events.append("overlay validated")), patch.object(
        vm, "_reset_overlay", side_effect=lambda: events.append("reset")
    ):
        vm._recover_abandoned_run()
    assert events == [("validated", {"verify_overlay": False}), ("stop", {"force": True}), "overlay validated", "reset"]


def test_abandoned_run_recovery_refuses_changed_domain(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    vm.state_path.write_text("{}")
    vm._state = {"provisioned": True}
    with patch.object(vm, "_load_state"), patch.object(vm, "_domain_exists", return_value=True), patch.object(
        vm, "_validate_domain", side_effect=VMError("different UUID")
    ), patch.object(vm, "_stop_owned_domain") as stop:
        with pytest.raises(VMError, match="different UUID"):
            vm._recover_abandoned_run()
    stop.assert_not_called()


def test_failure_artifacts_are_discovered_safely_and_redacted(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path, tmp_path / "reports")
    vm.password_path.write_text("private-password\n")
    files = {
        "/var/tmp/loofi-e2e/failure-artifacts.json": json.dumps([
            "future_test-accessibility.xml", "../../user-file-accessibility.xml", 1,
        ]).encode(),
        "/var/tmp/loofi-e2e/future_test-accessibility.xml": b"private-password <desktop/>",
    }

    def read(path):
        if path not in files:
            raise VMError("not available")
        return files[path]

    with patch.object(vm, "_read_guest_file", side_effect=read) as fetch:
        vm._collect_reports()
    assert (vm.reports_dir / "future_test-accessibility.xml").read_text() == "[redacted] <desktop/>"
    assert not any("../" in call.args[0] for call in fetch.call_args_list)


def _workflow(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _job(text: str, name: str) -> str:
    marker = f"  {name}:\n"
    tail = text.split(marker, 1)[1]
    match = re.search(r"\n  [a-zA-Z0-9_-]+:\n", tail)
    return tail if match is None else tail[:match.start()]


def test_domain_contract_is_rootless_and_has_no_host_shares(tmp_path: Path) -> None:
    xml = ET.fromstring(_domain_xml("00000000-0000-0000-0000-000000000001", tmp_path / "run.qcow2"))

    assert xml.findtext("name") == VM_NAME
    assert xml.findtext("uuid") == "00000000-0000-0000-0000-000000000001"
    assert xml.findtext("memory") == str(MEMORY_MIB)
    assert xml.find("memory").get("unit") == "MiB"
    assert xml.findtext("vcpu") == str(VCPUS)
    assert [interface.get("type") for interface in xml.findall("./devices/interface")] == ["user"]
    assert xml.find("./devices/interface/link").get("state") == "down"
    assert xml.findall("./devices/filesystem") == []
    assert xml.findall("./devices/hostdev") == []
    assert xml.find("./devices/graphics/listen").get("address") == "127.0.0.1"
    assert LIBVIRT_URI == "qemu:///session"


def test_preflight_blocks_root_execution_before_host_mutations(tmp_path: Path) -> None:
    data_root = tmp_path / "vm"
    with patch("e2e.vm.os.geteuid", return_value=0):
        with pytest.raises(VMError, match="normal desktop user"):
            preflight(data_root)
    assert not data_root.exists()


def test_preflight_enforces_memory_before_connecting_to_libvirt(tmp_path: Path) -> None:
    data_root = tmp_path / "vm"
    original_exists = Path.exists

    def exists_for_preflight(path: Path) -> bool:
        return path == Path("/dev/kvm") or original_exists(path)

    with patch("e2e.vm.os.geteuid", return_value=1000), patch(
        "e2e.vm.platform.freedesktop_os_release", return_value={"ID": "fedora", "VERSION_ID": FEDORA_RELEASE}
    ), patch("e2e.vm.shutil.which", return_value="/usr/bin/available"), patch("e2e.vm.os.access", return_value=True), patch.object(
        Path, "exists", exists_for_preflight
    ), patch("e2e.vm._available_memory_mib", return_value=MIN_AVAILABLE_MIB - 1), patch("e2e.vm._run") as run:
        with pytest.raises(VMError, match="currently available"):
            preflight(data_root)
    run.assert_not_called()
    assert not data_root.exists()


def test_existing_domain_validation_accepts_only_marked_shape(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    domain_uuid = "00000000-0000-0000-0000-000000000001"
    vm._state = {"uuid": domain_uuid, "provisioned": True}
    domain_xml = _domain_xml(domain_uuid, vm.overlay_disk)
    outputs = [
        subprocess.CompletedProcess([], 0, stdout=domain_uuid + "\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout=domain_xml, stderr=""),
    ]
    with patch.object(vm, "_domain_exists", return_value=True), patch.object(vm, "_validate_overlay"), patch("e2e.vm._run", side_effect=outputs):
        vm._validate_domain()


def test_libvirt_memory_units_are_normalized_for_ownership_checks() -> None:
    assert _memory_mib(ET.fromstring("<memory unit='MiB'>5120</memory>")) == MEMORY_MIB
    assert _memory_mib(ET.fromstring("<memory unit='KiB'>5242880</memory>")) == MEMORY_MIB
    assert _memory_mib(None) is None


def test_partial_install_domain_shape_is_accepted_for_owned_recovery(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    domain_uuid = "00000000-0000-0000-0000-000000000001"
    install_disk = tmp_path / "fedora-kde-install.qcow2"
    vm._state = {"uuid": domain_uuid, "provisioned": False, "install_disk": str(install_disk)}
    outputs = [
        subprocess.CompletedProcess([], 0, stdout=domain_uuid + "\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout=_domain_xml(domain_uuid, install_disk), stderr=""),
    ]
    with patch("e2e.vm._run", side_effect=outputs):
        vm._validate_partial_domain()


def test_existing_domain_with_foreign_uuid_is_never_touched(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    vm._state = {"uuid": "owned-by-runner", "provisioned": True}
    foreign_uuid = subprocess.CompletedProcess([], 0, stdout="different-uuid\n", stderr="")
    with patch.object(vm, "_domain_exists", return_value=True), patch("e2e.vm._run", return_value=foreign_uuid):
        with pytest.raises(VMError, match="different UUID"):
            vm._validate_domain()


def test_recovery_reset_refuses_a_foreign_partial_vm(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    vm._state = {"uuid": "owned-by-runner", "provisioned": False}
    foreign_uuid = subprocess.CompletedProcess([], 0, stdout="different-uuid\n", stderr="")
    with patch.object(vm, "_domain_exists", return_value=True), patch("e2e.vm._run", return_value=foreign_uuid):
        with pytest.raises(VMError, match="different UUID"):
            vm._validate_partial_domain()


def test_reset_refuses_unmarked_data(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    sentinel = vm.base_disk
    sentinel.write_text("preserve", encoding="utf-8")
    with pytest.raises(VMError, match="ownership marker"):
        vm.reset()
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_reset_removes_only_known_files_for_a_saved_owner(tmp_path: Path) -> None:
    import json

    vm = FedoraE2E(tmp_path)
    vm.state_path.write_text(
        json.dumps(
            {
                "name": VM_NAME,
                "uri": LIBVIRT_URI,
                "uuid": "00000000-0000-0000-0000-000000000001",
                "fedora_release": FEDORA_RELEASE,
                "provisioned": False,
            }
        ),
        encoding="utf-8",
    )
    vm.base_disk.write_text("owned", encoding="utf-8")
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("preserve", encoding="utf-8")
    with patch.object(vm, "_domain_exists", return_value=False):
        vm.reset()
    assert not vm.base_disk.exists()
    assert unrelated.read_text(encoding="utf-8") == "preserve"
    assert vm.state_path.exists() is False


def test_ci_vm_job_is_local_runner_only_and_skips_pull_requests() -> None:
    text = _workflow(".github/workflows/ci.yml")
    vm_job = _job(text, "vm_e2e")
    assert "if: github.ref == 'refs/heads/master' && github.event_name != 'pull_request'" in vm_job
    assert "[self-hosted, Linux, X64, loofi-vm-e2e]" in vm_job
    assert "run: python3 -m e2e.vm test-full --reboot-check" in vm_job
    assert "actions/upload-artifact@v4" in vm_job


def test_release_build_is_gated_by_successful_local_vm_tests() -> None:
    text = _workflow(".github/workflows/auto-release.yml")
    vm_job = _job(text, "vm_e2e")
    build_job = _job(text, "build")
    assert "github.ref == 'refs/heads/master'" in vm_job
    assert "startsWith(github.ref, 'refs/tags/v')" in vm_job
    assert "[self-hosted, Linux, X64, loofi-vm-e2e]" in vm_job
    assert "needs.validate.outputs.should_release == 'true'" in vm_job
    assert "run: just test-full" in vm_job
    assert "vm_e2e" in build_job.split("needs:", 1)[1].split("if:", 1)[0]
    assert "needs.vm_e2e.result == 'success'" in build_job


def test_rpm_builder_uses_a_unique_temp_root_and_reports_exact_rpm() -> None:
    text = (ROOT / "scripts" / "build_rpm.sh").read_text(encoding="utf-8")
    assert "mktemp -d" in text
    assert "RPM_PATH=$RPM_PATH" in text
    assert "rm -rf /tmp/loofi-fedora-tweaks-build" not in text


def test_guest_installs_local_rpm_without_refreshing_fedora_repositories() -> None:
    text = (ROOT / "e2e" / "guest" / "runner.py").read_text(encoding="utf-8")

    assert '["/usr/bin/rpm", "--upgrade", "--replacepkgs", "--nosignature", "--verbose", str(rpm_path)]' in text
    assert '"dnf", "install"' not in text


def test_documented_recovery_command_is_available() -> None:
    text = (ROOT / "Justfile").read_text(encoding="utf-8")
    assert "test-full-reset:" in text
    assert "choices=(\"preflight\", \"test-full\", \"reset\")" in _workflow("e2e/vm.py")


def test_kickstart_skips_plasma_first_run_setup_for_test_autologin(tmp_path: Path) -> None:
    kickstart = FedoraE2E(tmp_path)._kickstart("$6$test-hash")

    assert "touch /etc/plasma-setup-done" in kickstart
    assert "User=loofie2e\nSession=plasmax11" in kickstart
    assert "systemctl --root=/ set-default graphical.target" in kickstart
    assert "systemctl --root=/ enable qemu-guest-agent.service sddm.service" in kickstart
    assert "xorg-x11-drv-qxl" in kickstart


def test_install_wait_restarts_only_the_owned_domain_after_poweroff(tmp_path: Path) -> None:
    from e2e.vm import VMError

    vm = FedoraE2E(tmp_path)
    vm._state = {
        "uuid": "00000000-0000-0000-0000-000000000001",
        "provisioned": False,
        "install_disk": str(vm.data_root / "fedora-kde-install.qcow2"),
    }
    powered_off = subprocess.CompletedProcess([], 0, stdout="shut off\n", stderr="")
    started = subprocess.CompletedProcess([], 0, stdout="", stderr="")
    with patch.object(vm, "_qga", side_effect=[VMError("guest agent is unavailable"), {}]), patch.object(
        vm, "_validate_partial_domain"
    ) as validate_partial, patch("e2e.vm._run", side_effect=[powered_off, started]) as run, patch("e2e.vm.time.sleep"):
        vm._wait_for_agent(10, restart_if_powered_off=True)

    validate_partial.assert_called_once_with()
    assert run.call_args_list[1].args[0][-2:] == ["start", VM_NAME]
    assert vm._started_here
    assert vm._may_stop


def test_failed_first_install_cleanup_removes_only_runner_files(tmp_path: Path) -> None:
    import json

    vm = FedoraE2E(tmp_path)
    vm._install_created_here = True
    vm._state = {
        "name": VM_NAME,
        "uri": LIBVIRT_URI,
        "uuid": "00000000-0000-0000-0000-000000000001",
        "fedora_release": FEDORA_RELEASE,
        "provisioned": False,
        "install_disk": str(vm.data_root / "fedora-kde-install.qcow2"),
    }
    vm.state_path.write_text(json.dumps(vm._state), encoding="utf-8")
    owned = (
        vm.data_root / "fedora-kde-install.qcow2",
        vm.data_root / "ks.cfg",
        vm.password_path,
    )
    for path in owned:
        path.write_text("owned", encoding="utf-8")
    unrelated = vm.data_root / "unrelated.txt"
    unrelated.write_text("preserve", encoding="utf-8")

    with patch.object(vm, "_domain_exists", return_value=False):
        vm._discard_partial_install()

    assert all(not path.exists() for path in (*owned, vm.state_path))
    assert unrelated.read_text(encoding="utf-8") == "preserve"


def test_guest_file_transfer_accepts_integer_agent_handles(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    with patch.object(vm, "_qga", side_effect=[7, {"count": 3}, {}]) as agent:
        vm._write_guest_file("/var/tmp/test", b"abc")
    assert agent.call_args_list[1].args[0]["arguments"]["handle"] == 7
    with patch.object(vm, "_qga", side_effect=[7, {"buf-b64": "YWJj", "eof": True}, {}]):
        assert vm._read_guest_file("/var/tmp/test") == b"abc"


def test_native_suite_refuses_the_host_before_importing_dogtail() -> None:
    text = (ROOT / "e2e" / "tests" / "conftest.py").read_text()
    assert text.index('"/etc/loofi-e2e-guest"') < text.index("from helpers import")
    assert '"systemd-detect-virt", "--vm"' in text
    assert '"qemu"' in text


def test_guest_guard_accepts_hardware_accelerated_qemu() -> None:
    for name in ("e2e/guest/runner.py", "e2e/tests/conftest.py"):
        assert 'not in {"qemu", "kvm"}' in (ROOT / name).read_text()


def test_agent_payload_is_sent_over_stdin_not_host_argv(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path)
    response = subprocess.CompletedProcess([], 0, stdout='virsh # echoed input\n{"return":7}\nvirsh # quit\n', stderr="")
    with patch("e2e.vm._run", return_value=response) as run:
        assert vm._qga({"execute": "guest-file-write", "arguments": {"buf-b64": "private-test-payload"}}) == 7
    assert "private-test-payload" not in str(run.call_args.args[0])
    assert "private-test-payload" in run.call_args.kwargs["input_text"]


def test_success_is_reported_only_after_overlay_cleanup(tmp_path: Path) -> None:
    import json

    vm = FedoraE2E(tmp_path / "data", tmp_path / "reports")
    rpm = tmp_path / "test.rpm"
    rpm.write_bytes(b"test")
    methods = ("_load_state", "_ensure_base", "_validate_domain", "_reset_overlay", "_start", "_wait_for_agent", "_wait_for_desktop", "_prepare_payload", "_collect_reports")
    from contextlib import ExitStack
    with ExitStack() as stack:
        stack.enter_context(patch("e2e.vm.preflight", return_value={}))
        stack.enter_context(patch.object(vm, "_build_rpm", return_value=rpm))
        stack.enter_context(patch.object(vm, "_run_guest_tests", return_value=0))
        for name in methods:
            stack.enter_context(patch.object(vm, name))

        def fail_cleanup():
            raise VMError("cleanup failed")

        vm._install_created_here = True
        vm._state = {"provisioned": False}
        stack.enter_context(patch.object(vm, "_discard_partial_install", side_effect=fail_cleanup))
        with pytest.raises(VMError, match="cleanup failed"):
            vm.test_full()
    assert json.loads((vm.reports_dir / "summary.json").read_text())["status"] == "failed"


def test_separate_qualification_domain_keeps_golden_paths_and_identity(tmp_path: Path) -> None:
    ordinary = FedoraE2E(tmp_path / "golden")
    separate = FedoraE2E(tmp_path / "fresh", name=VM_NAME + "-fresh-x11-example")
    assert separate.base_disk != ordinary.base_disk
    assert separate.overlay_disk != ordinary.overlay_disk
    xml = ET.fromstring(_domain_xml("00000000-0000-0000-0000-000000000001", separate.overlay_disk, separate.name))
    assert xml.findtext("name") == separate.name
    assert xml.find("./devices/interface/link").get("state") == "down"


def test_wayland_kickstart_builds_only_guest_helpers_from_verified_source(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path, desktop="wayland", name=VM_NAME + "-wayland")
    kickstart = vm._kickstart("$6$test-hash")
    assert "Session=plasma\n" in kickstart
    assert "sha256sum --check" in kickstart
    assert "cmake --build" in kickstart
    assert "--target selenium-webdriver-at-spi-inputsynth selenium-webdriver-at-spi-screenshotter" in kickstart
    assert "/usr/share/applications/" in kickstart
    assert "-DCMAKE_INSTALL_PREFIX=/usr/local" in kickstart
    assert "/selenium-build/bin/selenium-webdriver-at-spi-inputsynth" in kickstart
    assert "plasma-discover" in kickstart
    assert "cmake --build" not in FedoraE2E(tmp_path)._kickstart("$6$test-hash")


def test_wayland_cannot_reuse_an_x11_ownership_marker(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path, desktop="wayland")
    vm.state_path.write_text(json.dumps({"name": VM_NAME, "uri": LIBVIRT_URI, "fedora_release": FEDORA_RELEASE, "uuid": "00000000-0000-0000-0000-000000000001", "provisioned": True}))
    with pytest.raises(VMError, match="different domain"):
        vm._load_state()


def test_reboot_requires_domain_validation_before_request(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path, reboot_check=True)
    with patch.object(vm, "_validate_domain", side_effect=VMError("foreign VM")), patch("e2e.vm._run") as run, patch.object(vm, "_guest_exec") as execute:
        with pytest.raises(VMError, match="foreign VM"):
            vm._reboot_guest()
    run.assert_not_called()
    execute.assert_not_called()


def test_reboot_records_changed_kernel_boot_and_protects_credentials(tmp_path: Path) -> None:
    vm = FedoraE2E(tmp_path, reboot_check=True)
    before = "00000000-0000-0000-0000-000000000001"
    after = "00000000-0000-0000-0000-000000000002"
    with patch.object(vm, "_validate_domain"), patch.object(vm, "_guest_exec", side_effect=[(0, before, ""), (0, after, ""), (0, "", "")]) as execute, patch(
        "e2e.vm._run"
    ) as run, patch.object(vm, "_wait_for_agent"), patch.object(vm, "_wait_for_desktop"), patch.object(vm, "_validated_password", return_value="private"), patch.object(vm, "_write_guest_file"):
        vm._reboot_guest()
    assert vm._reboot_evidence == {"before_boot_id": before, "after_boot_id": after}
    assert run.call_args.args[0][-4:] == ["reboot", VM_NAME, "--mode", "agent"]
    assert "os.chmod(f,0o600)" in execute.call_args.args[1][1]


def test_extended_qualification_remains_master_only_and_sequential() -> None:
    text = _workflow(".github/workflows/ci.yml")
    job = _job(text, "vm_extended_qualification")
    assert "github.ref == 'refs/heads/master'" in job
    assert "github.event_name == 'workflow_dispatch'" in job
    assert "inputs.extended_qualification" in job
    assert "needs: vm_e2e" in job
    assert "[self-hosted, Linux, X64, loofi-vm-e2e]" in job
    assert "--fresh --reboot-check" in job
    assert "--desktop wayland --reboot-check" in job
    assert job.index("Repeat from a clean overlay") < job.index("Provision and qualify a separate empty disk") < job.index("Qualify a separate Plasma Wayland guest")
