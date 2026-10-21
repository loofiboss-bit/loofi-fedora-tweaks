"""Corrected Qt staging must fail before installation on any identity mismatch."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch

from e2e.vm import ROOT, FEDORA_RELEASE, FedoraE2E, VMError, _qt_runtime_payload, _validate_graphics, main
from e2e.guest import runner


SOURCE_HASH = "5b2e00eccaf5a4d8c14134ffa0ea8dfd0a35ae1ffc7f8d87fa4305a1ed23cf22"
PACKAGES = ["qt6-qtbase-6.11.2-3.fc44.x86_64", "qt6-qtbase-gui-6.11.2-3.fc44.x86_64"]


class TestQtManifest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.library = self.root / "libQt6Widgets.so.6.11.2"
        self.library.write_bytes(b"\x7fELFwidgets")
        (self.root / "qt-scroll-probe").write_bytes(b"\x7fELFprobe")
        (self.root / "qtbase-everywhere-src-6.11.2.tar.xz").write_bytes(b"source")
        self.manifest = {"passed": True, "exit_code": 0, "source_sha256": SOURCE_HASH,
                         "runtime_path": str(self.library), "runtime_sha256": hashlib.sha256(self.library.read_bytes()).hexdigest(),
                         "patch_sha256": hashlib.sha256((ROOT / "packaging/qt/qtbase-scroll-area-accessibility.patch").read_bytes()).hexdigest(),
                         "installed_dependencies": "\n".join(PACKAGES),
                         "dependency_libraries": {name: {"path": f"/usr/lib64/libQt6{name}.so.6.11.2", "sha256": "a" * 64}
                                                  for name in ("Core", "Gui")}}
        self.path = self.root / "qualification.json"

    def save(self):
        self.path.write_text(json.dumps(self.manifest))

    @patch("e2e.vm.hashlib.file_digest")
    def test_valid_manifest_captures_exact_bytes_and_probe_hash(self, digest):
        digest.return_value.hexdigest.return_value = SOURCE_HASH
        self.save()
        payload, library, probe = _qt_runtime_payload(self.path)
        self.assertEqual(library, b"\x7fELFwidgets")
        self.assertEqual(payload["expected_packages"], PACKAGES)
        self.assertEqual(payload["probe_sha256"], hashlib.sha256(probe).hexdigest())

    @patch("e2e.vm.hashlib.file_digest")
    def test_rejects_unpassed_tampered_source_patch_and_library(self, digest):
        digest.return_value.hexdigest.return_value = SOURCE_HASH
        for key, value in (("passed", False), ("passed", "true"), ("exit_code", False),
                           ("exit_code", -11), ("source_sha256", "b" * 64),
                           ("patch_sha256", "b" * 64), ("runtime_sha256", "b" * 64)):
            with self.subTest(key=key, value=value):
                original = self.manifest[key]
                self.manifest[key] = value
                self.save()
                with self.assertRaises(VMError):
                    _qt_runtime_payload(self.path)
                self.manifest[key] = original

    @patch("e2e.vm.hashlib.file_digest")
    def test_rejects_actual_archive_hash_mismatch(self, digest):
        digest.return_value.hexdigest.return_value = "b" * 64
        self.save()
        with self.assertRaisesRegex(VMError, "source archive hash mismatch"):
            _qt_runtime_payload(self.path)

    @patch("e2e.vm.hashlib.file_digest")
    def test_rejects_old_guest_package_identity_and_missing_dependencies(self, digest):
        digest.return_value.hexdigest.return_value = SOURCE_HASH
        self.manifest["installed_dependencies"] = "qt6-qtbase-6.10.2-1.fc44.x86_64"
        self.save()
        with self.assertRaises(VMError):
            _qt_runtime_payload(self.path)
        self.manifest["installed_dependencies"] = "\n".join(PACKAGES)
        self.manifest["dependency_libraries"]["Core"]["path"] = "/tmp/libQt6Core.so.6.11.2"
        self.save()
        with self.assertRaisesRegex(VMError, "Core/Gui"):
            _qt_runtime_payload(self.path)

    @patch("e2e.vm.preflight")
    def test_option_is_rejected_for_preflight_and_reset(self, preflight):
        for command in ("preflight", "reset"):
            with self.subTest(command=command):
                self.assertEqual(main([command, "--qt-runtime-manifest", str(self.path)]), 2)
        preflight.assert_not_called()

    def test_default_run_has_no_corrected_runtime(self):
        vm = FedoraE2E(self.root)
        self.assertIsNone(vm._qt_runtime)

    @patch("e2e.vm._run")
    def test_staging_uses_guest_tmp_only_and_preserves_failure(self, run):
        vm = FedoraE2E(self.root, self.root)
        vm._qt_runtime = ({"manifest": self.manifest}, b"library", b"probe")
        with patch.object(vm, "_guest_exec", side_effect=[(0, "", ""), (2, "Qt mismatch", "")]) as execute, patch.object(vm, "_write_guest_file") as write:
            with self.assertRaisesRegex(VMError, "compatibility/regression failed"):
                vm._stage_qt_runtime()
        self.assertEqual(execute.call_args_list[0].args[0], "/usr/bin/mkdir")
        self.assertTrue(all(call.args[0].startswith("/var/tmp/loofi-e2e/") for call in write.call_args_list))
        self.assertEqual(len(write.call_args_list), 3)
        run.assert_not_called()
        self.assertTrue((self.root / "qt-runtime-host.json").exists())

    @patch("e2e.vm.hashlib.sha256")
    def test_runtime_mismatch_precedes_rpm_installation(self, sha256):
        vm = FedoraE2E(self.root, self.root)
        vm._qt_runtime = ({"manifest": self.manifest}, b"library", b"probe")
        revision = "50e41aa9913b16e5d0a6fec921c963485aa125b4"
        names = ("selenium-webdriver-at-spi.py", "app_roles.py")
        for name in names:
            (self.root / (revision + "-" + name)).write_bytes(b"cached driver")
        sha256.side_effect = [Mock(hexdigest=Mock(return_value=value)) for value in (
            "c0d317af690afe2c9625830f4452abce5f8e54dda3e294394abf155cba666fbd",
            "9d845a17539f388eaea89c89ae17b897dadad9f4a484a0e5c6e3299b61df70fd")]
        rpm = self.root / "candidate.rpm"
        rpm.write_bytes(b"candidate")
        with patch.object(vm, "_guest_exec", return_value=(0, "", "")) as execute, patch.object(
                vm, "_write_guest_file"), patch.object(vm, "_build_fixture", return_value=b"fixture"), patch.object(
                vm, "_validated_password", return_value="private"), patch.object(
                vm, "_stage_qt_runtime", side_effect=VMError("runtime mismatch")):
            with self.assertRaisesRegex(VMError, "runtime mismatch"):
                vm._prepare_payload(rpm)
        self.assertEqual(execute.call_count, 1)
        self.assertFalse(any("--install" in str(call.args) for call in execute.call_args_list))


class TestGuestQtGuard(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        directory = self.work / "qt-runtime"
        directory.mkdir()
        self.library = directory / "libQt6Widgets.so.6.11.2"
        self.library.write_bytes(b"widgets")
        probe = directory / "qt-scroll-probe"
        probe.write_bytes(b"probe")
        self.manifest = {"passed": True, "exit_code": 0, "runtime_sha256": hashlib.sha256(b"widgets").hexdigest(),
                         "dependency_libraries": {name: {"path": f"/usr/lib64/libQt6{name}.so.6.11.2", "sha256": hashlib.sha256(name.encode()).hexdigest()}
                                                  for name in ("Core", "Gui")}}
        self.payload = {"manifest": self.manifest, "expected_packages": PACKAGES, "probe_sha256": hashlib.sha256(b"probe").hexdigest()}
        (self.work / "qt-runtime-request.json").write_text(json.dumps(self.payload))
        (self.work / "credentials.json").write_text(json.dumps({"user": "fixture"}))
        self.mapping = (f"libQt6Widgets.so.6 => {directory}/libQt6Widgets.so.6 (0x1)\n"
                        "libQt6Core.so.6 => /lib64/libQt6Core.so.6 (0x2)\n"
                        "libQt6Gui.so.6 => /lib64/libQt6Gui.so.6 (0x3)\n")
        self.real_read = Path.read_bytes
        self.patchers = [patch.object(runner, "WORK", self.work), patch.object(runner.os, "chown"),
                         patch.object(runner.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=123, pw_gid=456)),
                         patch.object(Path, "read_bytes", autospec=True, side_effect=self.read_bytes)]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def read_bytes(self, path):
        for name in ("Core", "Gui"):
            if str(path) == f"/usr/lib64/libQt6{name}.so.6.11.2":
                return name.encode()
        return self.real_read(path)

    def results(self, code=0):
        return [subprocess.CompletedProcess([], 0, "\n".join(PACKAGES) + "\n", ""),
                subprocess.CompletedProcess([], 0, self.mapping, ""),
                subprocess.CompletedProcess([], code, "native probe", "")]

    @patch.object(runner.subprocess, "run")
    def test_matching_guest_qualifies_probe_with_process_scoped_environment(self, run):
        run.side_effect = self.results()
        with patch.dict(runner.os.environ, {"LD_LIBRARY_PATH": "/bad", "LD_PRELOAD": "/bad"}):
            evidence = runner._qualify_qt_runtime()
        self.assertTrue(evidence["passed"])
        self.assertEqual((self.library.parent / "libQt6Widgets.so.6").readlink(), Path(self.library.name))
        for call in run.call_args_list:
            self.assertNotIn("LD_LIBRARY_PATH", call.kwargs["env"])
            self.assertNotIn("LD_PRELOAD", call.kwargs["env"])
            self.assertIn("timeout", call.kwargs)
        self.assertEqual(run.call_args_list[1].args[0][0], "/lib64/ld-linux-x86-64.so.2")
        self.assertIn(f"LD_LIBRARY_PATH={self.library.parent}", run.call_args_list[2].args[0])
        self.assertTrue(json.loads((self.work / "qt-runtime-evidence.json").read_text())["passed"])

    @patch.object(runner.subprocess, "run")
    def test_old_guest_fails_before_library_link_or_probe(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "qt6-qtbase-6.10.2-1.fc44.x86_64\n", "")
        with self.assertRaisesRegex(RuntimeError, "packages do not match"):
            runner._qualify_qt_runtime()
        self.assertEqual(run.call_count, 1)
        self.assertFalse((self.library.parent / "libQt6Widgets.so.6").exists())
        evidence = json.loads((self.work / "qt-runtime-evidence.json").read_text())
        self.assertFalse(evidence["passed"])
        self.assertIn("6.10.2", evidence["error"])

    @patch.object(runner.subprocess, "run")
    def test_tampered_library_fails_before_any_guest_command(self, run):
        self.library.write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "artifact hash mismatch"):
            runner._qualify_qt_runtime()
        run.assert_not_called()

    @patch.object(runner.subprocess, "run")
    def test_dependency_hash_mismatch_fails_before_probe(self, run):
        self.payload["manifest"]["dependency_libraries"]["Core"]["sha256"] = "b" * 64
        (self.work / "qt-runtime-request.json").write_text(json.dumps(self.payload))
        run.side_effect = self.results()
        with self.assertRaisesRegex(RuntimeError, "QtCore library hash"):
            runner._qualify_qt_runtime()
        self.assertEqual(run.call_count, 1)

    @patch.object(runner.subprocess, "run")
    def test_probe_crash_is_preserved_as_failed_evidence(self, run):
        run.side_effect = self.results(code=-11)
        with self.assertRaisesRegex(RuntimeError, "native regression failed"):
            runner._qualify_qt_runtime()
        evidence = json.loads((self.work / "qt-runtime-evidence.json").read_text())
        self.assertFalse(evidence["passed"])
        self.assertEqual(evidence["exit_code"], -11)

    @patch.object(runner.subprocess, "run")
    def test_wrong_loaded_widgets_is_rejected(self, run):
        results = self.results()
        results[1].stdout = self.mapping.replace(str(self.library.parent), "/usr/lib64")
        run.side_effect = results
        with self.assertRaisesRegex(RuntimeError, "did not resolve"):
            runner._qualify_qt_runtime()
        self.assertEqual(run.call_count, 2)


class TestAppRuntimeEnvironment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        by = ModuleType("selenium.webdriver.common.by")
        by.By = Mock()
        modules = {key: ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common")}
        modules["selenium.webdriver.common.by"] = by
        spec = importlib.util.spec_from_file_location("qt_runtime_helpers", ROOT / "e2e/tests/helpers.py")
        cls.helpers = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(cls.helpers)

    @patch.dict("os.environ", {"LD_LIBRARY_PATH": "/untrusted", "LD_PRELOAD": "/untrusted", "LOOFI_E2E_CREDENTIALS_PATH": "private"}, clear=True)
    def test_default_application_strips_inherited_library_overrides_and_credentials(self):
        env = self.helpers.application_environment()
        self.assertNotIn("LD_LIBRARY_PATH", env)
        self.assertNotIn("LD_PRELOAD", env)
        self.assertNotIn("LOOFI_E2E_CREDENTIALS_PATH", env)

    @patch.dict("os.environ", {"LOOFI_E2E_QT_RUNTIME_DIR": "/var/tmp/loofi-e2e/qt-runtime"}, clear=True)
    @patch.object(Path, "read_text")
    @patch.object(Path, "read_bytes", return_value=b"widgets")
    def test_only_qualified_unchanged_library_is_added_to_app(self, read_bytes, read_text):
        read_text.return_value = json.dumps({"passed": True, "runtime_library_dir": "/var/tmp/loofi-e2e/qt-runtime",
                                            "runtime_sha256": hashlib.sha256(b"widgets").hexdigest()})
        self.assertEqual(self.helpers.application_environment()["LD_LIBRARY_PATH"], "/var/tmp/loofi-e2e/qt-runtime")
        read_bytes.return_value = b"changed"
        with self.assertRaisesRegex(RuntimeError, "changed after qualification"):
            self.helpers.application_environment()

    @patch.dict("os.environ", {"LOOFI_E2E_QT_RUNTIME_DIR": "/bad"}, clear=True)
    @patch.object(Path, "read_text", return_value='{"passed": true}')
    def test_alternate_staging_directory_is_rejected(self, read_text):
        with self.assertRaisesRegex(RuntimeError, "no successful guest qualification"):
            self.helpers.application_environment()

    @patch.dict("os.environ", {"LOOFI_E2E_QT_RUNTIME_DIR": "/var/tmp/loofi-e2e/qt-runtime"}, clear=True)
    @patch.object(Path, "write_text")
    @patch.object(Path, "exists", return_value=False)
    @patch.object(Path, "read_bytes", return_value=b"library")
    @patch.object(Path, "read_text")
    def test_actual_app_maps_are_required_and_saved(self, read_text, read_bytes, exists, write_text):
        checksum = hashlib.sha256(b"library").hexdigest()
        paths = {"Widgets": "/var/tmp/loofi-e2e/qt-runtime/libQt6Widgets.so.6.11.2",
                 "Core": "/usr/lib64/libQt6Core.so.6.11.2", "Gui": "/usr/lib64/libQt6Gui.so.6.11.2"}
        manifest = {"runtime_sha256": checksum, "dependency_libraries": {
            name: {"path": paths[name], "sha256": checksum} for name in ("Core", "Gui")}}
        maps = "\n".join(f"01-02 r-xp 0 0 0 {path}" for path in paths.values())
        read_text.side_effect = [json.dumps({"manifest": manifest}), maps]
        self.helpers.record_application_runtime(SimpleNamespace(pid=123))
        saved = json.loads(write_text.call_args.args[0])
        self.assertEqual(set(saved[0]["libraries"]), {"Widgets", "Core", "Gui"})
        self.assertEqual(saved[0]["pid"], 123)
        read_text.side_effect = [json.dumps({"manifest": manifest}), maps.replace(paths["Widgets"], "/usr/lib64/libQt6Widgets.so.6.11.2")]
        with self.assertRaisesRegex(RuntimeError, "expected QtWidgets"):
            self.helpers.record_application_runtime(SimpleNamespace(pid=123))


class TestIsolatedGraphics(unittest.TestCase):
    def validate(self, graphics):
        _validate_graphics(ET.fromstring("<domain><devices>" + graphics + "</devices></domain>"))

    def test_accepts_only_local_spice_or_explicit_none(self):
        for graphics in (
            "<graphics type='spice' autoport='yes'><listen type='address' address='127.0.0.1'/></graphics>",
            "<graphics type='spice'><listen type='none'/><image compression='off'/><gl enable='no'/></graphics>",
        ):
            with self.subTest(graphics=graphics):
                self.validate(graphics)

    def test_rejects_extra_devices_listeners_sockets_public_addresses_and_gl(self):
        disabled = "<graphics type='spice'><listen type='none'/></graphics>"
        cases = (
            "", disabled + disabled,
            disabled.replace("spice", "vnc"),
            disabled.replace("<listen type='none'/>", ""),
            disabled.replace("<listen type='none'/>", "<listen type='none'/><listen type='none'/>") ,
            disabled.replace("type='none'", "type='address' address='0.0.0.0'"),
            disabled.replace("type='none'", "type='address' address='192.0.2.1'"),
            disabled.replace("type='none'", "type='address' address='::'"),
            disabled.replace("type='none'", "type='none' address='127.0.0.1'"),
            disabled.replace("type='none'", "type='none' socket='/tmp/spice.sock'"),
            disabled.replace("type='none'", "type='socket' socket='/tmp/spice.sock'"),
            disabled.replace("type='spice'", "type='spice' socket='/tmp/spice.sock'"),
            disabled.replace("type='spice'", "type='spice' listen='127.0.0.1'"),
            disabled.replace("type='spice'", "type='spice' listen='0.0.0.0'"),
            disabled.replace("type='spice'", "type='spice' port='5900'"),
            disabled.replace("</graphics>", "<gl enable='yes'/></graphics>"),
            disabled.replace("</graphics>", "<gl/></graphics>"),
            disabled.replace("</graphics>", "<gl enable='no'/><gl enable='no'/></graphics>"),
            disabled.replace("</graphics>", "<socket path='/tmp/spice.sock'/></graphics>"),
            disabled.replace("</graphics>", "<other><listen type='none'/></other></graphics>"),
        )
        for graphics in cases:
            with self.subTest(graphics=graphics):
                with self.assertRaises(VMError):
                    self.validate(graphics)


class TestCorrectedRuntimeProvisioning(unittest.TestCase):
    @patch("e2e.vm._qt_runtime_payload", return_value=({"manifest": {}}, b"library", b"probe"))
    def test_updates_repo_is_explicit_corrected_runtime_only(self, payload):
        baseline = FedoraE2E(Path("/unused-e2e-test"))
        baseline_ks = baseline._kickstart("$6$fixture")
        payload.assert_not_called()
        manifest = Path("/mock/qualification.json")
        corrected = FedoraE2E(Path("/unused-e2e-test"), qt_runtime_manifest=manifest)
        corrected_ks = corrected._kickstart("$6$fixture")
        payload.assert_called_once_with(manifest)
        repository = (f'repo --name=loofi-e2e-fedora-updates --metalink="https://mirrors.fedoraproject.org/metalink?'
                      f'repo=updates-released-f{FEDORA_RELEASE}&arch=x86_64"\n')
        self.assertNotIn("loofi-e2e-fedora-updates", baseline_ks)
        self.assertEqual(corrected_ks.count(repository), 1)
        self.assertEqual(corrected_ks.replace(repository, ""), baseline_ks)
        self.assertLess(corrected_ks.index(repository), corrected_ks.index("%packages"))
        for bypass in ("--install", "--noverifyssl", "--nogpgcheck"):
            self.assertNotIn(bypass, repository)
