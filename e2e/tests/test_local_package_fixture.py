"""Offline native package manager qualification, confined to the disposable VM.

These tests qualify DNF5 transaction/readback and Polkit, not an application
store removal UI. The fixture has no executable payload or dependencies.
"""
from pathlib import Path
import subprocess

from helpers import authenticate_polkit


FIXTURE = Path("/var/tmp/loofi-e2e/loofi-e2e-fixture.rpm")
NAME = "loofi-e2e-fixture"
PAYLOAD = Path("/usr/share/loofi-e2e-fixture/probe.txt")


def installed() -> bool:
    result = subprocess.run(["rpm", "-q", "--qf", "%{NAME} %{VERSION}-%{RELEASE}", NAME],
                            text=True, capture_output=True, check=False, timeout=10)
    if result.returncode == 1:
        return False
    assert result.returncode == 0, result.stderr
    assert result.stdout == "loofi-e2e-fixture 1.0-1"
    return True


def transaction(arguments: list[str], completed) -> None:
    with open("/var/tmp/loofi-e2e/package-fixture.log", "a", encoding="utf-8") as log:
        process = subprocess.Popen(["pkexec", "/usr/bin/dnf5", "--cacheonly", "--assumeyes", "--disable-repo=*", *arguments],
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, text=True)
        try:
            def readback():
                if process.poll() is not None and process.returncode:
                    raise AssertionError("Guest fixture transaction failed; inspect package-fixture.log")
                return completed()
            authenticate_polkit(completed=readback)
            assert process.wait(timeout=90) == 0, "Guest fixture transaction failed"
            assert completed(), "DNF exit success did not match independent RPM/payload readback"
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def test_offline_local_fixture_install_and_remove_preserves_unrelated_packages(loofi_app) -> None:
    assert FIXTURE.is_file(), "VM infrastructure must stage the fixed inert RPM fixture"
    metadata = subprocess.run(["rpm", "-qp", "--qf", "%{NAME} %{VERSION}-%{RELEASE}", str(FIXTURE)],
                              capture_output=True, text=True, check=True, timeout=10)
    assert metadata.stdout == "loofi-e2e-fixture 1.0-1"
    files = subprocess.run(["rpm", "-qpl", str(FIXTURE)], capture_output=True, text=True, check=True, timeout=10)
    assert files.stdout.splitlines() == [str(PAYLOAD)], "fixture contains unexpected files"
    scripts = subprocess.run(["rpm", "-qp", "--scripts", str(FIXTURE)], capture_output=True, text=True, check=True, timeout=10)
    assert not scripts.stdout.strip(), "fixture must not execute transaction scripts"
    requires = subprocess.run(["rpm", "-qp", "--requires", str(FIXTURE)], capture_output=True, text=True, check=True, timeout=10)
    assert all(line.startswith("rpmlib(") for line in requires.stdout.splitlines()), "fixture has real package dependencies"
    assert not installed() and not PAYLOAD.exists(), "fixture must be absent in the clean overlay"
    before = subprocess.run(["rpm", "-qa"], capture_output=True, text=True, check=True, timeout=30).stdout.splitlines()
    try:
        transaction(["install", str(FIXTURE)], lambda: installed() and PAYLOAD.is_file())
        assert PAYLOAD.read_text().strip() == NAME
        verification = subprocess.run(["rpm", "-V", NAME], capture_output=True, text=True, check=False, timeout=10)
        assert verification.returncode == 0 and not verification.stdout
    finally:
        if installed():
            transaction(["--setopt=clean_requirements_on_remove=False", "remove", NAME],
                        lambda: not installed() and not PAYLOAD.exists())
    after = subprocess.run(["rpm", "-qa"], capture_output=True, text=True, check=True, timeout=30).stdout.splitlines()
    assert sorted(after) == sorted(before), "fixture cycle changed unrelated RPM packages"
