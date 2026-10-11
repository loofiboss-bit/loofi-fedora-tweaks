"""Repository runner setup contracts without changing host services or GitHub."""

import json
import subprocess
from unittest.mock import patch

import pytest

from e2e import ci_runner
from e2e.vm import VMError


def test_runner_plan_requires_explicit_approval_without_host_package_installation() -> None:
    details = ci_runner.plan()
    assert details["requires_explicit_host_approval"] is True
    assert details["system_packages_installed"] == []
    assert details["repository"] == ci_runner.REPOSITORY
    assert "loofi-vm-e2e" in details["labels"]


def test_unrelated_runner_directory_is_not_overwritten(tmp_path) -> None:
    root = tmp_path / "runner"
    root.mkdir()
    sentinel = root / "user-file"
    sentinel.write_text("keep")
    with patch.object(ci_runner, "preflight"), patch.object(ci_runner.shutil, "which", return_value="/usr/bin/gh"), patch.object(
        ci_runner, "plan", return_value={"install_directory": str(root), "user_service": str(tmp_path / "runner.service")}
    ):
        with pytest.raises(VMError, match="not owned"):
            ci_runner.install()
    assert sentinel.read_text() == "keep"


def test_registered_runner_with_utf8_bom_is_reused_without_download_or_registration(tmp_path) -> None:
    root = tmp_path / "runner"
    root.mkdir()
    (root / "loofi-runner.json").write_text(json.dumps({
        "repository": ci_runner.REPOSITORY, "name": ci_runner.RUNNER_NAME, "directory": str(root),
    }))
    (root / ".runner").write_text(json.dumps({
        "gitHubUrl": "https://github.com/" + ci_runner.REPOSITORY, "agentName": ci_runner.RUNNER_NAME,
    }), encoding="utf-8-sig")
    service = tmp_path / "user" / ci_runner.UNIT
    with patch.object(ci_runner, "preflight"), patch.object(ci_runner.shutil, "which", return_value="/usr/bin/gh"), patch.object(
        ci_runner, "plan", return_value={"install_directory": str(root), "user_service": str(service)}
    ), patch.object(ci_runner, "_run", return_value=json.dumps({
        "runners": [{"name": ci_runner.RUNNER_NAME, "status": "online"}],
    })) as run, patch.object(ci_runner.urllib.request, "urlopen") as download:
        ci_runner.install()
    download.assert_not_called()
    assert not any("registration-token" in str(call) for call in run.call_args_list)
    assert "ExecStart=" in service.read_text()
    assert f"WorkingDirectory={root}\n" in service.read_text()
    assert any(call.args[0] == ["systemctl", "--user", "enable", "--now", ci_runner.UNIT] for call in run.call_args_list)


def test_runner_command_failure_redacts_registration_token() -> None:
    token = "private-registration-token"
    with patch.object(ci_runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "error " + token)):
        with pytest.raises(VMError) as error:
            ci_runner._run(["config.sh"], env={"ACTIONS_RUNNER_INPUT_TOKEN": token})
    assert token not in str(error.value)
    assert "[redacted]" in str(error.value)
